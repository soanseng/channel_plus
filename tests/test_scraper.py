"""
Tests for Channel Plus scraper.
"""

import pytest
from unittest.mock import AsyncMock, Mock

from channel_plus.core.scraper import ChannelPlusScraper
from channel_plus.core.models import DownloadConfig
from channel_plus.utils.http_client import ChannelPlusHTTPClient


class TestChannelPlusScraper:
    """Test ChannelPlusScraper functionality."""
    
    @pytest.fixture
    def mock_http_client(self):
        """Create a mock HTTP client."""
        return AsyncMock(spec=ChannelPlusHTTPClient)
    
    @pytest.fixture
    def scraper(self, mock_http_client):
        """Create a scraper with mock HTTP client."""
        return ChannelPlusScraper(mock_http_client)
    
    def test_extract_course_id(self, scraper):
        """Test course ID extraction from URLs."""
        # Valid URL
        url = "https://channelplus.ner.gov.tw/viewalllang/390"
        assert scraper._extract_course_id(url) == 390
        
        # URL with parameters
        url = "https://channelplus.ner.gov.tw/viewalllang/123?page=1"
        assert scraper._extract_course_id(url) == 123
        
        # Invalid URL
        url = "https://example.com/invalid"
        assert scraper._extract_course_id(url) is None
    
    @pytest.mark.asyncio
    async def test_extract_episodes_from_page(self, scraper, mock_http_client):
        """Test extracting episodes from a page."""
        # Mock HTML content with JSON data
        mock_html = '''
        <html>
        <body>
        <script>
        window.__PRELOADED_STATE__ = {
            "reducers": {
                "languageEpisode": {
                    "status": "success",
                    "updated": false,
                    "created": false,
                    "deleted": false,
                    "languageId": null,
                    "count": 1,
                    "data": [
                        {
                            "onShelf": true,
                            "guest": [],
                            "audio": {
                                "path": "",
                                "duration": 1589.707755,
                                "from": "audio",
                                "sn": 47226,
                                "key": "test-audio-key",
                                "download": false,
                                "name": "test-audio.mp3"
                            },
                            "image": {"key": "test-image-key"},
                            "keyword": [],
                            "album": [],
                            "attachment": [],
                            "like": 9,
                            "view": 5189,
                            "verify": true,
                            "updateMember": {"sn": 21, "name": "Test User"},
                            "_id": 38199,
                            "programSn": 390,
                            "releaseDate": "2016/10/17 00:00:00",
                            "part": 1,
                            "name": "Test Episode",
                            "createdAt": "2016/08/08 18:21:32",
                            "updateAt": "2025/05/19 16:21:14",
                            "__v": 0
                        }
                    ]
                }
            }
        }
        </script>
        </body>
        </html>
        '''
        
        mock_http_client.get_text.return_value = mock_html
        
        episodes = await scraper.extract_episodes_from_page(390, 1)
        
        assert len(episodes) == 1
        episode = episodes[0]
        assert episode.id == 38199
        assert episode.part == 1
        assert episode.name == "Test Episode"
        assert episode.audio.key == "test-audio-key"
        assert episode.audio.name == "test-audio.mp3"
    
    @pytest.mark.asyncio
    async def test_extract_episodes_no_json(self, scraper, mock_http_client):
        """Test handling pages without JSON data."""
        mock_html = '<html><body>No JSON data here</body></html>'
        mock_http_client.get_text.return_value = mock_html
        
        episodes = await scraper.extract_episodes_from_page(390, 1)
        
        assert episodes == []
    
    @pytest.mark.asyncio
    async def test_validate_course_url_valid(self, scraper, mock_http_client):
        """Test validating a valid course URL."""
        # Mock successful response with episodes
        mock_html = '''
        <script>
        window.__PRELOADED_STATE__ = {
            "reducers": {
                "languageEpisode": {
                    "status": "success",
                    "updated": false,
                    "created": false,
                    "deleted": false,
                    "count": 1,
                    "data": [
                        {
                            "onShelf": true,
                            "guest": [],
                            "audio": {
                                "path": "",
                                "duration": 1589.707755,
                                "from": "audio",
                                "sn": 47226,
                                "key": "test-audio-key",
                                "download": false,
                                "name": "test-audio.mp3"
                            },
                            "_id": 38199,
                            "programSn": 390,
                            "releaseDate": "2016/10/17 00:00:00",
                            "part": 1,
                            "name": "Test Episode",
                            "createdAt": "2016/08/08 18:21:32",
                            "updateAt": "2025/05/19 16:21:14",
                            "__v": 0
                        }
                    ]
                }
            }
        }
        </script>
        '''
        
        mock_http_client.get_text.return_value = mock_html
        
        url = "https://channelplus.ner.gov.tw/viewalllang/390"
        is_valid = await scraper.validate_course_url(url)
        
        assert is_valid is True
    
    @pytest.mark.asyncio
    async def test_validate_course_url_invalid(self, scraper, mock_http_client):
        """Test validating an invalid course URL."""
        # Mock response with no episodes
        mock_html = '<html><body>No episodes</body></html>'
        mock_http_client.get_text.return_value = mock_html
        
        url = "https://channelplus.ner.gov.tw/viewalllang/999"
        is_valid = await scraper.validate_course_url(url)
        
        assert is_valid is False
    
    @pytest.mark.asyncio
    async def test_get_all_episodes(self, scraper, mock_http_client, tmp_path):
        """Test getting all episodes in a range."""
        # Mock HTML content for page 1
        mock_html = '''
        <script>
        window.__PRELOADED_STATE__ = {
            "reducers": {
                "languageEpisode": {
                    "status": "success",
                    "updated": false,
                    "created": false,
                    "deleted": false,
                    "count": 2,
                    "data": [
                        {
                            "onShelf": true,
                            "guest": [],
                            "audio": {
                                "path": "",
                                "duration": 1589.707755,
                                "from": "audio",
                                "sn": 47226,
                                "key": "test-audio-key-1",
                                "download": false,
                                "name": "test-audio-1.mp3"
                            },
                            "_id": 38199,
                            "programSn": 390,
                            "releaseDate": "2016/10/17 00:00:00",
                            "part": 1,
                            "name": "Test Episode 1",
                            "createdAt": "2016/08/08 18:21:32",
                            "updateAt": "2025/05/19 16:21:14",
                            "__v": 0
                        },
                        {
                            "onShelf": true,
                            "guest": [],
                            "audio": {
                                "path": "",
                                "duration": 1643.493878,
                                "from": "audio",
                                "sn": 47227,
                                "key": "test-audio-key-2",
                                "download": false,
                                "name": "test-audio-2.mp3"
                            },
                            "_id": 38200,
                            "programSn": 390,
                            "releaseDate": "2016/10/17 00:00:00",
                            "part": 2,
                            "name": "Test Episode 2",
                            "createdAt": "2016/08/08 18:21:32",
                            "updateAt": "2025/05/19 16:21:14",
                            "__v": 0
                        }
                    ]
                }
            }
        }
        </script>
        '''
        
        mock_http_client.get_text.return_value = mock_html
        mock_http_client.add_delay.return_value = None
        
        config = DownloadConfig(
            path=tmp_path,
            link="https://channelplus.ner.gov.tw/viewalllang/390",
            start_episode=1,
            final_episode=2
        )
        
        episodes = await scraper.get_all_episodes(config)
        
        assert len(episodes) == 2
        assert episodes[0].part == 1
        assert episodes[1].part == 2
        assert episodes[0].name == "Test Episode 1"
        assert episodes[1].name == "Test Episode 2"