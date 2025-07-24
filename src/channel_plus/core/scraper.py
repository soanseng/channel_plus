"""
Web scraper for Channel Plus website.

Extracts episode information from the Channel Plus website by parsing
the JSON data embedded in the page's window.__PRELOADED_STATE__.
"""

import json
import re
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from ..core.models import Episode, LanguageEpisodeData, DownloadConfig, AttachmentInfo
from ..core.config import ChannelPlusConfig
from ..utils.http_client import ChannelPlusHTTPClient


logger = logging.getLogger(__name__)


class ChannelPlusScraper:
    """Scraper for extracting episode data from Channel Plus website."""
    
    def __init__(self, http_client: ChannelPlusHTTPClient):
        """
        Initialize scraper with HTTP client.
        
        Args:
            http_client: HTTP client for making requests
        """
        self.http_client = http_client
        self.config = ChannelPlusConfig()
    
    async def extract_episodes_from_page(self, course_id: int, page: int) -> List[Episode]:
        """
        Extract episode data from a single page.
        
        Args:
            course_id: Course ID (extracted from URL)
            page: Page number to scrape
            
        Returns:
            List of Episode objects from the page
            
        Raises:
            ValueError: If page data cannot be parsed
            Exception: If HTTP request fails
        """
        url = self.config.get_course_url(course_id, page)
        logger.info(f"Scraping page {page} from {url}")
        
        try:
            # Get page content
            page_content = await self.http_client.get_text(url)
            
            # Extract JSON data using regex (same pattern as original Elixir code)
            json_pattern = r'window\.__PRELOADED_STATE__ = ({.+})'
            match = re.search(json_pattern, page_content)
            
            if not match:
                logger.warning(f"No JSON data found on page {page}")
                return []
            
            # Parse JSON data
            json_str = match.group(1)
            try:
                page_data = json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from page {page}: {e}")
                raise ValueError(f"Invalid JSON data on page {page}") from e
            
            # Navigate to episode data following the same path as Elixir code
            # reducers.languageEpisode.data
            try:
                reducers = page_data['reducers']
                language_episode = reducers['languageEpisode']
                
                # Parse using Pydantic model for validation
                episode_data = LanguageEpisodeData(**language_episode)
                
                logger.info(f"Found {len(episode_data.data)} episodes on page {page}")
                return episode_data.data
                
            except KeyError as e:
                logger.error(f"Missing expected key in JSON structure: {e}")
                logger.debug(f"Available keys: {list(page_data.keys())}")
                if 'reducers' in page_data:
                    logger.debug(f"Reducer keys: {list(page_data['reducers'].keys())}")
                return []
            
        except Exception as e:
            logger.error(f"Failed to scrape page {page}: {e}")
            raise
    
    async def get_all_episodes(self, config: DownloadConfig) -> List[Episode]:
        """
        Get all episodes within the specified range.
        
        Args:
            config: Download configuration with episode range
            
        Returns:
            List of episodes within the requested range
        """
        # Extract course ID from URL
        course_id = self._extract_course_id(config.link)
        if not course_id:
            raise ValueError(f"Cannot extract course ID from URL: {config.link}")
        
        logger.info(f"Collecting episodes {config.start_episode} to {config.final_episode}")
        logger.info(f"Scanning pages {config.start_page} to {config.final_page}")
        
        all_episodes = []
        
        # Scrape each page in the range
        for page_num in range(config.start_page, config.final_page + 1):
            try:
                logger.info(f"Processing page {page_num}...")
                episodes_on_page = await self.extract_episodes_from_page(course_id, page_num)
                
                # Filter episodes to only include those in our desired range
                for episode in episodes_on_page:
                    if config.start_episode <= episode.part <= config.final_episode:
                        all_episodes.append(episode)
                        logger.debug(f"Added episode {episode.part}: {episode.name}")
                
                # Add delay between page requests
                await self.http_client.add_delay()
                
            except Exception as e:
                logger.error(f"Failed to process page {page_num}: {e}")
                # Continue with other pages
                continue
        
        # Sort episodes by part number to ensure correct order
        all_episodes.sort(key=lambda ep: ep.part)
        
        logger.info(f"Successfully collected {len(all_episodes)} episodes")
        return all_episodes
    
    def _extract_course_id(self, url: str) -> Optional[int]:
        """
        Extract course ID from Channel Plus URL.
        
        Args:
            url: Channel Plus course URL
            
        Returns:
            Course ID as integer, or None if not found
        """
        # Pattern: https://channelplus.ner.gov.tw/viewalllang/390
        pattern = r'/viewalllang/(\d+)'
        match = re.search(pattern, url)
        
        if match:
            course_id = int(match.group(1))
            logger.debug(f"Extracted course ID: {course_id}")
            return course_id
        
        logger.error(f"Could not extract course ID from URL: {url}")
        return None
    
    async def get_course_name(self, course_id: int) -> Optional[str]:
        """
        Extract course name from the first page.
        
        Args:
            course_id: Course ID
            
        Returns:
            Course name suitable for folder creation, or None if not found
        """
        try:
            episodes = await self.extract_episodes_from_page(course_id, 1)
            if not episodes:
                return None
            
            # Get the course name from the first episode's audio name
            # Usually contains the course title
            audio_name = episodes[0].audio.name
            
            # Extract course name from audio filename
            # Pattern: "10001coursename.mp3" -> "coursename"
            import re
            
            # Try to extract course name from various patterns
            patterns = [
                r'\d+(.+?)\.mp3$',  # "10001coursename.mp3"
                r'\d+(.+?)$',       # "10001coursename"
                r'(.+?)\.mp3$',     # "coursename.mp3"
            ]
            
            for pattern in patterns:
                match = re.search(pattern, audio_name)
                if match:
                    course_name = match.group(1)
                    # Clean the course name for folder creation
                    course_name = self._clean_folder_name(course_name)
                    if course_name:
                        logger.debug(f"Extracted course name: {course_name}")
                        return course_name
            
            # Fallback: use episode name
            episode_name = episodes[0].name
            if episode_name:
                # Extract course name from episode title
                # Usually the first part before specific lesson info
                parts = episode_name.split(' ')
                if len(parts) > 1:
                    course_name = parts[0]
                    course_name = self._clean_folder_name(course_name)
                    if course_name:
                        return course_name
            
            # Final fallback
            return f"course_{course_id}"
            
        except Exception as e:
            logger.error(f"Failed to extract course name: {e}")
            return f"course_{course_id}"
    
    def _clean_folder_name(self, name: str) -> str:
        """
        Clean a string to be suitable for folder name.
        
        Args:
            name: Raw name string
            
        Returns:
            Cleaned folder name
        """
        if not name:
            return ""
        
        # Remove common prefixes/suffixes
        name = re.sub(r'^(第\d+課|課程|教學)', '', name)
        name = re.sub(r'(課程|教學|講義)$', '', name)
        
        # Remove invalid characters for folder names
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        name = re.sub(r'\s+', '', name)  # Remove all whitespace
        
        # Limit length
        if len(name) > 50:
            name = name[:50]
        
        return name.strip()
    
    async def get_total_episodes(self, course_id: int, max_pages: int = 50) -> int:
        """
        Determine the total number of episodes in a course.
        
        Args:
            course_id: Course ID
            max_pages: Maximum pages to scan (safety limit)
            
        Returns:
            Total number of episodes
        """
        try:
            logger.info(f"Scanning course {course_id} to find total episodes...")
            
            max_episode = 0
            page = 1
            
            while page <= max_pages:
                episodes = await self.extract_episodes_from_page(course_id, page)
                
                if not episodes:
                    # No more episodes, we've reached the end
                    break
                
                # Update max episode number found
                page_max = max(ep.part for ep in episodes)
                max_episode = max(max_episode, page_max)
                
                logger.debug(f"Page {page}: found episodes up to {page_max}")
                
                # If we got less than 10 episodes, this is likely the last page
                if len(episodes) < 10:
                    break
                
                page += 1
                await self.http_client.add_delay()
            
            logger.info(f"Total episodes found: {max_episode}")
            return max_episode
            
        except Exception as e:
            logger.error(f"Failed to determine total episodes: {e}")
            # Fallback: try to get from first page and estimate
            try:
                episodes = await self.extract_episodes_from_page(course_id, 1)
                if episodes:
                    return max(ep.part for ep in episodes) * 10  # Rough estimate
            except:
                pass
            
            return 100  # Conservative fallback
    
    async def validate_course_url(self, url: str) -> bool:
        """
        Validate that a course URL is accessible and contains episode data.
        
        Args:
            url: Course URL to validate
            
        Returns:
            True if URL is valid and contains episodes
        """
        course_id = self._extract_course_id(url)
        if not course_id:
            return False
        
        try:
            # Try to get first page
            episodes = await self.extract_episodes_from_page(course_id, 1)
            return len(episodes) > 0
        except Exception as e:
            logger.error(f"Course URL validation failed: {e}")
            return False
    
    async def get_course_info(self, url: str) -> Dict[str, Any]:
        """
        Get basic information about a course.
        
        Args:
            url: Course URL
            
        Returns:
            Dictionary with course information
        """
        course_id = self._extract_course_id(url)
        if not course_id:
            raise ValueError(f"Invalid course URL: {url}")
        
        try:
            # Get first page to determine course info
            episodes = await self.extract_episodes_from_page(course_id, 1)
            
            if not episodes:
                raise ValueError("No episodes found in course")
            
            # Get a few more pages to estimate total episodes
            total_episodes_estimate = len(episodes)
            
            # Try a few more pages to get better estimate
            for page in range(2, 6):  # Check up to page 5
                try:
                    page_episodes = await self.extract_episodes_from_page(course_id, page)
                    if not page_episodes:
                        break
                    total_episodes_estimate += len(page_episodes)
                    await self.http_client.add_delay()
                except:
                    break
            
            return {
                'course_id': course_id,
                'url': url,
                'episodes_found': total_episodes_estimate,
                'sample_episode': episodes[0].dict() if episodes else None,
                'max_episode_found': max(ep.part for ep in episodes) if episodes else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get course info: {e}")
            raise
    
    async def detect_course_materials(self, course_id: int) -> List[Tuple[AttachmentInfo, str]]:
        """
        Detect course materials (PDFs, documents) from the first page.
        
        Args:
            course_id: Course ID to check for materials
            
        Returns:
            List of tuples (attachment_info, download_url)
        """
        try:
            logger.info(f"Detecting course materials for course {course_id}...")
            
            # Get first page to check for materials
            episodes = await self.extract_episodes_from_page(course_id, 1)
            
            if not episodes:
                logger.info("No episodes found, no materials to detect")
                return []
            
            materials = []
            
            # Check all episodes on first page for materials
            for episode in episodes:
                if not episode.attachment:
                    continue
                
                for attachment in episode.attachment:
                    # Skip string attachments, focus on AttachmentInfo objects
                    if isinstance(attachment, str):
                        continue
                    
                    if isinstance(attachment, AttachmentInfo) and attachment.key:
                        # Generate download URL
                        download_url = f"https://channelplus.ner.gov.tw/api/files/{attachment.key}"
                        materials.append((attachment, download_url))
                        
                        logger.info(f"Found material: {attachment.name} -> {download_url}")
            
            if materials:
                logger.info(f"Found {len(materials)} course materials")
            else:
                logger.info("No course materials found")
            
            return materials
            
        except Exception as e:
            logger.error(f"Failed to detect course materials: {e}")
            return []
    
    async def download_course_materials(self, materials: List[Tuple[AttachmentInfo, str]], download_path: Path) -> List[Dict[str, Any]]:
        """
        Download course materials to the specified path.
        
        Args:
            materials: List of (attachment_info, download_url) tuples
            download_path: Path to download materials to
            
        Returns:
            List of download results with status information
        """
        if not materials:
            return []
        
        logger.info(f"Downloading {len(materials)} course materials to {download_path}")
        
        # Ensure materials subdirectory exists
        materials_path = download_path / "course_materials"
        materials_path.mkdir(exist_ok=True)
        
        results = []
        
        for attachment, download_url in materials:
            try:
                # Generate safe filename
                filename = self._generate_material_filename(attachment)
                file_path = materials_path / filename
                
                logger.info(f"Downloading {attachment.name} -> {file_path}")
                
                # Download the file
                content = await self.http_client.get_content(download_url)
                
                # Write to file
                with open(file_path, 'wb') as f:
                    f.write(content)
                
                result = {
                    'attachment': attachment,
                    'url': download_url,
                    'file_path': file_path,
                    'status': 'success',
                    'size': len(content)
                }
                
                logger.info(f"✅ Downloaded {attachment.name} ({len(content)} bytes)")
                
            except Exception as e:
                logger.error(f"❌ Failed to download {attachment.name}: {e}")
                result = {
                    'attachment': attachment,
                    'url': download_url,
                    'file_path': None,
                    'status': 'failed',
                    'error': str(e)
                }
            
            results.append(result)
            
            # Add delay between downloads
            await self.http_client.add_delay()
        
        return results
    
    def _generate_material_filename(self, attachment: AttachmentInfo) -> str:
        """
        Generate a safe filename for course material.
        
        Args:
            attachment: Attachment info
            
        Returns:
            Safe filename for the material
        """
        if attachment.name:
            # Use the original name if available
            filename = attachment.name
        else:
            # Fallback: generate from key/id
            key = attachment.key or attachment.id or "unknown"
            filename = f"course_material_{key}.pdf"
        
        # Clean filename for filesystem safety
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = filename.strip()
        
        # Ensure it has an extension
        if '.' not in filename:
            filename += '.pdf'
        
        return filename