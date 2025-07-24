"""
Web scraper for Channel Plus website.

Extracts episode information from the Channel Plus website by parsing
the JSON data embedded in the page's window.__PRELOADED_STATE__.
"""

import json
import re
import logging
from typing import List, Optional, Dict, Any

from ..core.models import Episode, LanguageEpisodeData, DownloadConfig
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