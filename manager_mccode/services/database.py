from datetime import datetime, timedelta
import sqlite3
from pathlib import Path
import logging
from typing import List, Dict, Optional, Tuple
import sys
import json
from manager_mccode.models.screen_summary import ScreenSummary
from manager_mccode.config.settings import settings

logger = logging.getLogger(__name__)

MIGRATIONS = [
    """
    -- initial_schema
    DROP TABLE IF EXISTS activity_snapshots;
    DROP TABLE IF EXISTS focus_states;
    DROP TABLE IF EXISTS task_segments;
    DROP TABLE IF EXISTS activities;
    DROP TABLE IF EXISTS environments;

    -- Core activity tracking
    CREATE TABLE activity_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP NOT NULL,
        summary TEXT NOT NULL,
        window_title TEXT,
        active_app TEXT,
        focus_score FLOAT,
        batch_id INTEGER
    );

    -- Focus state tracking
    CREATE TABLE focus_states (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id INTEGER NOT NULL,
        state_type VARCHAR(50) NOT NULL,  -- focused, transitioning, scattered
        confidence FLOAT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (snapshot_id) REFERENCES activity_snapshots(id) ON DELETE CASCADE
    );

    -- Environment details for each snapshot
    CREATE TABLE environments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id INTEGER NOT NULL,
        environment TEXT NOT NULL,  -- Changed to store environment as text
        FOREIGN KEY (snapshot_id) REFERENCES activity_snapshots(id) ON DELETE CASCADE
    );

    -- Activity details for each snapshot
    CREATE TABLE activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id INTEGER NOT NULL,
        activity_type TEXT NOT NULL,
        category TEXT NOT NULL,
        attention_level FLOAT NOT NULL,
        context_switches TEXT NOT NULL,  -- low, medium, high
        workspace_organization TEXT NOT NULL,  -- organized, mixed, scattered
        FOREIGN KEY (snapshot_id) REFERENCES activity_snapshots(id) ON DELETE CASCADE
    );

    -- Indexes for performance
    CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp 
        ON activity_snapshots(timestamp);
    
    CREATE INDEX IF NOT EXISTS idx_activities_snapshot 
        ON activities(snapshot_id);
    
    CREATE INDEX IF NOT EXISTS idx_focus_states_snapshot 
        ON focus_states(snapshot_id);
    
    CREATE INDEX IF NOT EXISTS idx_environments_snapshot 
        ON environments(snapshot_id);
    """
]

class DatabaseError(Exception):
    """Base exception for database-related errors"""
    pass

class DatabaseManager:
    def __init__(self, db_path=None):
        """Initialize database manager
        
        Args:
            db_path: Path to database file, or ":memory:" for in-memory database
        """
        self.db_path = db_path or settings.DEFAULT_DB_PATH
        logger.info(f"Initialized DatabaseManager with db_path: {self.db_path}")
        self.conn = None
        self.initialize()

    def get_connection(self):
        """Get a database connection, creating it if needed"""
        if self.conn is None:
            # Create new connection if none exists
            if self.db_path != ":memory:":
                db_path = Path(self.db_path)
                db_path.parent.mkdir(parents=True, exist_ok=True)
                db_path_str = str(db_path)
            else:
                db_path_str = self.db_path

            self.conn = sqlite3.connect(db_path_str)
            # Enable foreign key support
            self.conn.execute("PRAGMA foreign_keys = ON")
            # Enable WAL mode for better concurrency
            self.conn.execute("PRAGMA journal_mode = WAL")
            # Set synchronous mode for better performance while maintaining safety
            self.conn.execute("PRAGMA synchronous = NORMAL")
            # Enable memory-mapped I/O for better performance
            self.conn.execute("PRAGMA mmap_size = 30000000000")

        return self.conn

    def _optimize_database(self) -> None:
        """Run database optimizations"""
        try:
            logger.info("Running database optimizations...")
            
            # Skip VACUUM for in-memory databases
            if self.db_path != ":memory:":
                self.conn.execute("PRAGMA optimize")
                self.conn.execute("ANALYZE")
                self.conn.execute("VACUUM")
            else:
                # Just run basic optimizations for in-memory
                self.conn.execute("PRAGMA optimize")
                self.conn.execute("ANALYZE")
            
            logger.info("Database optimizations complete")
        except Exception as e:
            logger.error(f"Failed to optimize database: {e}")
            raise DatabaseError(f"Optimization failed: {e}")

    def cleanup_old_data(self, days: Optional[int] = None) -> Tuple[int, int]:
        """Remove data older than specified days"""
        retention_days = days or settings.DB_RETENTION_DAYS
        cutoff = datetime.now() - timedelta(days=retention_days)

        try:
            # Start transaction
            self.conn.execute("BEGIN TRANSACTION")

            # Get initial size (skip for in-memory database)
            initial_size = 0
            if self.db_path != ":memory:":
                initial_size = Path(self.db_path).stat().st_size

            # Delete old records
            cursor = self.conn.execute("""
                DELETE FROM activity_snapshots 
                WHERE timestamp < ?
            """, [cutoff])
            deleted = cursor.rowcount

            # Get final size (skip for in-memory database)
            final_size = 0
            if self.db_path != ":memory:":
                self.conn.commit()  # Commit to get accurate size
                final_size = Path(self.db_path).stat().st_size
                space_reclaimed = initial_size - final_size
            else:
                space_reclaimed = 0  # Can't measure for in-memory

            return deleted, space_reclaimed

        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to clean up old data: {e}")
            raise DatabaseError(f"Data cleanup failed: {e}")

    def get_database_stats(self) -> Dict:
        """Get database statistics"""
        try:
            cursor = self.conn.execute("""
                SELECT 
                    COUNT(*) as total_records,
                    MIN(timestamp) as earliest_record,
                    MAX(timestamp) as latest_record
                FROM activity_snapshots
            """)
            snapshot_stats = dict(zip(['total_records', 'earliest_record', 'latest_record'], cursor.fetchone()))
            
            # Get table info
            cursor = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            # Get database size (0 for in-memory)
            db_size = 0
            if self.db_path != ":memory:":
                db_size = Path(self.db_path).stat().st_size / (1024 * 1024)  # Convert to MB
            
            return {
                'tables': tables,
                'database_size_mb': db_size,
                'time_range': snapshot_stats
            }
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            raise DatabaseError(f"Stats collection failed: {e}")

    def verify_database_integrity(self) -> bool:
        """Run integrity check on the database
        
        Returns:
            bool: True if database is healthy
            
        Raises:
            DatabaseError: If integrity check fails
        """
        try:
            cursor = self.conn.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]
            
            if result != "ok":
                logger.error(f"Database integrity check failed: {result}")
                return False
                
            cursor = self.conn.execute("PRAGMA foreign_key_check")
            if cursor.fetchone() is not None:
                logger.error("Foreign key violations found")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to verify database integrity: {e}")
            raise DatabaseError(f"Integrity check failed: {e}")

    def initialize(self):
        """Initialize the database and run migrations"""
        try:
            logger.info(f"Connecting to database at path: {self.db_path}")
            
            # Only create directories if not using in-memory database
            if self.db_path != ":memory:":
                db_path = Path(self.db_path)
                db_path.parent.mkdir(parents=True, exist_ok=True)
                db_path_str = str(db_path)
            else:
                db_path_str = self.db_path

            self.conn = sqlite3.connect(db_path_str)
            # Enable foreign key support
            self.conn.execute("PRAGMA foreign_keys = ON")
            # Enable WAL mode for better concurrency
            self.conn.execute("PRAGMA journal_mode = WAL")
            # Set synchronous mode for better performance while maintaining safety
            self.conn.execute("PRAGMA synchronous = NORMAL")
            # Enable memory-mapped I/O for better performance
            self.conn.execute("PRAGMA mmap_size = 30000000000")
            
            logger.info("Successfully connected to SQLite.")
            
            # Run migrations in a transaction
            self.conn.execute("BEGIN TRANSACTION")
            try:
                self._run_migrations()
                self._optimize_database()
                self.conn.commit()
                logger.info("Database initialization complete")
            except Exception as e:
                self.conn.rollback()
                raise e
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}", exc_info=True)
            raise DatabaseError(f"Initialization failed: {e}")

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

    def get_recent_activity(self, hours: int = 1) -> List[Dict]:
        """Get recent activity with focus states"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    a.timestamp,
                    a.summary,
                    f.state_type as focus_state,
                    f.confidence as focus_confidence,
                    act.activity_type,
                    act.category,
                    act.attention_level
                FROM activity_snapshots a
                LEFT JOIN focus_states f ON a.id = f.snapshot_id
                LEFT JOIN activities act ON a.id = act.snapshot_id
                WHERE a.timestamp > datetime('now', ?) 
                ORDER BY a.timestamp DESC
            """, (f'-{hours} hours',))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'timestamp': row[0],
                    'summary': row[1],
                    'focus_state': row[2],
                    'focus_confidence': row[3],
                    'activity_type': row[4],
                    'category': row[5],
                    'attention_level': row[6]
                })
            
            return results
                
        except Exception as e:
            logger.error(f"Failed to get recent activity: {e}")
            raise DatabaseError(f"Failed to get recent activity: {e}")

    def close(self):
        """Close database connection"""
        if self.conn:
            try:
                self._optimize_database()
                self.conn.close()
                logger.info("Database connection closed.")
            except Exception as e:
                logger.error(f"Error closing database: {e}")

    def store_summary(self, summary: ScreenSummary) -> int:
        """Store a screen summary in the database"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Insert main snapshot
            cursor.execute("""
                INSERT INTO activity_snapshots 
                (timestamp, summary, focus_score)
                VALUES (?, ?, ?)
                RETURNING id
            """, (
                summary.timestamp,
                summary.summary,
                summary.context.confidence if summary.context else 0.0
            ))
            
            snapshot_id = cursor.fetchone()[0]
            
            # Store focus state
            if summary.context and summary.context.attention_state:
                cursor.execute("""
                    INSERT INTO focus_states 
                    (snapshot_id, state_type, confidence)
                    VALUES (?, ?, ?)
                """, (
                    snapshot_id,
                    summary.context.attention_state,
                    summary.context.confidence
                ))
            
            # Store activities
            for activity in summary.activities:
                cursor.execute("""
                    INSERT INTO activities 
                    (snapshot_id, activity_type, category, attention_level,
                     context_switches, workspace_organization)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    snapshot_id,
                    activity.name,
                    activity.category,
                    activity.focus_indicators.attention_level,
                    activity.focus_indicators.context_switches,
                    activity.focus_indicators.workspace_organization
                ))
            
            conn.commit()
            return snapshot_id
                
        except Exception as e:
            logger.error(f"Failed to store summary: {e}")
            raise DatabaseError(f"Failed to store summary: {e}")

    def _calculate_focus_score(self, summary: ScreenSummary) -> float:
        """Calculate a focus score from the summary"""
        try:
            if not summary.context:
                raise DatabaseError("Missing context in summary")

            # Rest of the function...

        except Exception as e:
            logger.error(f"Error calculating focus score: {e}")
            raise DatabaseError(f"Failed to calculate focus score: {e}")

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
        """Get the most recent summaries with their associated focus states"""
        try:
            cursor = self.conn.execute("""
                SELECT 
                    a.id as id,
                    datetime(a.timestamp) as timestamp,
                    a.summary as summary,
                    a.focus_score as focus_score,
                    f.state_type as focus_state,
                    f.confidence as focus_confidence,
                    e.environment as environment
                FROM activity_snapshots a
                LEFT JOIN focus_states f ON a.id = f.snapshot_id
                LEFT JOIN environments e ON a.id = e.snapshot_id
                ORDER BY a.timestamp DESC
                LIMIT ?
            """, [limit])
            
            # Convert rows to dictionaries using column names
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting recent summaries: {e}")
            raise DatabaseError(f"Failed to get recent summaries: {e}") 