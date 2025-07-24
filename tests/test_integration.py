"""
Integration tests for Channel Plus downloader.

These tests verify that the components work together correctly.
They may make real HTTP requests to test against the actual website.
"""

import pytest
import asyncio
from pathlib import Path

from channel_plus.core.models import DownloadConfig
from channel_plus.core.scraper import ChannelPlusScraper
from channel_plus.utils.http_client import ChannelPlusHTTPClient


class TestIntegration:
    """Integration tests for the complete system."""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_real_course_validation(self):
        """Test validating a real course on the Channel Plus website."""
        async with ChannelPlusHTTPClient() as http_client:
            scraper = ChannelPlusScraper(http_client)
            
            # Test with a known good course URL
            url = "https://channelplus.ner.gov.tw/viewalllang/390"
            is_valid = await scraper.validate_course_url(url)
            
            assert is_valid is True
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_real_episode_extraction(self):
        """Test extracting episodes from the real website."""
        async with ChannelPlusHTTPClient() as http_client:
            scraper = ChannelPlusScraper(http_client)
            
            # Extract episodes from the first page
            episodes = await scraper.extract_episodes_from_page(390, 1)
            
            assert len(episodes) > 0
            
            # Check that episodes have expected structure
            episode = episodes[0]
            assert hasattr(episode, 'id')
            assert hasattr(episode, 'part')
            assert hasattr(episode, 'name')
            assert hasattr(episode, 'audio')
            assert hasattr(episode.audio, 'key')
            assert hasattr(episode.audio, 'name')
            
            # Check that audio URL is correct
            expected_base = "https://channelplus.ner.gov.tw/api/audio/"
            assert episode.audio_url.startswith(expected_base)
    
    @pytest.mark.asyncio
    @pytest.mark.integration  
    async def test_real_course_info(self):
        """Test getting course information from the real website."""
        async with ChannelPlusHTTPClient() as http_client:
            scraper = ChannelPlusScraper(http_client)
            
            url = "https://channelplus.ner.gov.tw/viewalllang/390"
            course_info = await scraper.get_course_info(url)
            
            assert course_info['course_id'] == 390
            assert course_info['episodes_found'] > 0
            assert 'sample_episode' in course_info
            assert course_info['sample_episode'] is not None
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_episode_range_collection(self, tmp_path):
        """Test collecting episodes in a specific range."""
        async with ChannelPlusHTTPClient() as http_client:
            scraper = ChannelPlusScraper(http_client)
            
            config = DownloadConfig(
                path=tmp_path,
                link="https://channelplus.ner.gov.tw/viewalllang/390",
                start_episode=1,
                final_episode=3
            )
            
            episodes = await scraper.get_all_episodes(config)
            
            assert len(episodes) == 3
            
            # Episodes should be in order
            assert episodes[0].part == 1
            assert episodes[1].part == 2  
            assert episodes[2].part == 3
            
            # All episodes should have valid audio URLs
            for episode in episodes:
                assert episode.audio_url.startswith("https://channelplus.ner.gov.tw/api/audio/")
                assert len(episode.audio.key) > 0
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_audio_url_accessibility(self):
        """Test that audio URLs are accessible (may be slow)."""
        async with ChannelPlusHTTPClient(timeout=30) as http_client:
            scraper = ChannelPlusScraper(http_client)
            
            # Get a sample episode
            episodes = await scraper.extract_episodes_from_page(390, 1)
            assert len(episodes) > 0
            
            episode = episodes[0]
            
            # Test that we can make a HEAD request to the audio URL
            # This doesn't download the file but checks if it's accessible
            try:
                # Try to get the first few bytes to verify the URL works
                response = await http_client._make_request_with_retry(
                    'HEAD', episode.audio_url
                )
                # Check that we get a successful response
                assert response.status == 200
                response.close()
            except Exception as e:
                pytest.skip(f"Audio URL not accessible: {e}")


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Custom markers for different test categories
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (may make HTTP requests)"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )