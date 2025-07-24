"""
Tests for Channel Plus data models.
"""

import pytest
from pathlib import Path

from channel_plus.core.models import (
    AudioInfo, Episode, DownloadConfig, DownloadProgress
)


class TestAudioInfo:
    """Test AudioInfo model."""
    
    def test_audio_info_creation(self):
        """Test creating AudioInfo with valid data."""
        audio = AudioInfo(
            key="test-key-123",
            name="test-audio.mp3",
            duration=120.5,
            sn=12345,
            download=True
        )
        
        assert audio.key == "test-key-123"
        assert audio.name == "test-audio.mp3"
        assert audio.duration == 120.5
        assert audio.sn == 12345
        assert audio.download is True


class TestEpisode:
    """Test Episode model."""
    
    def test_episode_creation(self):
        """Test creating Episode with valid data."""
        audio = AudioInfo(
            key="test-key-123",
            name="test-audio.mp3",
            duration=120.5,
            sn=12345
        )
        
        episode_data = {
            "_id": 1001,
            "programSn": 390,
            "part": 1,
            "name": "Test Episode",
            "releaseDate": "2024-01-01 00:00:00",
            "onShelf": True,
            "audio": audio.dict(),
            "createdAt": "2024-01-01 12:00:00",
            "updateAt": "2024-01-01 12:00:00"
        }
        
        episode = Episode(**episode_data)
        
        assert episode.id == 1001
        assert episode.program_sn == 390
        assert episode.part == 1
        assert episode.name == "Test Episode"
        assert episode.on_shelf is True
        assert episode.audio.key == "test-key-123"
    
    def test_audio_url_property(self):
        """Test audio_url property generates correct URL."""
        audio = AudioInfo(
            key="test-key-123",
            name="test-audio.mp3",
            duration=120.5,
            sn=12345
        )
        
        episode_data = {
            "_id": 1001,
            "programSn": 390,
            "part": 1,
            "name": "Test Episode",
            "releaseDate": "2024-01-01 00:00:00",
            "onShelf": True,
            "audio": audio.dict(),
            "createdAt": "2024-01-01 12:00:00",
            "updateAt": "2024-01-01 12:00:00"
        }
        
        episode = Episode(**episode_data)
        expected_url = "https://channelplus.ner.gov.tw/api/audio/test-key-123"
        
        assert episode.audio_url == expected_url
    
    def test_safe_filename_property(self):
        """Test safe_filename property."""
        audio = AudioInfo(
            key="test-key-123",
            name="test-audio.mp3",
            duration=120.5,
            sn=12345
        )
        
        episode_data = {
            "_id": 1001,
            "programSn": 390,
            "part": 1,
            "name": "Test Episode",
            "releaseDate": "2024-01-01 00:00:00",
            "onShelf": True,
            "audio": audio.dict(),
            "createdAt": "2024-01-01 12:00:00",
            "updateAt": "2024-01-01 12:00:00"
        }
        
        episode = Episode(**episode_data)
        
        # Should use the audio name if available
        assert episode.safe_filename == "test-audio.mp3"
        
        # Test with empty audio name
        audio.name = ""
        episode_data["audio"] = audio.dict()
        episode = Episode(**episode_data)
        
        # Should generate filename from episode info
        assert episode.safe_filename == "00001_Test Episode.mp3"


class TestDownloadConfig:
    """Test DownloadConfig model."""
    
    def test_download_config_creation(self, tmp_path):
        """Test creating DownloadConfig with valid data."""
        config = DownloadConfig(
            path=tmp_path,
            link="https://channelplus.ner.gov.tw/viewalllang/390",
            start_episode=1,
            final_episode=10
        )
        
        assert config.path == tmp_path
        assert config.link == "https://channelplus.ner.gov.tw/viewalllang/390"
        assert config.start_episode == 1
        assert config.final_episode == 10
        assert config.concurrent_downloads == 3  # default
    
    def test_pagination_properties(self, tmp_path):
        """Test pagination calculation properties."""
        config = DownloadConfig(
            path=tmp_path,
            link="https://channelplus.ner.gov.tw/viewalllang/390",
            start_episode=15,
            final_episode=25
        )
        
        # Episodes 15-25 should be on pages 2-3 (10 episodes per page)
        assert config.start_page == 2
        assert config.final_page == 3
        assert config.total_episodes == 11
    
    def test_validation_errors(self, tmp_path):
        """Test validation errors."""
        # Test final episode before start episode
        with pytest.raises(ValueError, match="Final episode must be >= start episode"):
            DownloadConfig(
                path=tmp_path,
                link="https://channelplus.ner.gov.tw/viewalllang/390",
                start_episode=10,
                final_episode=5
            )
        
        # Test negative episode numbers
        with pytest.raises(ValueError, match="Episode numbers must be positive"):
            DownloadConfig(
                path=tmp_path,
                link="https://channelplus.ner.gov.tw/viewalllang/390",
                start_episode=0,
                final_episode=10
            )


class TestDownloadProgress:
    """Test DownloadProgress model."""
    
    def test_progress_calculation(self):
        """Test progress percentage calculation."""
        audio = AudioInfo(
            key="test-key-123",
            name="test-audio.mp3",
            duration=120.5,
            sn=12345
        )
        
        episode_data = {
            "_id": 1001,
            "programSn": 390,
            "part": 1,
            "name": "Test Episode",
            "releaseDate": "2024-01-01 00:00:00",
            "onShelf": True,
            "audio": audio.dict(),
            "createdAt": "2024-01-01 12:00:00",
            "updateAt": "2024-01-01 12:00:00"
        }
        
        episode = Episode(**episode_data)
        
        progress = DownloadProgress(
            episode=episode,
            bytes_downloaded=5000,
            total_bytes=10000
        )
        
        assert progress.progress_percent == 50.0
        
        # Test with no total bytes
        progress.total_bytes = None
        assert progress.progress_percent == 0.0