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

    -- Task segments for continuous work periods
    CREATE TABLE task_segments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        start_time TIMESTAMP NOT NULL,
        end_time TIMESTAMP,
        task_name TEXT NOT NULL,
        category TEXT NOT NULL,
        focus_level FLOAT  -- Aggregate focus score for the segment
    );

    -- Environment details for each snapshot
    CREATE TABLE environments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id INTEGER NOT NULL,
        window_count INTEGER,
        tab_count INTEGER,
        active_displays INTEGER,
        noise_level TEXT,  -- low, medium, high
        interruption_probability FLOAT,
        FOREIGN KEY (snapshot_id) REFERENCES activity_snapshots(id) ON DELETE CASCADE
    );

    -- Activity details for each snapshot
    CREATE TABLE activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id INTEGER NOT NULL,
        task_segment_id INTEGER,
        activity_type TEXT NOT NULL,
        category TEXT NOT NULL,
        attention_level FLOAT NOT NULL,
        context_switches TEXT NOT NULL,  -- low, medium, high
        workspace_organization TEXT NOT NULL,  -- organized, mixed, scattered
        start_time TIMESTAMP,
        duration INTEGER,  -- in seconds
        FOREIGN KEY (snapshot_id) REFERENCES activity_snapshots(id) ON DELETE CASCADE,
        FOREIGN KEY (task_segment_id) REFERENCES task_segments(id) ON DELETE SET NULL
    );

    -- Indexes for performance
    CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp 
        ON activity_snapshots(timestamp);
    
    CREATE INDEX IF NOT EXISTS idx_task_segments_time 
        ON task_segments(start_time, end_time);
    
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

    def _optimize_database(self) -> None:
        """Run database optimizations
        
        This includes:
        - Analyzing tables for better query planning
        - Running VACUUM to reclaim space
        - Updating statistics
        """
        try:
            logger.info("Running database optimizations...")
            self.conn.execute("PRAGMA optimize")
            self.conn.execute("ANALYZE")
            self.conn.execute("VACUUM")
            logger.info("Database optimizations complete")
        except Exception as e:
            logger.error(f"Failed to optimize database: {e}")
            raise DatabaseError(f"Optimization failed: {e}")

    def cleanup_old_data(self, days: Optional[int] = None) -> Tuple[int, int]:
        """Remove data older than specified days
        
        Args:
            days: Days of data to retain, defaults to settings.DB_RETENTION_DAYS
            
        Returns:
            Tuple[int, int]: (records deleted, space reclaimed in bytes)
            
        Raises:
            DatabaseError: If cleanup fails
        """
        retention_days = days or settings.DB_RETENTION_DAYS
        cutoff = datetime.now() - timedelta(days=retention_days)
        
        try:
            # Start transaction
            self.conn.execute("BEGIN TRANSACTION")
            
            # Get initial database size
            initial_size = Path(self.db_path).stat().st_size
            
            # Delete old records from all tables
            cursor = self.conn.execute("""
                DELETE FROM activity_snapshots 
                WHERE timestamp < ?
            """, [cutoff])
            deleted_count = cursor.rowcount
            
            # Optimize after large deletions
            self._optimize_database()
            
            # Calculate space reclaimed
            final_size = Path(self.db_path).stat().st_size
            space_reclaimed = initial_size - final_size
            
            self.conn.commit()
            logger.info(
                f"Cleaned up {deleted_count} records older than {retention_days} days. "
                f"Reclaimed {space_reclaimed/1024/1024:.1f}MB"
            )
            
            return deleted_count, space_reclaimed
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to clean up old data: {e}")
            raise DatabaseError(f"Data cleanup failed: {e}")

    def get_database_stats(self) -> Dict:
        """Get database statistics and health metrics
        
        Returns:
            Dict containing:
            - Table row counts
            - Database size
            - Index sizes
            - Last optimization time
            - Data retention metrics
        """
        try:
            stats = {}
            
            # Get table statistics
            cursor = self.conn.execute("""
                SELECT 
                    name,
                    (SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND tbl_name=m.name) as index_count,
                    (SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND tbl_name=m.name) as trigger_count
                FROM sqlite_master m
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """)
            
            tables = {}
            for table_name, index_count, trigger_count in cursor.fetchall():
                # Get row count for table
                count_cursor = self.conn.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = count_cursor.fetchone()[0]
                
                tables[table_name] = {
                    'row_count': row_count,
                    'index_count': index_count,
                    'trigger_count': trigger_count
                }
            
            stats['tables'] = tables
            
            # Get database file size
            stats['database_size_mb'] = Path(self.db_path).stat().st_size / 1024 / 1024
            
            # Get oldest and newest records
            cursor = self.conn.execute("""
                SELECT 
                    MIN(timestamp) as oldest,
                    MAX(timestamp) as newest,
                    COUNT(*) as total
                FROM activity_snapshots
            """)
            time_stats = cursor.fetchone()
            stats['time_range'] = {
                'oldest': time_stats[0],
                'newest': time_stats[1],
                'total_records': time_stats[2]
            }
            
            # Get index statistics
            cursor = self.conn.execute("""
                SELECT name, sql 
                FROM sqlite_master 
                WHERE type='index' AND sql IS NOT NULL
            """)
            stats['indexes'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            return stats
            
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
            try:
                self._optimize_database()
                self.conn.close()
                logger.info("Database connection closed.")
            except Exception as e:
                logger.error(f"Error closing database: {e}")

    def store_summary(self, summary: ScreenSummary):
        """Store a summary in the database and return its ID
        
        This method handles the complete storage of a screen summary, including:
        - The main activity snapshot
        - Focus state information
        - Environmental details
        - Activity details
        - Task segment updates
        
        All operations are performed in a single transaction for consistency.
        """
        try:
            self.conn.execute("BEGIN TRANSACTION")
            try:
                # 1. Insert main snapshot
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

                # 2. Store focus state if available
                if summary.context and summary.context.attention_state:
                    self.conn.execute("""
                        INSERT INTO focus_states (
                            snapshot_id, state_type, confidence
                        ) VALUES (?, ?, ?)
                    """, [
                        snapshot_id,
                        summary.context.attention_state,
                        summary.context.confidence
                    ])

                # 3. Store environment details
                if summary.context and summary.context.environment:
                    # Environment is stored as a string in the model
                    env_data = json.loads(summary.context.environment)
                    self.conn.execute("""
                        INSERT INTO environments (
                            snapshot_id, window_count, tab_count, 
                            active_displays, noise_level, interruption_probability
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, [
                        snapshot_id,
                        env_data.get('window_count', 0),
                        env_data.get('tab_count', 0),
                        env_data.get('active_displays', 1),
                        env_data.get('noise_level', 'medium'),
                        env_data.get('interruption_probability', 0.5)
                    ])

                # 4. Update task segments and store activities
                if summary.context and summary.context.primary_task:
                    task_segment_id = self._update_task_segments(summary)
                    
                    # Store activities with reference to task segment
                    if summary.activities:
                        for activity in summary.activities:
                            self.conn.execute("""
                                INSERT INTO activities (
                                    snapshot_id, task_segment_id, activity_type,
                                    category, attention_level, context_switches,
                                    workspace_organization, start_time, duration
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, [
                                snapshot_id,
                                task_segment_id,
                                activity.name,  # Using name as activity_type
                                activity.category,
                                float(activity.focus_indicators.attention_level) / 100.0,
                                activity.focus_indicators.context_switches,
                                activity.focus_indicators.workspace_organization,
                                summary.timestamp,  # Using summary timestamp
                                None  # Duration not in model
                            ])

                self.conn.commit()
                return snapshot_id

            except Exception as e:
                self.conn.rollback()
                raise e

        except Exception as e:
            logger.error(f"Failed to store summary: {str(e)}")
            raise

    def _calculate_focus_score(self, summary: ScreenSummary) -> float:
        """Calculate a focus score from the summary using weighted components
        
        Weights:
        - Attention level: 50% (direct measure of focus)
        - Context switches: 30% (impact on task continuity)
        - Workspace organization: 20% (environmental factor)
        
        Base attention states are also more nuanced:
        - focused: 0.85-1.0
        - transitioning: 0.4-0.7
        - scattered: 0.1-0.4
        """
        try:
            # Base score from attention state with randomized variation
            # This adds some natural variation within each state
            import random
            base_ranges = {
                'focused': (0.85, 1.0),
                'transitioning': (0.4, 0.7),
                'scattered': (0.1, 0.4)
            }
            base_range = base_ranges.get(summary.context.attention_state, (0.3, 0.6))
            base_score = random.uniform(*base_range)

            # Adjust based on activities with weights
            activity_scores = []
            for activity in summary.activities:
                focus_indicators = activity.focus_indicators
                
                # Convert string indicators to numeric scores
                attention_level = float(focus_indicators.attention_level) / 100.0
                
                context_switches = {
                    'low': 0.9,    # Minimal interruption
                    'medium': 0.6,  # Some task switching
                    'high': 0.3    # Frequent switching
                }.get(focus_indicators.context_switches, 0.6)
                
                organization = {
                    'organized': 0.9,   # Clear structure
                    'mixed': 0.6,       # Some clutter
                    'scattered': 0.3    # Disorganized
                }.get(focus_indicators.workspace_organization, 0.6)
                
                # Apply weights to each component
                weighted_score = (
                    attention_level * 0.5 +      # 50% weight
                    context_switches * 0.3 +     # 30% weight
                    organization * 0.2           # 20% weight
                )
                activity_scores.append(weighted_score)

            # Combine base score with weighted activity scores
            if activity_scores:
                # Base score gets 40% weight, activity scores get 60%
                final_score = base_score * 0.4 + (sum(activity_scores) / len(activity_scores)) * 0.6
                
                # Add small random variation to avoid repetitive scores
                variation = random.uniform(-0.05, 0.05)
                final_score = max(0.0, min(1.0, final_score + variation))
                
                return round(final_score, 2)
            
            return round(base_score, 2)

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