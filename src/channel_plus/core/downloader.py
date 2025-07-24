"""
Async audio downloader for Channel Plus episodes.

Handles concurrent downloads with progress tracking, resume capability,
and robust error handling.
"""

import asyncio
import logging
import json
from pathlib import Path
from typing import List, Dict, Callable, Optional, Any, Set
from datetime import datetime

from rich.progress import Progress, TaskID, BarColumn, TextColumn, TimeRemainingColumn, SpinnerColumn
from rich.console import Console

from ..core.models import Episode, DownloadConfig, DownloadProgress
from ..utils.http_client import ChannelPlusHTTPClient


logger = logging.getLogger(__name__)


class ChannelPlusDownloader:
    """Async downloader for Channel Plus audio files."""
    
    def __init__(self, http_client: ChannelPlusHTTPClient, config: DownloadConfig):
        """
        Initialize downloader.
        
        Args:
            http_client: HTTP client for downloads
            config: Download configuration
        """
        self.http_client = http_client
        self.config = config
        self.console = Console()
        
        # Track download progress
        self.download_stats: Dict[int, DownloadProgress] = {}
        self.failed_downloads: List[Episode] = []
        self.successful_downloads: List[Episode] = []
        self.skipped_downloads: List[Episode] = []
        
        # Resume functionality
        self.resume_file = config.path / ".channel_plus_resume.json"
        self.completed_files: Set[str] = set()
        self.min_file_size = 1024  # Minimum file size to consider valid (1KB)
    
    def load_resume_state(self) -> Dict[str, Any]:
        """
        Load resume state from file.
        
        Returns:
            Dictionary with previously completed downloads
        """
        try:
            if self.resume_file.exists():
                with open(self.resume_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"Loaded resume state: {len(data.get('completed_files', []))} completed files")
                    return data
        except Exception as e:
            logger.warning(f"Could not load resume state: {e}")
        
        return {'completed_files': [], 'last_updated': None}
    
    def save_resume_state(self, completed_files: List[str]) -> None:
        """
        Save resume state to file.
        
        Args:
            completed_files: List of completed file paths
        """
        try:
            # Ensure directory exists
            self.resume_file.parent.mkdir(parents=True, exist_ok=True)
            
            resume_data = {
                'completed_files': completed_files,
                'last_updated': datetime.now().isoformat(),
                'config': {
                    'concurrent_downloads': self.config.concurrent_downloads,
                    'total_episodes': len(completed_files)
                }
            }
            
            with open(self.resume_file, 'w', encoding='utf-8') as f:
                json.dump(resume_data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Saved resume state: {len(completed_files)} completed files")
        except Exception as e:
            logger.warning(f"Could not save resume state: {e}")
    
    def is_file_complete(self, file_path: Path, episode: Episode) -> bool:
        """
        Check if a file is complete and valid.
        
        Args:
            file_path: Path to the file to check
            episode: Episode information for validation
            
        Returns:
            True if file is complete and valid
        """
        if not file_path.exists():
            return False
        
        # Check file size
        file_size = file_path.stat().st_size
        if file_size < self.min_file_size:
            logger.debug(f"File {file_path.name} too small ({file_size} bytes), marking incomplete")
            return False
        
        # For audio files, we can do basic format validation
        if file_path.suffix.lower() in ['.mp3', '.wav', '.m4a']:
            try:
                # Check if file starts with valid audio header
                with open(file_path, 'rb') as f:
                    header = f.read(10)
                    
                # MP3 file should start with ID3 tag or sync frame
                if header.startswith(b'ID3') or header.startswith(b'\xff\xfb'):
                    return True
                # M4A files start with ftyp
                elif b'ftyp' in header:
                    return True
                else:
                    logger.debug(f"File {file_path.name} has invalid audio header, marking incomplete")
                    return False
            except Exception as e:
                logger.debug(f"Could not validate {file_path.name}: {e}")
                return False
        
        # For non-audio files, size check is sufficient
        return True
    
    def filter_episodes_for_download(
        self, 
        episodes: List[Episode], 
        force_redownload: bool = False
    ) -> Dict[str, List[Episode]]:
        """
        Filter episodes based on existing files and resume state.
        
        Args:
            episodes: List of all episodes
            force_redownload: If True, download all episodes regardless of existing files
            
        Returns:
            Dictionary with 'to_download', 'existing', and 'invalid' episode lists
        """
        if force_redownload:
            return {
                'to_download': episodes,
                'existing': [],
                'invalid': []
            }
        
        # Load resume state
        resume_state = self.load_resume_state()
        completed_files = set(resume_state.get('completed_files', []))
        
        to_download = []
        existing = []
        invalid = []
        
        for episode in episodes:
            file_path = self.config.path / episode.safe_filename
            relative_path = str(file_path.relative_to(self.config.path))
            
            if relative_path in completed_files and self.is_file_complete(file_path, episode):
                # File was completed in previous run and is still valid
                existing.append(episode)
                self.completed_files.add(relative_path)
            elif file_path.exists():
                if self.is_file_complete(file_path, episode):
                    # File exists and is complete but not in resume state
                    existing.append(episode)
                    self.completed_files.add(relative_path)
                else:
                    # File exists but is incomplete/invalid
                    invalid.append(episode)
                    # Delete invalid file
                    try:
                        file_path.unlink()
                        logger.info(f"Deleted invalid file: {file_path.name}")
                    except Exception as e:
                        logger.warning(f"Could not delete invalid file {file_path.name}: {e}")
                    to_download.append(episode)
            else:
                # File doesn't exist
                to_download.append(episode)
        
        return {
            'to_download': to_download,
            'existing': existing,
            'invalid': invalid
        }
        
    async def download_episode(
        self,
        episode: Episode,
        progress_callback: Optional[Callable[[int, Optional[int]], None]] = None,
        force_download: bool = False
    ) -> bool:
        """
        Download a single episode.
        
        Args:
            episode: Episode to download
            progress_callback: Optional callback for progress updates
            force_download: If True, download even if file exists
            
        Returns:
            True if download successful, False otherwise
        """
        # Create progress tracking
        progress = DownloadProgress(episode=episode, status="starting")
        self.download_stats[episode.part] = progress
        
        try:
            # Determine file path
            file_path = self.config.path / episode.safe_filename
            relative_path = str(file_path.relative_to(self.config.path))
            
            # Skip if file already exists and is complete (unless force_download)
            if not force_download and self.is_file_complete(file_path, episode):
                logger.info(f"Episode {episode.part} already exists and is complete, skipping")
                progress.status = "skipped"
                self.skipped_downloads.append(episode)
                self.completed_files.add(relative_path)
                return True
            
            logger.info(f"Downloading episode {episode.part}: {episode.name}")
            progress.status = "downloading"
            
            # Create progress callback that updates our tracking
            def track_progress(bytes_downloaded: int, total_bytes: Optional[int]):
                progress.bytes_downloaded = bytes_downloaded
                progress.total_bytes = total_bytes
                
                if progress_callback:
                    progress_callback(bytes_downloaded, total_bytes)
            
            # Download the file
            success = await self.http_client.download_file(
                episode.audio_url,
                file_path,
                progress_callback=track_progress
            )
            
            if success:
                progress.status = "completed"
                self.successful_downloads.append(episode)
                self.completed_files.add(relative_path)
                
                # Save resume state after each successful download
                self.save_resume_state(list(self.completed_files))
                
                logger.info(f"✅ Successfully downloaded episode {episode.part}")
                return True
            else:
                progress.status = "failed"
                progress.error_message = "Download failed"
                self.failed_downloads.append(episode)
                logger.error(f"❌ Failed to download episode {episode.part}")
                return False
                
        except Exception as e:
            progress.status = "failed"
            progress.error_message = str(e)
            self.failed_downloads.append(episode)
            logger.error(f"❌ Error downloading episode {episode.part}: {e}")
            return False
    
    async def download_episodes_batch(
        self,
        episodes: List[Episode],
        show_progress: bool = True,
        force_redownload: bool = False
    ) -> Dict[str, Any]:
        """
        Download multiple episodes with progress tracking and resume support.
        
        Args:
            episodes: List of episodes to download
            show_progress: Whether to show progress bars
            force_redownload: If True, download all episodes regardless of existing files
            
        Returns:
            Dictionary with download results and statistics
        """
        if not episodes:
            logger.warning("No episodes to download")
            return self._get_download_summary()
        
        # Filter episodes based on existing files and resume state
        episode_filter = self.filter_episodes_for_download(episodes, force_redownload)
        to_download = episode_filter['to_download']
        existing = episode_filter['existing']
        invalid = episode_filter['invalid']
        
        # Add existing files to successful downloads for stats
        self.skipped_downloads.extend(existing)
        
        if existing:
            logger.info(f"Found {len(existing)} existing complete files, skipping")
        if invalid:
            logger.info(f"Found {len(invalid)} invalid files, will redownload")
        
        if not to_download:
            logger.info("All episodes already downloaded and complete!")
            return self._get_download_summary()
        
        logger.info(f"Starting download of {len(to_download)} episodes (out of {len(episodes)} total)")
        logger.info(f"Concurrent downloads: {self.config.concurrent_downloads}")
        
        # Create semaphore to limit concurrent downloads
        semaphore = asyncio.Semaphore(self.config.concurrent_downloads)
        
        # Set up progress display
        if show_progress:
            progress_display = Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TextColumn("({task.completed}/{task.total})"),
                TimeRemainingColumn(),
                console=self.console
            )
        else:
            progress_display = None
        
        # Track overall progress
        overall_task = None
        episode_tasks: Dict[int, TaskID] = {}
        
        async def download_with_semaphore(episode: Episode) -> bool:
            """Download single episode with concurrency control."""
            async with semaphore:
                # Create individual progress task
                if progress_display:
                    task_id = progress_display.add_task(
                        f"Episode {episode.part}",
                        total=100
                    )
                    episode_tasks[episode.part] = task_id
                
                def update_progress(bytes_downloaded: int, total_bytes: Optional[int]):
                    if progress_display and episode.part in episode_tasks:
                        if total_bytes and total_bytes > 0:
                            percentage = (bytes_downloaded / total_bytes) * 100
                            progress_display.update(
                                episode_tasks[episode.part],
                                completed=percentage
                            )
                
                result = await self.download_episode(episode, update_progress, force_redownload)
                
                # Update overall progress
                if progress_display and overall_task:
                    progress_display.advance(overall_task)
                
                return result
        
        # Start progress display
        download_start_time = datetime.now()
        
        if progress_display:
            with progress_display:
                overall_task = progress_display.add_task(
                    "Overall Progress",
                    total=len(to_download)
                )
                
                # Create download tasks
                download_tasks = [
                    download_with_semaphore(episode)
                    for episode in to_download
                ]
                
                # Run all downloads
                results = await asyncio.gather(*download_tasks, return_exceptions=True)
        else:
            # Run without progress display
            download_tasks = [
                download_with_semaphore(episode)
                for episode in to_download
            ]
            results = await asyncio.gather(*download_tasks, return_exceptions=True)
        
        download_end_time = datetime.now()
        download_duration = (download_end_time - download_start_time).total_seconds()
        
        # Process results
        successful_count = sum(1 for result in results if result is True)
        failed_count = len(to_download) - successful_count
        total_existing = len(existing)
        
        logger.info(f"Download completed in {download_duration:.1f} seconds")
        logger.info(f"✅ Downloaded: {successful_count}")
        logger.info(f"⏭️  Skipped (existing): {total_existing}")
        logger.info(f"❌ Failed: {failed_count}")
        logger.info(f"📁 Total episodes processed: {len(episodes)}")
        
        return self._get_download_summary(download_duration)
    
    def _get_download_summary(self, duration: Optional[float] = None) -> Dict[str, Any]:
        """
        Get comprehensive download summary.
        
        Args:
            duration: Total download duration in seconds
            
        Returns:
            Dictionary with download statistics
        """
        total_episodes = len(self.successful_downloads) + len(self.failed_downloads) + len(self.skipped_downloads)
        downloaded_episodes = len(self.successful_downloads)
        skipped_episodes = len(self.skipped_downloads)
        
        total_bytes = sum(
            progress.bytes_downloaded
            for progress in self.download_stats.values()
            if progress.bytes_downloaded > 0
        )
        
        summary = {
            'total_episodes': total_episodes,
            'successful_downloads': downloaded_episodes,
            'skipped_downloads': skipped_episodes,
            'failed_downloads': len(self.failed_downloads),
            'success_rate': (
                (downloaded_episodes + skipped_episodes) / total_episodes * 100
                if total_episodes > 0 else 0
            ),
            'download_rate': (
                downloaded_episodes / total_episodes * 100
                if total_episodes > 0 else 0
            ),
            'total_bytes_downloaded': total_bytes,
            'failed_episodes': [ep.part for ep in self.failed_downloads],
            'successful_episodes': [ep.part for ep in self.successful_downloads],
            'skipped_episodes': [ep.part for ep in self.skipped_downloads],
        }
        
        if duration:
            summary['duration_seconds'] = duration
            summary['average_speed_mbps'] = (
                (total_bytes / (1024 * 1024)) / duration
                if duration > 0 else 0
            )
        
        return summary
    
    async def retry_failed_downloads(self, max_retries: int = 2) -> Dict[str, Any]:
        """
        Retry failed downloads.
        
        Args:
            max_retries: Maximum number of retry attempts
            
        Returns:
            Summary of retry results
        """
        if not self.failed_downloads:
            logger.info("No failed downloads to retry")
            return self._get_download_summary()
        
        logger.info(f"Retrying {len(self.failed_downloads)} failed downloads")
        
        retry_episodes = self.failed_downloads.copy()
        self.failed_downloads.clear()
        
        for attempt in range(max_retries):
            if not retry_episodes:
                break
                
            logger.info(f"Retry attempt {attempt + 1}/{max_retries}")
            
            # Wait before retry
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
            
            # Try downloading failed episodes again
            await self.download_episodes_batch(retry_episodes, show_progress=False)
            
            # Update retry list
            retry_episodes = self.failed_downloads.copy()
            self.failed_downloads.clear()
        
        return self._get_download_summary()
    
    def print_summary(self, summary: Dict[str, Any]) -> None:
        """
        Print a formatted download summary.
        
        Args:
            summary: Download summary dictionary
        """
        self.console.print("\n[bold blue]Download Summary[/bold blue]")
        self.console.print("=" * 50)
        
        self.console.print(f"Total Episodes: {summary['total_episodes']}")
        self.console.print(f"✅ Downloaded: {summary['successful_downloads']}")
        self.console.print(f"⏭️  Skipped (existing): {summary['skipped_downloads']}")
        self.console.print(f"❌ Failed: {summary['failed_downloads']}")
        self.console.print(f"Success Rate: {summary['success_rate']:.1f}%")
        if summary['skipped_downloads'] > 0:
            self.console.print(f"Download Rate: {summary['download_rate']:.1f}% (new files only)")
        
        if summary['total_bytes_downloaded'] > 0:
            mb_downloaded = summary['total_bytes_downloaded'] / (1024 * 1024)
            self.console.print(f"Total Downloaded: {mb_downloaded:.1f} MB")
        
        if 'duration_seconds' in summary:
            duration = summary['duration_seconds']
            self.console.print(f"Duration: {duration:.1f} seconds")
            
        if 'average_speed_mbps' in summary:
            speed = summary['average_speed_mbps']
            self.console.print(f"Average Speed: {speed:.2f} MB/s")
        
        if summary['failed_episodes']:
            self.console.print(f"\n❌ Failed Episodes: {summary['failed_episodes']}")
        
        self.console.print("=" * 50)