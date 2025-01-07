import click
import os
import sys
import subprocess
from pathlib import Path
from manager_mccode.config.logging_config import setup_logging
from manager_mccode.services.database import DatabaseManager
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from datetime import datetime, timedelta
import logging
import asyncio

# Set up logging
logger = logging.getLogger(__name__)

@click.group()
def cli():
    """Manager McCode Service Controller"""
    # Set up logging before anything else
    setup_logging()
    pass

@cli.command()
def install():
    """Install Manager McCode as a system service"""
    if sys.platform == 'darwin':  # macOS
        plist_path = Path.home() / 'Library/LaunchAgents/com.jake.manager-mccode.plist'
        template_path = Path(__file__).parent / 'templates/com.jake.manager-mccode.plist'
        
        # Create plist from template
        with open(template_path) as f:
            template = f.read()
        
        # Replace paths
        poetry_path = subprocess.check_output(['which', 'poetry']).decode().strip()
        project_path = Path(__file__).parent.parent.parent
        
        plist_content = template.replace('/path/to/poetry', poetry_path)
        plist_content = plist_content.replace('/path/to/manager_mccode', str(project_path))
        
        # Write plist
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        with open(plist_path, 'w') as f:
            f.write(plist_content)
        
        # Load service
        subprocess.run(['launchctl', 'load', str(plist_path)])
        click.echo("Service installed and started!")
        
    elif sys.platform.startswith('linux'):  # Linux
        systemd_path = Path('/etc/systemd/system/manager-mccode@.service')
        template_path = Path(__file__).parent / 'templates/manager-mccode.service'
        
        if not os.geteuid() == 0:
            click.echo("This command must be run as root on Linux")
            sys.exit(1)
            
        # Create service file from template
        with open(template_path) as f:
            template = f.read()
        
        # Replace paths
        poetry_path = subprocess.check_output(['which', 'poetry']).decode().strip()
        project_path = Path(__file__).parent.parent.parent
        
        service_content = template.replace('/path/to/poetry', poetry_path)
        service_content = service_content.replace('/path/to/manager_mccode', str(project_path))
        
        # Write service file
        with open(systemd_path, 'w') as f:
            f.write(service_content)
            
        # Reload systemd and start service
        subprocess.run(['systemctl', 'daemon-reload'])
        subprocess.run(['systemctl', 'enable', f'manager-mccode@{os.getenv("USER")}'])
        subprocess.run(['systemctl', 'start', f'manager-mccode@{os.getenv("USER")}'])
        click.echo("Service installed and started!")

@cli.command()
def start():
    """Start the Manager McCode service"""
    try:
        if sys.platform == 'darwin':
            subprocess.run(['launchctl', 'start', 'com.jake.manager-mccode'])
        elif sys.platform.startswith('linux'):
            subprocess.run(['systemctl', 'start', f'manager-mccode@{os.getenv("USER")}'])
        click.echo("Service started!")
    except Exception as e:
        logging.error(f"Failed to start service: {e}")
        sys.exit(1)

@cli.command()
def stop():
    """Stop the Manager McCode service"""
    try:
        if sys.platform == 'darwin':
            subprocess.run(['launchctl', 'stop', 'com.jake.manager-mccode'])
        elif sys.platform.startswith('linux'):
            subprocess.run(['systemctl', 'stop', f'manager-mccode@{os.getenv("USER")}'])
        if os.path.exists("manager_mccode.db"):
            os.remove("manager_mccode.db")
        click.echo("Service stopped!")
    except Exception as e:
        logging.error(f"Failed to stop service: {e}")
        sys.exit(1)

@cli.command()
def status():
    """Check the status of Manager McCode service"""
    if sys.platform == 'darwin':
        subprocess.run(['launchctl', 'list', 'com.jake.manager-mccode'])
    elif sys.platform.startswith('linux'):
        subprocess.run(['systemctl', 'status', f'manager-mccode@{os.getenv("USER")}'])

@cli.command()
def inspect():
    """Inspect the stored summaries in the database"""
    console = Console()
    db = DatabaseManager()
    
    # Get last 10 summaries
    summaries = db.get_recent_summaries(limit=10)
    
    if not summaries:
        console.print("[yellow]No summaries found in the database[/yellow]")
        return
    
    # Create summary table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Time", style="cyan", width=12)
    table.add_column("Activities", style="green")
    table.add_column("Snapshots", justify="right", style="blue")
    table.add_column("Summary", style="white", width=60)
    
    for summary in summaries:
        time_str = summary['timestamp']
        activities = summary.get('activities', [])
        activities_str = ", ".join(act.get('name', 'Unknown') for act in activities)
        if len(activities_str) > 40:
            activities_str = activities_str[:37] + "..."
            
        table.add_row(
            time_str,
            activities_str,
            "1",  # Each summary is one snapshot
            summary['summary'][:57] + "..." if len(summary['summary']) > 60 else summary['summary']
        )
    
    console.print("\n[bold cyan]Recent Database Summaries[/bold cyan]")
    console.print(table)
    
    # Show statistics
    total_snapshots = sum(s['snapshot_count'] for s in summaries)
    total_periods = len(summaries)
    all_activities = set([act for s in summaries for acts in s['all_activities'] for act in acts])
    
    console.print("\n[bold yellow]Statistics[/bold yellow]")
    console.print(f"Total Time Periods: {total_periods} (15-min blocks)")
    console.print(f"Total Snapshots: {total_snapshots}")
    console.print(f"Unique Activities: {len(all_activities)}")

@cli.command()
def check():
    """Detailed check of the service status"""
    try:
        console = Console()
        
        # Check if process is running
        if sys.platform == 'darwin':
            result = subprocess.run(['pgrep', '-f', 'manager_mccode'], capture_output=True)
            is_running = result.returncode == 0
        elif sys.platform.startswith('linux'):
            result = subprocess.run(['systemctl', 'is-active', f'manager-mccode@{os.getenv("USER")}'], capture_output=True)
            is_running = result.returncode == 0
            
        # Check log file
        log_file = Path("logs/manager_mccode.log")
        recent_logs = []
        if log_file.exists():
            with open(log_file) as f:
                recent_logs = list(f)[-10:]  # Get last 10 lines
                
        # Check screenshots directory
        screenshots_dir = Path("temp_screenshots")
        screenshot_count = len(list(screenshots_dir.glob("*.png"))) if screenshots_dir.exists() else 0
        
        # Display status
        console.print("\n[bold cyan]Service Status Check[/bold cyan]")
        console.print(f"Process running: [{'green' if is_running else 'red'}]{is_running}[/]")
        console.print(f"Screenshot count: {screenshot_count}")
        console.print("\n[bold yellow]Recent Logs:[/bold yellow]")
        for log in recent_logs:
            console.print(log.strip())
            
    except Exception as e:
        logging.error(f"Status check failed: {e}")
        sys.exit(1)

@cli.command()
def debug():
    """Run the service in debug mode"""
    try:
        console = Console()
        console.print("[yellow]Starting Manager McCode in debug mode...[/yellow]")
        
        # Set debug logging
        logging.getLogger().setLevel(logging.DEBUG)
        
        # Run the main process directly
        from manager_mccode.main import main
        asyncio.run(main())
    except Exception as e:
        logging.error(f"Debug mode failed: {e}", exc_info=True)
        sys.exit(1)

@cli.group()
def db():
    """Database management commands"""
    pass

@db.command()
@click.option('--days', type=int, help='Days of data to retain')
def cleanup(days: int):
    """Clean up old data from the database"""
    try:
        db = DatabaseManager()
        deleted, reclaimed = db.cleanup_old_data(days)
        
        console = Console()
        console.print(Panel(
            f"[green]Cleaned up {deleted} records[/green]\n"
            f"[blue]Reclaimed {reclaimed/1024/1024:.1f}MB of space[/blue]",
            title="Database Cleanup"
        ))
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        sys.exit(1)

@db.command()
def stats():
    """Show database statistics"""
    try:
        db = DatabaseManager()
        stats = db.get_database_stats()
        
        console = Console()
        
        # Table statistics
        table = Table(title="Database Tables")
        table.add_column("Table", style="cyan")
        table.add_column("Rows", justify="right", style="green")
        table.add_column("Indexes", justify="right", style="yellow")
        table.add_column("Triggers", justify="right", style="magenta")
        
        for table_name, info in stats['tables'].items():
            table.add_row(
                table_name,
                str(info['row_count']),
                str(info['index_count']),
                str(info['trigger_count'])
            )
        
        console.print(table)
        
        # Time range info
        time_range = stats['time_range']
        if time_range['oldest'] and time_range['newest']:
            oldest = datetime.fromisoformat(time_range['oldest'])
            newest = datetime.fromisoformat(time_range['newest'])
            date_range = newest - oldest
            
            time_panel = Panel(
                f"[cyan]Date Range:[/cyan] {date_range.days} days\n"
                f"[green]Oldest Record:[/green] {oldest.strftime('%Y-%m-%d %H:%M')}\n"
                f"[green]Newest Record:[/green] {newest.strftime('%Y-%m-%d %H:%M')}\n"
                f"[yellow]Total Records:[/yellow] {time_range['total_records']:,}",
                title="Data Overview"
            )
            console.print(time_panel)
        
        # Database size
        size_text = Text()
        size_text.append("\nDatabase Size: ", style="bold")
        size_text.append(f"{stats['database_size_mb']:.1f}MB", style="green")
        console.print(size_text)
        
    except Exception as e:
        logger.error(f"Failed to get database stats: {e}")
        sys.exit(1)

@db.command()
def verify():
    """Verify database integrity"""
    try:
        db = DatabaseManager()
        is_healthy = db.verify_database_integrity()
        
        console = Console()
        if is_healthy:
            console.print("[green]Database integrity check passed[/green]")
        else:
            console.print("[red]Database integrity check failed![/red]")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Integrity check failed: {e}")
        sys.exit(1)

@db.command()
def optimize():
    """Optimize database performance"""
    try:
        db = DatabaseManager()
        db._optimize_database()
        console = Console()
        console.print("[green]Database optimization complete[/green]")
    except Exception as e:
        logger.error(f"Optimization failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    cli() 