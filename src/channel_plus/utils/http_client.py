"""
HTTP client with session management for Channel Plus downloader.

Provides async HTTP client with proper headers, retries, and session management
for accessing the Channel Plus website and downloading audio files.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from pathlib import Path

import aiohttp
from aiohttp import ClientSession, ClientTimeout, ClientResponse


logger = logging.getLogger(__name__)


class ChannelPlusHTTPClient:
    """Async HTTP client optimized for Channel Plus website."""
    
    def __init__(
        self,
        timeout: int = 300,
        retry_attempts: int = 3,
        delay_between_requests: float = 1.0,
        max_concurrent: int = 10
    ):
        """
        Initialize HTTP client with configuration.
        
        Args:
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts for failed requests
            delay_between_requests: Delay between requests in seconds
            max_concurrent: Maximum concurrent connections
        """
        self.timeout = ClientTimeout(total=timeout)
        self.retry_attempts = retry_attempts
        self.delay_between_requests = delay_between_requests
        self.max_concurrent = max_concurrent
        
        # Session will be created when needed
        self._session: Optional[ClientSession] = None
        self._semaphore: Optional[asyncio.Semaphore] = None
        
        # Default headers that work with Channel Plus
        self.default_headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,zh-TW;q=0.8,zh;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def _ensure_session(self):
        """Ensure session and semaphore are created."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=self.max_concurrent,
                limit_per_host=self.max_concurrent,
                ttl_dns_cache=300,
                use_dns_cache=True,
            )
            
            self._session = ClientSession(
                connector=connector,
                timeout=self.timeout,
                headers=self.default_headers
            )
        
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent)
    
    async def close(self):
        """Close the HTTP session and clean up resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
        self._semaphore = None
    
    async def _make_request_with_retry(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> ClientResponse:
        """
        Make HTTP request with retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            headers: Additional headers
            **kwargs: Additional arguments for aiohttp request
            
        Returns:
            aiohttp ClientResponse
            
        Raises:
            aiohttp.ClientError: After all retry attempts fail
        """
        await self._ensure_session()
        
        # Merge headers
        request_headers = self.default_headers.copy()
        if headers:
            request_headers.update(headers)
        
        last_exception = None
        
        for attempt in range(self.retry_attempts):
            try:
                async with self._semaphore:  # Limit concurrent requests
                    logger.debug(f"Making {method} request to {url} (attempt {attempt + 1})")
                    
                    response = await self._session.request(
                        method, url, headers=request_headers, **kwargs
                    )
                    
                    # Check if response is successful
                    if response.status == 200:
                        return response
                    elif response.status in (429, 502, 503, 504):
                        # Rate limited or server error - retry with backoff
                        logger.warning(f"Request failed with status {response.status}, retrying...")
                        response.close()  # Close the response
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    else:
                        # Other HTTP errors - log and continue
                        logger.error(f"HTTP {response.status} for {url}")
                        response.close()  # Close the response
                        response.raise_for_status()
                            
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_exception = e
                logger.warning(f"Request attempt {attempt + 1} failed: {e}")
                
                if attempt < self.retry_attempts - 1:
                    # Wait before retry with exponential backoff
                    wait_time = min(2 ** attempt, 30)  # Cap at 30 seconds
                    logger.info(f"Waiting {wait_time} seconds before retry...")
                    await asyncio.sleep(wait_time)
                    continue
        
        # All attempts failed
        logger.error(f"All {self.retry_attempts} attempts failed for {url}")
        if last_exception:
            raise last_exception
        else:
            raise aiohttp.ClientError(f"Failed to fetch {url} after {self.retry_attempts} attempts")
    
    async def get_text(self, url: str, headers: Optional[Dict[str, str]] = None) -> str:
        """
        Get text content from URL.
        
        Args:
            url: URL to fetch
            headers: Additional headers
            
        Returns:
            Response text content
        """
        # Add referer for Channel Plus pages
        request_headers = {}
        if headers:
            request_headers.update(headers)
        
        if 'channelplus.ner.gov.tw' in url and 'Referer' not in request_headers:
            request_headers['Referer'] = 'https://channelplus.ner.gov.tw/'
        
        response = await self._make_request_with_retry('GET', url, headers=request_headers)
        try:
            text = await response.text()
            logger.debug(f"Retrieved {len(text)} characters from {url}")
            return text
        finally:
            response.close()
    
    async def download_file(
        self,
        url: str,
        file_path: Path,
        headers: Optional[Dict[str, str]] = None,
        progress_callback: Optional[callable] = None
    ) -> bool:
        """
        Download a file from URL to local path.
        
        Args:
            url: URL to download
            file_path: Local path to save file
            headers: Additional headers
            progress_callback: Optional callback for progress updates (bytes_downloaded, total_bytes)
            
        Returns:
            True if download successful, False otherwise
        """
        try:
            # Prepare headers for audio download
            request_headers = {
                'Accept': 'audio/mpeg,audio/*,*/*',
                'Accept-Encoding': 'identity',  # Don't compress audio
            }
            if headers:
                request_headers.update(headers)
            
            if 'channelplus.ner.gov.tw' in url and 'Referer' not in request_headers:
                request_headers['Referer'] = 'https://channelplus.ner.gov.tw/'
            
            response = await self._make_request_with_retry('GET', url, headers=request_headers)
            
            try:
                # Get file size if available
                total_size = response.headers.get('Content-Length')
                total_bytes = int(total_size) if total_size else None
                
                logger.info(f"Downloading {url} to {file_path}")
                if total_bytes:
                    logger.info(f"File size: {total_bytes:,} bytes")
                
                # Ensure parent directory exists
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                bytes_downloaded = 0
                
                # Download file in chunks
                with open(file_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):  # 8KB chunks
                        f.write(chunk)
                        bytes_downloaded += len(chunk)
                        
                        # Call progress callback if provided
                        if progress_callback:
                            progress_callback(bytes_downloaded, total_bytes)
                
                logger.info(f"Successfully downloaded {bytes_downloaded:,} bytes to {file_path}")
                return True
            finally:
                response.close()
                
        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            # Clean up partial file
            if file_path.exists():
                file_path.unlink()
            return False
    
    async def get_json(self, url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Get JSON content from URL.
        
        Args:
            url: URL to fetch
            headers: Additional headers
            
        Returns:
            Parsed JSON response
        """
        response = await self._make_request_with_retry('GET', url, headers=headers)
        try:
            json_data = await response.json()
            logger.debug(f"Retrieved JSON data from {url}")
            return json_data
        finally:
            response.close()
    
    async def get_content(self, url: str, headers: Optional[Dict[str, str]] = None) -> bytes:
        """
        Get binary content from URL.
        
        Args:
            url: URL to fetch
            headers: Additional headers
            
        Returns:
            Binary content as bytes
        """
        # Add referer for Channel Plus pages
        request_headers = {}
        if headers:
            request_headers.update(headers)
        
        if 'channelplus.ner.gov.tw' in url and 'Referer' not in request_headers:
            request_headers['Referer'] = 'https://channelplus.ner.gov.tw/'
        
        response = await self._make_request_with_retry('GET', url, headers=request_headers)
        try:
            content = await response.read()
            logger.debug(f"Retrieved {len(content)} bytes from {url}")
            return content
        finally:
            response.close()
    
    def add_delay(self):
        """Add configured delay between requests."""
        return asyncio.sleep(self.delay_between_requests)