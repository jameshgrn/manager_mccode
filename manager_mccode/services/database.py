from datetime import datetime, timedelta
import sqlite3
from pathlib import Path
import logging
from typing import List, Dict
import sys
import json
from manager_mccode.models.screen_summary import ScreenSummary

logger = logging.getLogger(__name__)

MIGRATIONS = [
    """
    -- initial_schema
    DROP TABLE IF EXISTS activity_snapshots;
    DROP TABLE IF EXISTS focus_states;
    DROP TABLE IF EXISTS task_segments;

    CREATE TABLE activity_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP NOT NULL,
        summary TEXT NOT NULL,
        window_title TEXT,
        active_app TEXT,
        focus_score FLOAT,
        batch_id INTEGER
    );

    CREATE TABLE focus_states (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id INTEGER,
        state_type VARCHAR(50),
        confidence FLOAT,
        context TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE task_segments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        start_time TIMESTAMP NOT NULL,
        end_time TIMESTAMP,
        task_name TEXT,
        category TEXT,
        context TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp 
        ON activity_snapshots(timestamp);
    
    CREATE INDEX IF NOT EXISTS idx_task_segments_time 
        ON task_segments(start_time, end_time);
    """
]

class DatabaseManager:
    def __init__(self, db_path: str = "manager_mccode.db"):
        self.db_path = Path(db_path)
        logger.info(f"Initialized DatabaseManager with db_path: {self.db_path}")
        self.conn = None
        self.initialize()

    def initialize(self):
        """Initialize the database and run migrations"""
        try:
            logger.info(f"Connecting to database at path: {self.db_path}")
            db_path_str = str(self.db_path)
            
            # Try to create parent directory if it doesn't exist
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            self.conn = sqlite3.connect(db_path_str)
            # Enable foreign key support
            self.conn.execute("PRAGMA foreign_keys = ON")
            logger.info("Successfully connected to SQLite.")
            
            # Run migrations in a transaction
            self.conn.execute("BEGIN TRANSACTION")
            try:
                self._run_migrations()
                self.conn.commit()
                logger.info("Database initialization complete")
            except Exception as e:
                self.conn.rollback()
                raise e
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}", exc_info=True)
            raise

    def _run_migrations(self):
        """Run any pending database migrations"""
        try:
            # Create migrations table first
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS migrations (
                    name VARCHAR PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Then run each migration in order
            for migration in MIGRATIONS:
                # Extract migration name from comment
                migration_name = migration.split('\n')[1].strip('- ')
                
                # Check if migration has been run
                cursor = self.conn.execute("""
                    SELECT COUNT(*) 
                    FROM migrations 
                    WHERE name = ?
                """, [migration_name])
                result = cursor.fetchone()
                
                if result[0] == 0:
                    logger.info(f"Running migration: {migration_name}")
                    try:
                        # Execute migration
                        self.conn.executescript(migration)
                        
                        # Record migration
                        self.conn.execute(
                            "INSERT INTO migrations (name) VALUES (?)",
                            [migration_name]
                        )
                        
                        logger.info(f"Successfully applied migration: {migration_name}")
                        
                    except Exception as e:
                        logger.error(f"Failed to apply migration {migration_name}: {e}")
                        raise e
                        
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise e

    def store_snapshot(self, snapshot_data: Dict):
        """Store a new activity snapshot"""
        try:
            self.conn.execute("""
                INSERT INTO activity_snapshots (
                    timestamp, summary, window_title, 
                    active_app, focus_score
                ) VALUES (?, ?, ?, ?, ?)
            """, [
                snapshot_data['timestamp'],
                snapshot_data['summary'],
                snapshot_data.get('window_title'),
                snapshot_data.get('active_app'),
                snapshot_data.get('focus_score', 0.0)
            ])
            self.conn.commit()
            logger.info("Snapshot stored successfully.")
        except Exception as e:
            logger.error(f"Failed to store snapshot: {e}", exc_info=True)
            raise

    def get_recent_activity(self, hours: int = 24) -> List[Dict]:
        """Get recent activity summaries"""
        cutoff = datetime.now() - timedelta(hours=hours)
        cursor = self.conn.execute("""
            SELECT 
                strftime('%Y-%m-%d %H:%M', timestamp, '15 minutes') as period,
                COUNT(*) as snapshot_count,
                GROUP_CONCAT(DISTINCT active_app) as apps,
                AVG(focus_score) as avg_focus,
                GROUP_CONCAT(summary, ' | ') as summaries
            FROM activity_snapshots 
            WHERE timestamp > ?
            GROUP BY period
            ORDER BY period DESC
        """, [cutoff])
        return cursor.fetchall()

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed.") 

    def store_summary(self, summary: ScreenSummary):
        """Store a summary in the database and return its ID"""
        try:
            self.conn.execute("BEGIN TRANSACTION")
            try:
                # Insert snapshot and get the generated ID
                cursor = self.conn.execute("""
                    INSERT INTO activity_snapshots (
                        timestamp, summary, focus_score
                    ) VALUES (?, ?, ?)
                    RETURNING id
                """, [
                    summary.timestamp,
                    summary.summary,
                    self._calculate_focus_score(summary)
                ])
                snapshot_id = cursor.fetchone()[0]

                # Store focus states if we have context
                if summary.context and summary.context.attention_state:
                    self.conn.execute("""
                        INSERT INTO focus_states (
                            snapshot_id, state_type, confidence, context
                        ) VALUES (?, ?, ?, ?)
                    """, [
                        snapshot_id,
                        summary.context.attention_state,
                        summary.context.confidence,
                        json.dumps(summary.context.dict())
                    ])

                # Update task segments if needed
                if summary.context and summary.context.primary_task:
                    self._update_task_segments(summary)

                self.conn.commit()
                return snapshot_id

            except Exception as e:
                self.conn.rollback()
                raise e

        except Exception as e:
            logger.error(f"Failed to store summary: {str(e)}")
            raise

    def _calculate_focus_score(self, summary: ScreenSummary) -> float:
        """Calculate a focus score from the summary"""
        try:
            # Base score from attention state
            base_score = {
                'focused': 0.8,
                'transitioning': 0.5,
                'scattered': 0.2
            }.get(summary.context.attention_state, 0.5)

            # Adjust based on activities
            activity_scores = []
            for activity in summary.activities:
                focus_indicators = activity.focus_indicators
                activity_score = 0.0
                
                # Convert string indicators to numeric scores
                attention_level = float(focus_indicators.attention_level) / 100.0
                context_switches = {
                    'low': 0.8,
                    'medium': 0.5,
                    'high': 0.2
                }.get(focus_indicators.context_switches, 0.5)
                organization = {
                    'organized': 0.8,
                    'mixed': 0.5,
                    'scattered': 0.2
                }.get(focus_indicators.workspace_organization, 0.5)
                
                # Combine scores
                activity_score = (attention_level + context_switches + organization) / 3
                activity_scores.append(activity_score)

            # Combine base score with activity scores
            if activity_scores:
                return (base_score + sum(activity_scores) / len(activity_scores)) / 2
            return base_score

        except Exception as e:
            logger.error(f"Error calculating focus score: {e}")
            return 0.5

    def _update_task_segments(self, summary: ScreenSummary):
        """Update or create task segments based on the summary"""
        try:
            # First, close any open segments
            self.conn.execute("""
                UPDATE task_segments 
                SET end_time = ? 
                WHERE end_time IS NULL
            """, [summary.timestamp])

            # Create new segment using SQLite's autoincrement
            self.conn.execute("""
                INSERT INTO task_segments (
                    start_time, 
                    end_time,
                    task_name, 
                    category, 
                    context
                ) VALUES (?, NULL, ?, ?, ?)
            """, [
                summary.timestamp,
                summary.context.primary_task if summary.context else 'unknown',
                summary.activities[0].category if summary.activities else 'unknown',
                json.dumps({
                    'environment': summary.context.environment if summary.context else {},
                    'activities': [a.dict() for a in summary.activities] if summary.activities else []
                })
            ])
                
        except Exception as e:
            logger.error(f"Error updating task segments: {str(e)}")
            raise e

    def _get_segment_task(self, segment_id: int) -> str:
        """Get the task name for a segment"""
        cursor = self.conn.execute("""
            SELECT task_name FROM task_segments WHERE id = ?
        """, [segment_id])
        result = cursor.fetchone()
        return result[0] if result else "unknown"  # Return "unknown" instead of None

    def _verify_schema(self):
        """Verify database schema is correct"""
        try:
            # SQLite schema query
            cursor = self.conn.execute("""
                SELECT sql FROM sqlite_master 
                WHERE type='table' AND name='task_segments';
            """)
            schema = cursor.fetchone()
            logger.debug(f"Task segments table schema: {schema}")
            
            # Check autoincrement
            cursor = self.conn.execute("""
                SELECT * FROM sqlite_sequence 
                WHERE name='task_segments';
            """)
            seq = cursor.fetchone()
            logger.debug(f"Task segments sequence info: {seq}")
        except Exception as e:
            logger.error(f"Schema verification failed: {e}") 

    def get_recent_summaries(self, limit: int = 10) -> List[Dict]:
        """Get the most recent summaries with their associated task segments and focus states"""
        try:
            cursor = self.conn.execute("""
                SELECT 
                    a.id,
                    datetime(a.timestamp) as timestamp,
                    a.summary,
                    a.focus_score,
                    t.task_name,
                    t.category,
                    f.state_type as focus_state,
                    f.confidence as focus_confidence
                FROM activity_snapshots a
                LEFT JOIN task_segments t ON a.timestamp >= t.start_time 
                    AND (a.timestamp < t.end_time OR t.end_time IS NULL)
                LEFT JOIN focus_states f ON a.id = f.snapshot_id
                ORDER BY a.timestamp DESC
                LIMIT ?
            """, [limit])
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'id': row[0],
                    'timestamp': row[1],
                    'summary': row[2],
                    'focus_score': row[3],
                    'task_name': row[4],
                    'category': row[5],
                    'focus_state': row[6],
                    'focus_confidence': row[7]
                })
            return results
        except Exception as e:
            logger.error(f"Error getting recent summaries: {e}")
            raise 