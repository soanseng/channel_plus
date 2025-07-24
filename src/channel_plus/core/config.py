"""
Configuration management for Channel Plus downloader.
"""

import logging
from pathlib import Path
from typing import Optional


def setup_logging(verbose: bool = False) -> None:
    """
    Set up logging configuration.
    
    Args:
        verbose: Enable verbose logging
    """
    level = logging.DEBUG if verbose else logging.INFO
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Set up console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        handlers=[console_handler],
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Reduce noise from aiohttp
    logging.getLogger('aiohttp').setLevel(logging.WARNING)


class ChannelPlusConfig:
    """Configuration constants for Channel Plus downloader."""
    
    # Base URLs
    BASE_URL = "https://channelplus.ner.gov.tw"
    AUDIO_API_URL = f"{BASE_URL}/api/audio"
    
    # Default settings
    DEFAULT_CONCURRENT_DOWNLOADS = 3
    DEFAULT_TIMEOUT = 300
    DEFAULT_RETRY_ATTEMPTS = 3
    DEFAULT_DELAY_BETWEEN_REQUESTS = 1.0
    
    # Pagination
    EPISODES_PER_PAGE = 10
    
    # File settings
    SUPPORTED_AUDIO_FORMATS = ['.mp3', '.m4a', '.wav']
    MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB per file
    
    @classmethod
    def get_course_url(cls, course_id: int, page: int = 1) -> str:
        """
        Generate course URL for a specific page.
        
        Args:
            course_id: Course ID (e.g., 390)
            page: Page number (1-based)
            
        Returns:
            Full URL for the course page
        """
        return f"{cls.BASE_URL}/viewalllang/{course_id}?page={page}"
    
    @classmethod
    def get_audio_url(cls, audio_key: str) -> str:
        """
        Generate audio download URL.
        
        Args:
            audio_key: Audio file key
            
        Returns:
            Full URL for audio download
        """
        return f"{cls.AUDIO_API_URL}/{audio_key}"