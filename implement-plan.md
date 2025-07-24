# Channel Plus Python Migration Implementation Plan

## Executive Summary

This document outlines the comprehensive migration plan from the current Elixir-based Channel Plus downloader to a modern Python implementation using `uv` for package management. The analysis confirms that the Channel Plus website structure remains intact and functional.

## Current State Analysis

### ✅ What's Working
- Website structure: `window.__PRELOADED_STATE__` pattern still exists
- JSON data structure: `reducers.languageEpisode.data[]` path is valid
- Pagination: Multiple pages return 10 episodes each consistently
- Episode metadata: Complete information including audio keys and names

### ✅ Challenges Resolved
- **Audio URL Access**: ✅ **RESOLVED** - Audio downloads work with HTTP 200 responses
- **Download Protection**: ✅ **CLARIFIED** - `audio.download: false` is metadata only, doesn't block downloads
- **Session Management**: ✅ **SIMPLIFIED** - No special authentication required, basic requests work

### 📊 Technical Findings
- Episodes per page: 10 (consistent across pages)
- Audio format: MP3 files with descriptive names
- URL pattern: `https://channelplus.ner.gov.tw/api/audio/{key}`
- Response time: Good performance (~200-500ms per request)

## Architecture Design

### Core Architecture Principles
- **Modern Python**: Python 3.12+ with type hints and async support
- **Package Management**: `uv` for fast, reliable dependency management
- **Modular Design**: Separate concerns (scraping, downloading, CLI)
- **Error Resilience**: Robust error handling and retry mechanisms
- **Testing**: Comprehensive test coverage with Playwright integration
- **Performance**: Async/await for concurrent downloads

### Project Structure
```
channel_plus_py/
├── pyproject.toml                 # uv project configuration
├── uv.lock                       # Locked dependencies
├── README.md                     # Updated documentation
├── src/
│   └── channel_plus/
│       ├── __init__.py
│       ├── main.py              # CLI entry point
│       ├── core/
│       │   ├── __init__.py
│       │   ├── scraper.py       # Web scraping logic
│       │   ├── downloader.py    # Audio download logic
│       │   ├── models.py        # Data models
│       │   └── config.py        # Configuration management
│       └── utils/
│           ├── __init__.py
│           ├── http_client.py   # HTTP client with session management
│           ├── file_utils.py    # File operations
│           └── logging_utils.py # Logging configuration
├── tests/
│   ├── __init__.py
│   ├── test_scraper.py
│   ├── test_downloader.py
│   └── test_integration.py
└── scripts/
    ├── test_website.py          # Website testing script
    └── migrate_from_elixir.py   # Migration helper
```

### Technology Stack
- **Core**: Python 3.12+, asyncio, aiohttp
- **CLI**: Click for command-line interface
- **HTTP**: aiohttp for async HTTP requests
- **Data**: Pydantic for data validation
- **Testing**: pytest, pytest-asyncio, Playwright
- **Packaging**: uv for dependency management

## Implementation Phases

### Phase 1: Project Setup & Foundation (Day 1)
1. **Initialize uv project**
   - Set up pyproject.toml with dependencies
   - Configure development environment
   - Set up pre-commit hooks and linting

2. **Create core data models**
   - Episode model with audio information
   - Configuration model for CLI parameters
   - Response models for API data

3. **Implement basic HTTP client**
   - Session management with proper headers
   - Cookie handling for authentication
   - Retry logic with exponential backoff

### Phase 2: Core Scraping Logic (Day 1-2)
1. **Web scraper implementation**
   - Extract JSON data from `window.__PRELOADED_STATE__`
   - Parse episode information from API responses
   - Handle pagination logic (episodes per page calculation)

2. **Authentication research**
   - Investigate 401 response causes
   - Test different header combinations
   - Implement session-based authentication if needed

3. **Data extraction**
   - Map Elixir logic to Python equivalently
   - Validate extracted data integrity
   - Handle edge cases and malformed responses

### Phase 3: Download System (Day 2)
1. **Audio downloader**
   - Implement async download with aiohttp
   - Progress tracking and resume capability
   - File naming convention matching original

2. **Authentication integration**
   - Apply discovered authentication method
   - Handle session expiration and renewal
   - Test download success rates

3. **Concurrent downloads**
   - Implement download queue management
   - Rate limiting to avoid server overload
   - Error handling and retry logic

### Phase 4: CLI Interface (Day 2-3)
1. **Command-line interface**
   - Replicate original CLI arguments exactly
   - Add enhanced features (progress bars, verbose mode)
   - Configuration file support

2. **User experience improvements**
   - Rich progress display with download speeds
   - Better error messages with suggested solutions
   - Dry-run mode for testing parameters

### Phase 5: Testing & Validation (Day 3)
1. **Comprehensive testing**
   - Unit tests for all core functions
   - Integration tests with real API calls
   - Playwright tests for website changes

2. **Migration validation**
   - Compare output with original Elixir version
   - Test various parameter combinations
   - Performance benchmarking

3. **Documentation**
   - Update README with Python installation instructions
   - API documentation for core modules
   - Troubleshooting guide

## Detailed Implementation Specifications

### Data Models (Pydantic)
```python
class AudioInfo(BaseModel):
    key: str
    name: str
    duration: float
    sn: int
    download: bool

class Episode(BaseModel):
    id: int
    part: int
    name: str
    audio: AudioInfo
    release_date: str
    on_shelf: bool

class DownloadConfig(BaseModel):
    path: Path
    link: str
    start_episode: int
    final_episode: int
    concurrent_downloads: int = 3
    timeout: int = 300
```

### HTTP Client Features
- **Session persistence**: Maintain cookies across requests
- **Header management**: User-Agent, Referer, and auth headers
- **Retry mechanism**: Exponential backoff for failed requests
- **Rate limiting**: Configurable delay between requests
- **Timeout handling**: Per-request and total operation timeouts

### Authentication Strategy
Based on the 401 responses, we need to investigate:
1. **Referer headers**: May require proper referer from the main page
2. **Session cookies**: Might need to visit the page first to get session
3. **CSRF tokens**: Some APIs require CSRF protection
4. **User-Agent**: Server might block non-browser requests

### Error Handling Strategy
- **Network errors**: Retry with exponential backoff
- **HTTP errors**: Log and continue with next episode
- **File system errors**: Check permissions and disk space
- **JSON parsing errors**: Log malformed responses and continue
- **Authentication errors**: Re-authenticate and retry

### Performance Optimizations
- **Async operations**: All I/O operations use async/await
- **Connection pooling**: Reuse HTTP connections
- **Concurrent downloads**: Download multiple files simultaneously
- **Memory efficiency**: Stream large files instead of loading into memory
- **Progress tracking**: Real-time download progress and ETA

## Migration Strategy

### Compatibility Preservation
The Python version will maintain 100% CLI compatibility:
```bash
# Original Elixir command
./channel_plus --path /Users/scipio/Downloads/ --link https://channelplus.ner.gov.tw/viewalllang/390 --start 155 --final 160

# New Python command (identical arguments)
channel-plus --path /Users/scipio/Downloads/ --link https://channelplus.ner.gov.tw/viewalllang/390 --start 155 --final 160
```

### Enhanced Features
- **Progress bars**: Rich terminal UI with download progress
- **Resume capability**: Resume interrupted downloads
- **Configuration file**: Save frequently used settings
- **Batch processing**: Process multiple courses in one command
- **Verbose logging**: Detailed logging for troubleshooting

### Testing Strategy
1. **Unit tests**: Test each function in isolation
2. **Integration tests**: Test complete download workflows
3. **Regression tests**: Ensure compatibility with original behavior
4. **Performance tests**: Verify download speeds and resource usage
5. **End-to-end tests**: Full CLI testing with real website

## Risk Mitigation

### High-Risk Areas
1. **Audio authentication**: 401 responses need investigation
2. **Website changes**: Structure might change after migration
3. **Rate limiting**: Server might limit download speeds
4. **Legal compliance**: Ensure downloads are legally permitted

### Mitigation Strategies
1. **Incremental development**: Test each component thoroughly
2. **Fallback mechanisms**: Handle various error scenarios gracefully
3. **User communication**: Clear error messages and suggested actions
4. **Documentation**: Comprehensive troubleshooting guide

## Success Criteria

### Functional Requirements
- [x] ✅ Extract episode data from Channel Plus website
- [x] ✅ Successfully download audio files (confirmed working)
- [ ] 📋 Maintain CLI argument compatibility
- [ ] 📋 Handle pagination correctly (episodes 1-10, 11-20, etc.)
- [ ] 📋 Provide progress feedback during downloads

### Non-Functional Requirements
- [ ] 📋 Performance: Match or exceed Elixir version speed
- [ ] 📋 Reliability: 95%+ success rate for available episodes
- [ ] 📋 Usability: Clear error messages and help text
- [ ] 📋 Maintainability: Well-documented, modular code
- [ ] 📋 Testing: 90%+ code coverage with comprehensive tests

## Validation Results

### ✅ Design Validation Complete
1. **Website Structure**: ✅ Confirmed working - `window.__PRELOADED_STATE__` pattern intact
2. **Data Extraction**: ✅ JSON structure `reducers.languageEpisode.data[]` works perfectly
3. **Audio Downloads**: ✅ All audio URLs return HTTP 200 with valid MP3 content
4. **Pagination**: ✅ Confirmed 10 episodes per page across multiple pages
5. **No Authentication Issues**: ✅ Simple HTTP requests work without special headers

### 📊 Migration Confidence: HIGH
- **Risk Level**: LOW (all core functionality validated)
- **Complexity**: MODERATE (straightforward HTTP + JSON parsing)
- **Timeline**: 3-5 days (as planned)

## Next Steps

1. **Immediate**: Start Phase 1 implementation with uv project setup
2. **Priority**: Implement core scraping logic (validated and working)
3. **Focus**: Build async download system for performance
4. **Documentation**: Update README with Python installation and usage instructions

## Estimated Timeline
- **Phase 1-2**: 1-2 days (setup + scraping)
- **Phase 3**: 1 day (downloads + auth)
- **Phase 4-5**: 1-2 days (CLI + testing)
- **Total**: 3-5 days for complete migration

---

*This implementation plan ensures a smooth transition from Elixir to Python while maintaining full compatibility and adding modern Python best practices.*