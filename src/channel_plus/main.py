"""
Main entry point for Channel Plus downloader.

A modern Python implementation of the Channel Plus audio downloader,
providing the same CLI interface as the original Elixir version with
enhanced features like progress bars and better error handling.
"""

import asyncio
import logging
import sys
from pathlib import Path

import click
from rich.console import Console

from .core.models import DownloadConfig
from .core.scraper import ChannelPlusScraper
from .core.downloader import ChannelPlusDownloader
from .core.config import setup_logging
from .utils.http_client import ChannelPlusHTTPClient


console = Console()


@click.command()
@click.option(
    '--path',
    required=True,
    type=click.Path(path_type=Path),
    help='Download path for audio files'
)
@click.option(
    '--link',
    required=True,
    help='Channel Plus course URL (e.g., https://channelplus.ner.gov.tw/viewalllang/390)'
)
@click.option(
    '--start',
    required=True,
    type=int,
    help='Starting episode number'
)
@click.option(
    '--final',
    required=True,
    type=int,
    help='Final episode number'  
)
@click.option(
    '--concurrent',
    default=3,
    type=click.IntRange(1, 10),
    help='Number of concurrent downloads (1-10, default: 3)'
)
@click.option(
    '--timeout',
    default=300,
    type=int,
    help='Request timeout in seconds (default: 300)'
)
@click.option(
    '--retry-attempts',
    default=3,
    type=click.IntRange(1, 10),
    help='Number of retry attempts (default: 3)'
)
@click.option(
    '--delay',
    default=1.0,
    type=float,
    help='Delay between requests in seconds (default: 1.0)'
)
@click.option(
    '--verbose',
    is_flag=True,
    help='Enable verbose logging'
)
@click.option(
    '--dry-run',
    is_flag=True,
    help='Show what would be downloaded without actually downloading'
)
@click.option(
    '--validate-only',
    is_flag=True,
    help='Only validate the course URL and show course information'
)
def main(
    path: Path,
    link: str,
    start: int,
    final: int,
    concurrent: int,
    timeout: int,
    retry_attempts: int,
    delay: float,
    verbose: bool,
    dry_run: bool,
    validate_only: bool
) -> None:
    """
    Channel Plus audio downloader - Python implementation.
    
    Downloads audio files from Taiwan National Radio Channel Plus language learning courses.
    
    Example usage:
        channel-plus --path /Users/scipio/Downloads/ --link https://channelplus.ner.gov.tw/viewalllang/390 --start 155 --final 160
    
    Compatible with the original Elixir version's command-line interface.
    """
    # Set up logging
    setup_logging(verbose)
    logger = logging.getLogger(__name__)
    
    try:
        # Run the async main function
        asyncio.run(async_main(
            path, link, start, final, concurrent, timeout,
            retry_attempts, delay, verbose, dry_run, validate_only
        ))
    except KeyboardInterrupt:
        console.print("\n[yellow]Download interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


async def async_main(
    path: Path,
    link: str,
    start: int,
    final: int,  
    concurrent: int,
    timeout: int,
    retry_attempts: int,
    delay: float,
    verbose: bool,
    dry_run: bool,
    validate_only: bool
) -> None:
    """Async main function that handles the actual work."""
    logger = logging.getLogger(__name__)
    
    try:
        # Create download configuration
        config = DownloadConfig(
            path=path,
            link=link,
            start_episode=start,
            final_episode=final,
            concurrent_downloads=concurrent,
            timeout=timeout,
            retry_attempts=retry_attempts,
            delay_between_requests=delay
        )
        
        # Display configuration
        console.print("[bold blue]Channel Plus Downloader - Python Implementation[/bold blue]")
        console.print("=" * 60)
        console.print(f"Course URL: {link}")
        console.print(f"Episodes: {start} to {final} ({config.total_episodes} total)")
        console.print(f"Download Path: {path}")
        console.print(f"Pages to scan: {config.start_page} to {config.final_page}")
        
        if not dry_run and not validate_only:
            console.print(f"Concurrent downloads: {concurrent}")
            console.print(f"Request timeout: {timeout}s")
        
        console.print("=" * 60)
        
        # Initialize HTTP client and scraper
        async with ChannelPlusHTTPClient(
            timeout=timeout,
            retry_attempts=retry_attempts,
            delay_between_requests=delay,
            max_concurrent=max(concurrent, 5)
        ) as http_client:
            
            scraper = ChannelPlusScraper(http_client)
            
            # Validate course URL
            console.print("[yellow]Validating course URL...[/yellow]")
            if not await scraper.validate_course_url(link):
                console.print("[red]❌ Invalid course URL or no episodes found[/red]")
                sys.exit(1)
            
            console.print("[green]✅ Course URL is valid[/green]")
            
            # Get course information
            if validate_only:
                console.print("\n[yellow]Getting course information...[/yellow]")
                course_info = await scraper.get_course_info(link)
                
                console.print("\n[bold blue]Course Information[/bold blue]")
                console.print(f"Course ID: {course_info['course_id']}")
                console.print(f"Episodes found: {course_info['episodes_found']}")
                console.print(f"Max episode number: {course_info['max_episode_found']}")
                
                if course_info['sample_episode']:
                    sample = course_info['sample_episode']
                    console.print(f"\nSample episode:")
                    console.print(f"  - Part {sample['part']}: {sample['name']}")
                    console.print(f"  - Duration: {sample['audio']['duration']/60:.1f} minutes")
                
                return
            
            # Get episodes in range
            console.print(f"\n[yellow]Collecting episodes {start} to {final}...[/yellow]")
            episodes = await scraper.get_all_episodes(config)
            
            if not episodes:
                console.print("[red]❌ No episodes found in the specified range[/red]")
                sys.exit(1)
            
            console.print(f"[green]✅ Found {len(episodes)} episodes[/green]")
            
            # Show episode list
            if verbose or dry_run:
                console.print("\n[bold blue]Episodes to download:[/bold blue]")
                for episode in episodes[:10]:  # Show first 10
                    duration_min = episode.audio.duration / 60
                    console.print(f"  {episode.part:3d}. {episode.name} ({duration_min:.1f}min)")
                
                if len(episodes) > 10:
                    console.print(f"  ... and {len(episodes) - 10} more episodes")
            
            # Dry run - just show what would be downloaded
            if dry_run:
                total_duration = sum(ep.audio.duration for ep in episodes) / 60
                console.print(f"\n[yellow]Dry run completed[/yellow]")
                console.print(f"Would download {len(episodes)} episodes ({total_duration:.1f} minutes total)")
                return
            
            # Actual download
            console.print(f"\n[yellow]Starting download of {len(episodes)} episodes...[/yellow]")
            
            downloader = ChannelPlusDownloader(http_client, config)
            
            # Download episodes with progress tracking
            summary = await downloader.download_episodes_batch(episodes, show_progress=True)
            
            # Show results
            downloader.print_summary(summary)
            
            # Retry failed downloads if any
            if summary['failed_downloads'] > 0:
                console.print(f"\n[yellow]Retrying {summary['failed_downloads']} failed downloads...[/yellow]")
                retry_summary = await downloader.retry_failed_downloads(max_retries=2)
                
                if retry_summary['failed_downloads'] > 0:
                    console.print(f"\n[red]❌ {retry_summary['failed_downloads']} downloads still failed after retries[/red]")
                    console.print("You may want to try running the command again later.")
                else:
                    console.print("[green]✅ All failed downloads completed successfully![/green]")
            
            # Final status
            final_success_rate = (
                (summary['successful_downloads'] + 
                 (retry_summary.get('successful_downloads', 0) if 'retry_summary' in locals() else 0)) /
                summary['total_episodes'] * 100
            )
            
            if final_success_rate == 100:
                console.print("\n[green]🎉 All downloads completed successfully![/green]")
            elif final_success_rate >= 90:
                console.print(f"\n[yellow]⚠️  Download completed with {final_success_rate:.1f}% success rate[/yellow]")
            else:
                console.print(f"\n[red]❌ Download completed with {final_success_rate:.1f}% success rate[/red]")
    
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        console.print(f"[red]Error: {e}[/red]")
        raise


if __name__ == "__main__":
    main()