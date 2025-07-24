"""
Async audio downloader for Channel Plus episodes.

Handles concurrent downloads with progress tracking, resume capability,
and robust error handling.
"""

import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Callable, Optional, Any
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
        
    async def download_episode(
        self,
        episode: Episode,
        progress_callback: Optional[Callable[[int, Optional[int]], None]] = None
    ) -> bool:
        """
        Download a single episode.
        
        Args:
            episode: Episode to download
            progress_callback: Optional callback for progress updates
            
        Returns:
            True if download successful, False otherwise
        """
        # Create progress tracking
        progress = DownloadProgress(episode=episode, status="starting")
        self.download_stats[episode.part] = progress
        
        try:
            # Determine file path
            file_path = self.config.path / episode.safe_filename
            
            # Skip if file already exists and is complete
            if file_path.exists() and file_path.stat().st_size > 0:
                logger.info(f"Episode {episode.part} already exists, skipping")
                progress.status = "skipped"
                self.successful_downloads.append(episode)
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
        show_progress: bool = True
    ) -> Dict[str, Any]:
        """
        Download multiple episodes with progress tracking.
        
        Args:
            episodes: List of episodes to download
            show_progress: Whether to show progress bars
            
        Returns:
            Dictionary with download results and statistics
        """
        if not episodes:
            logger.warning("No episodes to download")
            return self._get_download_summary()
        
        logger.info(f"Starting download of {len(episodes)} episodes")
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
                
                result = await self.download_episode(episode, update_progress)
                
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
                    total=len(episodes)
                )
                
                # Create download tasks
                download_tasks = [
                    download_with_semaphore(episode)
                    for episode in episodes
                ]
                
                # Run all downloads
                results = await asyncio.gather(*download_tasks, return_exceptions=True)
        else:
            # Run without progress display
            download_tasks = [
                download_with_semaphore(episode)
                for episode in episodes
            ]
            results = await asyncio.gather(*download_tasks, return_exceptions=True)
        
        download_end_time = datetime.now()
        download_duration = (download_end_time - download_start_time).total_seconds()
        
        # Process results
        successful_count = sum(1 for result in results if result is True)
        failed_count = len(episodes) - successful_count
        
        logger.info(f"Download completed in {download_duration:.1f} seconds")
        logger.info(f"✅ Successful: {successful_count}")
        logger.info(f"❌ Failed: {failed_count}")
        
        return self._get_download_summary(download_duration)
    
    def _get_download_summary(self, duration: Optional[float] = None) -> Dict[str, Any]:
        """
        Get comprehensive download summary.
        
        Args:
            duration: Total download duration in seconds
            
        Returns:
            Dictionary with download statistics
        """
        total_episodes = len(self.successful_downloads) + len(self.failed_downloads)
        total_bytes = sum(
            progress.bytes_downloaded
            for progress in self.download_stats.values()
            if progress.bytes_downloaded > 0
        )
        
        summary = {
            'total_episodes': total_episodes,
            'successful_downloads': len(self.successful_downloads),
            'failed_downloads': len(self.failed_downloads),
            'success_rate': (
                len(self.successful_downloads) / total_episodes * 100
                if total_episodes > 0 else 0
            ),
            'total_bytes_downloaded': total_bytes,
            'failed_episodes': [ep.part for ep in self.failed_downloads],
            'successful_episodes': [ep.part for ep in self.successful_downloads],
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
        self.console.print(f"✅ Successful: {summary['successful_downloads']}")
        self.console.print(f"❌ Failed: {summary['failed_downloads']}")
        self.console.print(f"Success Rate: {summary['success_rate']:.1f}%")
        
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