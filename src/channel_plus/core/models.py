"""
Data models for Channel Plus downloader using Pydantic.

These models define the structure of data extracted from the Channel Plus website
and configuration options for the downloader.
"""

from pathlib import Path
from typing import List, Optional
from datetime import datetime

from pydantic import BaseModel, Field, validator


class AudioInfo(BaseModel):
    """Information about an audio file from Channel Plus."""
    
    key: str = Field(..., description="Unique key for the audio file")
    name: str = Field(..., description="Original filename of the audio")
    duration: float = Field(..., description="Duration in seconds")
    sn: int = Field(..., description="Serial number of the audio")
    download: bool = Field(default=False, description="Download flag (metadata only)")
    path: str = Field(default="", description="Original path (usually empty)")
    from_source: str = Field(default="audio", alias="from", description="Source type")


class ImageInfo(BaseModel):
    """Information about an image associated with an episode."""
    
    key: str = Field(..., description="Unique key for the image")


class UpdateMember(BaseModel):
    """Information about the member who updated the episode."""
    
    sn: int = Field(..., description="Member serial number")
    name: str = Field(..., description="Member name")


class Episode(BaseModel):
    """Complete episode information from Channel Plus."""
    
    id: int = Field(..., alias="_id", description="Episode ID")
    program_sn: int = Field(..., alias="programSn", description="Program serial number")
    part: int = Field(..., description="Episode part number")
    name: str = Field(..., description="Episode title")
    release_date: str = Field(..., alias="releaseDate", description="Release date string")
    on_shelf: bool = Field(..., alias="onShelf", description="Whether episode is available")
    verify: bool = Field(default=True, description="Verification status")
    
    # Related objects
    audio: AudioInfo = Field(..., description="Audio file information")
    image: Optional[ImageInfo] = Field(None, description="Associated image")
    update_member: Optional[UpdateMember] = Field(None, alias="updateMember", description="Last update member")
    
    # Metadata
    like: int = Field(default=0, description="Number of likes")
    view: int = Field(default=0, description="Number of views")
    guest: List[str] = Field(default_factory=list, description="Guest list")
    keyword: List[str] = Field(default_factory=list, description="Keywords")
    album: List[str] = Field(default_factory=list, description="Album information")
    attachment: List[str] = Field(default_factory=list, description="Attachments")
    
    # Timestamps
    created_at: str = Field(..., alias="createdAt", description="Creation timestamp")
    update_at: str = Field(..., alias="updateAt", description="Update timestamp")
    version: int = Field(default=0, alias="__v", description="Version number")

    @validator('release_date', 'created_at', 'update_at')
    def validate_date_format(cls, v):
        """Validate date strings are in expected format."""
        if not v or not isinstance(v, str):
            return v
        # Accept various date formats from the API
        return v

    @property
    def audio_url(self) -> str:
        """Generate the full audio download URL."""
        return f"https://channelplus.ner.gov.tw/api/audio/{self.audio.key}"
    
    @property
    def safe_filename(self) -> str:
        """Generate a safe filename for downloading."""
        # Use the original audio name if available, otherwise construct one
        if self.audio.name and self.audio.name.strip():
            return self.audio.name
        
        # Fallback: construct filename from episode info
        safe_name = f"{self.part:05d}_{self.name.replace('/', '_').replace('\\', '_')}.mp3"
        return safe_name


class LanguageEpisodeData(BaseModel):
    """Container for language episode data from the API response."""
    
    status: str = Field(..., description="API response status")
    updated: bool = Field(..., description="Whether data was updated")
    created: bool = Field(..., description="Whether data was created")
    deleted: bool = Field(..., description="Whether data was deleted")
    language_id: Optional[str] = Field(None, alias="languageId", description="Language ID")
    count: int = Field(..., description="Total count of episodes")
    data: List[Episode] = Field(..., description="List of episodes")


class DownloadConfig(BaseModel):
    """Configuration for the Channel Plus downloader."""
    
    path: Path = Field(..., description="Download directory path")
    link: str = Field(..., description="Channel Plus course URL")
    start_episode: int = Field(..., description="Starting episode number")
    final_episode: int = Field(..., description="Final episode number")
    
    # Optional settings
    concurrent_downloads: int = Field(default=3, description="Number of concurrent downloads")
    timeout: int = Field(default=300, description="Request timeout in seconds")
    retry_attempts: int = Field(default=3, description="Number of retry attempts")
    delay_between_requests: float = Field(default=1.0, description="Delay between requests in seconds")
    
    @validator('path')
    def validate_path(cls, v):
        """Ensure path exists or can be created."""
        if isinstance(v, str):
            v = Path(v)
        
        # Create directory if it doesn't exist
        v.mkdir(parents=True, exist_ok=True)
        return v
    
    @validator('start_episode', 'final_episode')
    def validate_episode_numbers(cls, v):
        """Ensure episode numbers are positive."""
        if v <= 0:
            raise ValueError("Episode numbers must be positive")
        return v
    
    @validator('final_episode')
    def validate_episode_range(cls, v, values):
        """Ensure final episode is not before start episode."""
        if 'start_episode' in values and v < values['start_episode']:
            raise ValueError("Final episode must be >= start episode")
        return v
    
    @validator('concurrent_downloads')
    def validate_concurrent_downloads(cls, v):
        """Ensure reasonable concurrency limits."""
        if v < 1:
            raise ValueError("Must have at least 1 concurrent download")
        if v > 10:
            raise ValueError("Too many concurrent downloads (max 10)")
        return v
    
    @property
    def start_page(self) -> int:
        """Calculate the starting page number for pagination."""
        return (self.start_episode - 1) // 10 + 1
    
    @property
    def final_page(self) -> int:
        """Calculate the final page number for pagination."""
        return (self.final_episode - 1) // 10 + 1
    
    @property
    def total_episodes(self) -> int:
        """Calculate total number of episodes to download."""
        return self.final_episode - self.start_episode + 1


class DownloadProgress(BaseModel):
    """Progress information for a download operation."""
    
    episode: Episode = Field(..., description="Episode being downloaded")
    bytes_downloaded: int = Field(default=0, description="Bytes downloaded so far")
    total_bytes: Optional[int] = Field(None, description="Total bytes to download")
    start_time: datetime = Field(default_factory=datetime.now, description="Download start time")
    status: str = Field(default="pending", description="Download status")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    
    @property
    def progress_percent(self) -> float:
        """Calculate download progress as percentage."""
        if not self.total_bytes or self.total_bytes == 0:
            return 0.0
        return (self.bytes_downloaded / self.total_bytes) * 100
    
    @property
    def elapsed_time(self) -> float:
        """Calculate elapsed time in seconds."""
        return (datetime.now() - self.start_time).total_seconds()
    
    @property
    def download_speed(self) -> float:
        """Calculate download speed in bytes per second."""
        elapsed = self.elapsed_time
        if elapsed == 0:
            return 0.0
        return self.bytes_downloaded / elapsed