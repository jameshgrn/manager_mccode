from datetime import datetime
from typing import List, Dict
import os
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.layout import Layout
from rich.markdown import Markdown

class TerminalDisplay:
    def __init__(self):
        self.console = Console()
        
    def show_recent_summaries(self, summaries: List[Dict], hours: float = 1.0):
        """Display recent summaries in a nice terminal format"""
        # Clear screen
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # Create header
        header = Text()
        header.append("📊 Manager McCode Activity Monitor", style="bold cyan")
        header.append(f"\nShowing last {hours} hours of activity\n", style="dim")
        self.console.print(Panel(header, expand=False))
        
        if not summaries:
            self.console.print("\n[yellow]No recent activities recorded[/yellow]")
            return

        # Show detailed summaries in reverse chronological order
        for summary in reversed(summaries):
            time_str = summary['bucket'].strftime('%H:%M')
            activities = summary['all_activities']
            summary_text = summary['combined_summaries']
            snapshot_count = summary['snapshot_count']
            contexts = summary.get('contexts', [])
            attention_states = summary.get('attention_states', [])
            
            # Create time block header
            time_header = Text()
            time_header.append(f"🕒 {time_str}", style="bold cyan")
            time_header.append(f" ({snapshot_count} snapshots)", style="dim")
            
            # Add attention state if available
            if attention_states:
                primary_state = max(set(attention_states), key=attention_states.count)
                state_emoji = {
                    'focused': '🎯',
                    'scattered': '🔄',
                    'transitioning': '⚡'
                }.get(primary_state, '❓')
                time_header.append(f" {state_emoji} {primary_state}", style="bold yellow")
            
            self.console.print("\n" + "="*80)
            self.console.print(time_header)
            
            # Show activities with their context
            if activities:
                self.console.print("\n[bold green]Activities:[/bold green]")
                for activity_group in activities:
                    for activity in activity_group:
                        if isinstance(activity, dict):
                            name = activity.get('name', 'Unknown')
                            category = activity.get('category', 'Other')
                            purpose = activity.get('purpose', '')
                            focus = activity.get('focus_indicators', {})
                            
                            activity_text = Text()
                            activity_text.append(f"  • {name}", style="green")
                            if category:
                                activity_text.append(f" [{category}]", style="blue")
                            if purpose:
                                activity_text.append(f": {purpose}", style="dim")
                            
                            # Show focus indicators
                            if focus:
                                window_state = focus.get('window_state')
                                tab_count = focus.get('tab_count')
                                content_type = focus.get('content_type')
                                
                                focus_text = []
                                if window_state:
                                    focus_text.append(window_state)
                                if tab_count:
                                    focus_text.append(f"{tab_count} tabs")
                                if content_type:
                                    focus_text.append(content_type)
                                
                                if focus_text:
                                    activity_text.append(f" ({', '.join(focus_text)})", style="italic dim")
                                
                            self.console.print(activity_text)
            
            # Show context if available
            if contexts:
                context = contexts[0]  # Take first context as representative
                if isinstance(context, dict):
                    self.console.print("\n[bold magenta]Context:[/bold magenta]")
                    if primary_task := context.get('primary_task'):
                        self.console.print(f"  Task: {primary_task}")
                    if environment := context.get('environment'):
                        self.console.print(f"  Environment: {environment}")
            
            # Show summary
            if summary_text:
                self.console.print("\n[bold white]Summary:[/bold white]")
                for idx, detail in enumerate(summary_text.split(" | ")):
                    if detail.strip():
                        self.console.print(f"  {idx+1}. {detail.strip()}")
            
            self.console.print("-"*80)
        
        # Show overall statistics with enhanced metrics
        total_snapshots = sum(s['snapshot_count'] for s in summaries)
        total_minutes = len(summaries) * 15
        
        # Collect all unique activities and their contexts
        all_activities = []
        for s in summaries:
            for activity_group in s['all_activities']:
                all_activities.extend([
                    act for act in activity_group 
                    if isinstance(act, dict)
                ])
        
        # Calculate focus metrics
        attention_states = [
            state 
            for s in summaries 
            if 'attention_states' in s
            for state in s['attention_states']
        ]
        focus_percentage = (
            attention_states.count('focused') / len(attention_states)
            if attention_states else 0
        ) * 100
        
        stats = Text()
        stats.append("\n📈 Session Statistics\n", style="bold yellow")
        stats.append(f"Time Tracked: {total_minutes} minutes\n", style="dim")
        stats.append(f"Total Snapshots: {total_snapshots}\n", style="dim")
        stats.append(f"Focus Score: {focus_percentage:.1f}%\n", style="bold green")
        
        self.console.print(Panel(stats, expand=False)) 