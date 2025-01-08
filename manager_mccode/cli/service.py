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
import uvicorn
from manager_mccode.config.settings import Settings
from manager_mccode.config.settings import settings
import signal

# Set up logging
logger = logging.getLogger(__name__)

# Initialize console
console = Console()

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
@click.option('--debug', is_flag=True, help='Enable debug output')
def start(debug):
    """Start Manager McCode as a background service"""
    try:
        from manager_mccode.services.runner import run_service
        if not debug:
            # Only show minimal output
            console.print("[yellow]Starting Manager McCode...[/yellow]")
            run_service()
        else:
            # Show full debug output
            console.print("[yellow]Starting Manager McCode in debug mode...[/yellow]")
            logging.getLogger().setLevel(logging.DEBUG)
            run_service()
    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        console.print(f"[red]Failed to start service: {e}[/red]")
        sys.exit(1)

@cli.command()
def stop():
    """Stop the Manager McCode service"""
    try:
        if sys.platform == 'darwin':
            subprocess.run(['launchctl', 'stop', 'com.jake.manager-mccode'])
        elif sys.platform.startswith('linux'):
            subprocess.run(['systemctl', 'stop', f'manager-mccode@{os.getenv("USER")}'])
            
        # Clean up only temporary files
        temp_dir = Path(settings.TEMP_DIR)
        if temp_dir.exists():
            for file in temp_dir.glob("*.png"):
                file.unlink()
            
        click.echo("Service stopped!")
    except Exception as e:
        logging.error(f"Failed to stop service: {e}")
        sys.exit(1)

@cli.command()
def status():
    """Check service status"""
    try:
        pid_file = settings.DATA_DIR / "manager_mccode.pid"
        if not pid_file.exists():
            console.print("[yellow]Service is not running[/yellow]")
            return
        
        pid = int(pid_file.read_text().strip())
        try:
            os.kill(pid, 0)  # Check if process exists
            console.print(f"[green]Service is running (PID: {pid})[/green]")
        except ProcessLookupError:
            console.print("[red]Service crashed or was killed[/red]")
            pid_file.unlink()
    except Exception as e:
        logger.error(f"Failed to check service status: {e}")
        sys.exit(1)

@cli.command()
def inspect():
    """Inspect recent activity summaries"""
    try:
        db = DatabaseManager()
        summaries = db.get_recent_summaries(hours=24)  # Show last 24 hours of summaries
        
        if not summaries:
            console.print("[yellow]No recent summaries found[/yellow]")
            return
            
        # Create a table for display
        table = Table(title="Recent Activity Summaries")
        table.add_column("Time", justify="left", style="cyan")
        table.add_column("Summary", justify="left", style="green")
        table.add_column("Activities", justify="left", style="yellow")
        
        for summary in summaries:
            activities = "\n".join([
                f"• {a.name} ({a.category})" 
                for a in summary.activities
            ])
            
            table.add_row(
                summary.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                summary.summary,
                activities
            )
            
        console.print(table)
        
    except Exception as e:
        logger.error(f"Failed to inspect summaries: {e}")
        console.print(f"[red]Error inspecting summaries: {e}[/red]")
        sys.exit(1)

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

@db.command()
def clear():
    """Clear all data from the database"""
    try:
        db = DatabaseManager()
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Disable foreign key checks temporarily
        cursor.execute("PRAGMA foreign_keys = OFF")
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        # Delete data from all tables
        for (table_name,) in tables:
            if table_name != 'sqlite_sequence':  # Skip SQLite internal table
                cursor.execute(f"DELETE FROM {table_name}")
        
        cursor.execute("PRAGMA foreign_keys = ON")
        conn.commit()
        
        click.echo("Database cleared successfully")
    except Exception as e:
        click.echo(f"Error clearing database: {e}", err=True)
        sys.exit(1)

@db.command()
def info():
    """Show database information"""
    try:
        db = DatabaseManager()
        stats = db.get_database_stats()
        
        console = Console()
        console.print("\n[bold]Database Statistics[/bold]")
        
        if stats['time_range']['total_records'] > 0:
            console.print(f"\nTotal Records: {stats['time_range']['total_records']}")
            console.print(f"Earliest Record: {stats['time_range']['earliest_record']}")
            console.print(f"Latest Record: {stats['time_range']['latest_record']}")
        else:
            console.print("\n[yellow]No records found in database[/yellow]")
            
        console.print(f"\nDatabase Size: {stats['database_size_mb']:.2f}MB")
        
    except Exception as e:
        click.echo(f"Error getting database info: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.option('--host', default='127.0.0.1', help='Host to bind to')
@click.option('--port', default=8000, help='Port to bind to')
@click.option('--reload', is_flag=True, help='Enable auto-reload')
def web(host: str, port: int, reload: bool):
    """Start the web interface"""
    settings = Settings()
    
    # Ensure template and static directories exist
    web_dir = Path(__file__).parent.parent / 'web'
    templates_dir = web_dir / 'templates'
    static_dir = web_dir / 'static'
    
    if not all(d.exists() for d in [templates_dir, static_dir]):
        click.echo("Error: Web interface directories not found")
        return
    
    click.echo(f"Starting web interface on http://{host}:{port}")
    uvicorn.run(
        "manager_mccode.web.app:app",
        host=host,
        port=port,
        reload=reload
    )

@cli.command()
@click.option('--hours', default=24, help='Hours of history to analyze')
def focus(hours):
    """Analyze focus patterns and productivity metrics"""
    console = Console()
    
    try:
        db = DatabaseManager()
        metrics = db.get_focus_metrics(hours=hours)
        
        # Create focus report
        time_chart = Table(title="Peak Performance Times")
        time_chart.add_column("Time Block")
        time_chart.add_column("Focus Score")
        time_chart.add_column("Common Activities")
        
        # Context Switching Analysis
        switch_panel = Panel(
            Text.from_markup(
                f"[bold]Context Switching Patterns[/bold]\n"
                f"Average switches per hour: {metrics['context_switches']['switches_per_hour']:.1f}\n"
                f"Longest focus duration: {metrics['context_switches']['max_focus_duration']} minutes\n"
                f"Most common triggers: {', '.join(metrics['context_switches']['common_triggers'])}"
            )
        )
        
        # Task Completion Stats
        completion_chart = Table(title="Task Completion Analysis")
        completion_chart.add_column("Task Type")
        completion_chart.add_column("Completion Rate")
        completion_chart.add_column("Avg Focus Quality")
        
        # Focus Recovery Insights
        recovery_panel = Panel(
            Text.from_markup(
                f"[bold]Focus Recovery Patterns[/bold]\n"
                f"Average recovery time: {metrics['task_completion']['avg_recovery_time']:.1f} minutes\n"
                f"Best recovery activities: {', '.join(metrics['focus_quality']['recovery_activities'])}\n"
                f"Environmental factors: {', '.join(metrics['environment_impact']['environmental_impacts'])}"
            )
        )
        
        # Recommendations
        recommendations = Panel(
            Text.from_markup(
                "[bold]Focus Enhancement Recommendations[/bold]\n"
                "• " + "\n• ".join(metrics['recommendations'])
            ),
            title="Personalized Recommendations"
        )
        
        # Display all components
        console.print(time_chart)
        console.print(switch_panel)
        console.print(completion_chart)
        console.print(recovery_panel)
        console.print(recommendations)
        
    except Exception as e:
        logger.error(f"Failed to analyze focus patterns: {e}")
        console.print(f"[red]Error analyzing focus patterns: {e}[/red]")

@cli.command()
def debug_db():
    """Debug database contents"""
    try:
        db = DatabaseManager()
        conn = db.get_connection()
        try:
            cursor = conn.cursor()
            
            # Check activity_snapshots
            cursor.execute("SELECT COUNT(*) FROM activity_snapshots")
            snapshot_count = cursor.fetchone()[0]
            console.print(f"[cyan]Total snapshots:[/cyan] {snapshot_count}")
            
            # Get most recent snapshots
            cursor.execute("""
                SELECT id, timestamp, summary 
                FROM activity_snapshots 
                ORDER BY timestamp DESC 
                LIMIT 5
            """)
            recent = cursor.fetchall()
            
            if recent:
                console.print("\n[cyan]Most recent snapshots:[/cyan]")
                for row in recent:
                    console.print(f"ID: {row[0]}, Time: {row[1]}")
                    console.print(f"Summary: {row[2][:100]}...")
            
            # Check activities
            cursor.execute("SELECT COUNT(*) FROM activities")
            activity_count = cursor.fetchone()[0]
            console.print(f"\n[cyan]Total activities:[/cyan] {activity_count}")
            
            # Get activity distribution
            cursor.execute("""
                SELECT category, COUNT(*) 
                FROM activities 
                GROUP BY category
            """)
            categories = cursor.fetchall()
            
            if categories:
                console.print("\n[cyan]Activity categories:[/cyan]")
                for cat, count in categories:
                    console.print(f"{cat}: {count}")
                    
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Failed to debug database: {e}")
        console.print(f"[red]Error debugging database: {e}[/red]")
        sys.exit(1)

if __name__ == '__main__':
    cli() 