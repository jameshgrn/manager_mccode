import json
from datetime import datetime, timedelta
from typing import List, Dict
import duckdb
from manager_mccode.models.screen_summary import ScreenSummary
from manager_mccode.config.settings import DEFAULT_DB_PATH

class DatabaseManager:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.conn = duckdb.connect(db_path)
        self._migrate_db()
        self._init_db()

    def _migrate_db(self):
        """Handle database migrations"""
        try:
            # Drop everything and start fresh
            self.conn.execute("DROP VIEW IF EXISTS hourly_summaries")
            self.conn.execute("DROP VIEW IF EXISTS fifteen_min_summaries")
            self.conn.execute("DROP TABLE IF EXISTS screen_summaries")
            print("Database reset complete")
            
        except Exception as e:
            print(f"Migration failed: {str(e)}")
            print("Creating fresh tables...")
            self.conn.execute("DROP TABLE IF EXISTS screen_summaries")

    def _init_db(self):
        """Initialize database tables"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS screen_summaries (
                timestamp TIMESTAMP,
                summary VARCHAR,
                activities JSON,  -- Stores full activity objects
                context JSON,     -- Stores context information
                fifteen_min_bucket TIMESTAMP
            )
        """)
        
        self.conn.execute("""
            CREATE VIEW IF NOT EXISTS fifteen_min_summaries AS
            SELECT 
                fifteen_min_bucket,
                STRING_AGG(summary, ' | ') as combined_summaries,
                JSON_GROUP_ARRAY(activities) as all_activities,
                JSON_GROUP_ARRAY(context) as contexts,
                COUNT(*) as snapshot_count,
                -- Extract attention states for analysis
                JSON_GROUP_ARRAY(
                    JSON_EXTRACT(context, '$.attention_state')
                ) as attention_states
            FROM screen_summaries
            GROUP BY fifteen_min_bucket
            ORDER BY fifteen_min_bucket DESC
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_screen_summaries_timestamp 
            ON screen_summaries(timestamp)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_screen_summaries_bucket 
            ON screen_summaries(fifteen_min_bucket)
        """)

    def store_summary(self, summary: ScreenSummary):
        """Store a single summary with 15-minute bucketing"""
        try:
            minutes = summary.timestamp.minute
            fifteen_min_bucket = summary.timestamp.replace(
                minute=(minutes // 15) * 15,
                second=0,
                microsecond=0
            )
            
            self.conn.execute("""
                INSERT INTO screen_summaries (
                    timestamp, 
                    summary, 
                    activities, 
                    context,
                    fifteen_min_bucket
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                summary.timestamp,
                summary.summary,
                json.dumps([act.model_dump() for act in summary.activities]),
                json.dumps(summary.context.model_dump()),
                fifteen_min_bucket
            ))
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"Error storing summary: {e}")

    def get_recent_fifteen_min_summaries(self, hours: float = 1.0) -> List[Dict]:
        """Get 15-minute summaries from the last N hours"""
        cutoff = datetime.now() - timedelta(hours=hours)
        try:
            results = self.conn.execute("""
                SELECT 
                    fifteen_min_bucket as bucket,
                    combined_summaries,
                    CAST(all_activities AS VARCHAR) as activities,
                    snapshot_count
                FROM fifteen_min_summaries
                WHERE fifteen_min_bucket > ?
                ORDER BY fifteen_min_bucket DESC
            """, [cutoff]).fetchall()
            
            return [{
                'bucket': row[0],
                'combined_summaries': row[1],
                'all_activities': json.loads(row[2]) if row[2] else [],
                'snapshot_count': row[3]
            } for row in results]
            
        except Exception as e:
            print(f"Database error: {str(e)}")
            return []

    def export_daily_summary(self, date: datetime = None) -> str:
        """Export daily summary as formatted text"""
        if date is None:
            date = datetime.now()
        
        # Fix: Create datetime objects properly for start/end of day
        start_of_day = datetime.combine(date.date(), datetime.min.time())
        end_of_day = datetime.combine(date.date(), datetime.max.time())
        
        try:
            results = self.conn.execute("""
                SELECT 
                    fifteen_min_bucket,
                    combined_summaries,
                    CAST(all_activities AS VARCHAR) as activities,
                    snapshot_count
                FROM fifteen_min_summaries
                WHERE fifteen_min_bucket >= ? AND fifteen_min_bucket < ?
                ORDER BY fifteen_min_bucket ASC
            """, [start_of_day, end_of_day]).fetchall()
            
            summary_text = self._format_daily_summary(date, results)
            filename = f"daily_summary_{date.strftime('%Y%m%d')}.txt"
            
            with open(filename, 'w') as f:
                f.write(summary_text)
            
            return filename
            
        except Exception as e:
            logger.error(f"Error exporting daily summary: {e}")
            return None

    def _format_daily_summary(self, date: datetime, results: List) -> str:
        summary_text = f"Daily Summary for {date.strftime('%Y-%m-%d')}\n"
        summary_text += "=" * 80 + "\n\n"
        
        total_snapshots = 0
        all_activities = set()
        
        for row in results:
            bucket_time = row[0]
            summaries = row[1]
            activities = json.loads(row[2]) if row[2] else []
            snapshot_count = row[3]
            
            total_snapshots += snapshot_count
            all_activities.update([act for acts in activities for act in acts])
            
            summary_text += self._format_time_block(bucket_time, snapshot_count, activities, summaries)
        
        overview = self._format_overview(len(results), total_snapshots, all_activities)
        return overview + summary_text

    def _format_time_block(self, bucket_time: datetime, snapshot_count: int, 
                          activities: List, summaries: str) -> str:
        return f"""Time Period: {bucket_time.strftime('%H:%M')} - {(bucket_time + timedelta(minutes=15)).strftime('%H:%M')}
Snapshots: {snapshot_count}
Activities: {', '.join(set(act for acts in activities for act in acts))}
Summary: {summaries}
{'-' * 80}\n\n"""

    def _format_overview(self, num_periods: int, total_snapshots: int, 
                        all_activities: set) -> str:
        return f"""Daily Overview:
Total Time Tracked: {num_periods * 15} minutes
Total Snapshots: {total_snapshots}
Unique Activities: {', '.join(sorted(all_activities))}

Detailed Timeline:
""" 