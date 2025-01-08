from datetime import datetime, timedelta
import sqlite3
from pathlib import Path
import logging
from typing import List, Dict, Optional, Tuple, Any
import sys
import json
from manager_mccode.models.screen_summary import ScreenSummary, Activity, FocusIndicators
from manager_mccode.config.settings import settings
from manager_mccode.services.analyzer import GeminiAnalyzer
from manager_mccode.models.focus_session import FocusSession, FocusTrigger
from manager_mccode.services.errors import DatabaseError
import asyncio

logger = logging.getLogger(__name__)

MIGRATIONS = [
    """
    -- Core activity tracking
    CREATE TABLE IF NOT EXISTS activity_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP NOT NULL,
        summary TEXT NOT NULL,
        window_title TEXT,
        active_app TEXT,
        focus_score FLOAT,
        batch_id INTEGER
    );

    -- Activity details for each snapshot
    CREATE TABLE IF NOT EXISTS activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        purpose TEXT,
        attention_level FLOAT NOT NULL,
        context_switches TEXT NOT NULL,
        workspace_organization TEXT NOT NULL,
        FOREIGN KEY (snapshot_id) REFERENCES activity_snapshots(id) ON DELETE CASCADE
    );

    -- Focus state tracking
    CREATE TABLE IF NOT EXISTS focus_states (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id INTEGER NOT NULL,
        state_type VARCHAR(50) NOT NULL,
        confidence FLOAT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (snapshot_id) REFERENCES activity_snapshots(id) ON DELETE CASCADE
    );

    -- Focus session tracking
    CREATE TABLE IF NOT EXISTS focus_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        start_time TIMESTAMP NOT NULL,
        end_time TIMESTAMP,
        duration_minutes INTEGER,
        activity_type TEXT NOT NULL,
        interruption_count INTEGER DEFAULT 0,
        context_switches INTEGER DEFAULT 0,
        attention_score FLOAT
    );

    -- Focus trigger tracking
    CREATE TABLE IF NOT EXISTS focus_triggers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        trigger_time TIMESTAMP NOT NULL,
        trigger_type TEXT NOT NULL,
        trigger_source TEXT NOT NULL,
        recovery_time_seconds INTEGER,
        FOREIGN KEY (session_id) REFERENCES focus_sessions(id)
    );

    -- Environment details for each snapshot
    CREATE TABLE IF NOT EXISTS environments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id INTEGER NOT NULL,
        environment TEXT NOT NULL,
        FOREIGN KEY (snapshot_id) REFERENCES activity_snapshots(id) ON DELETE CASCADE
    );

    -- Create indexes if they don't exist
    CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON activity_snapshots(timestamp);
    CREATE INDEX IF NOT EXISTS idx_activities_snapshot ON activities(snapshot_id);
    CREATE INDEX IF NOT EXISTS idx_focus_states_snapshot ON focus_states(snapshot_id);
    CREATE INDEX IF NOT EXISTS idx_focus_sessions_time ON focus_sessions(start_time);
    CREATE INDEX IF NOT EXISTS idx_environments_snapshot ON environments(snapshot_id);
    """
]

class DatabaseConnectionError(DatabaseError):
    """Exception raised when database connection fails"""
    pass

class QueryError(DatabaseError):
    """Exception raised when a database query fails"""
    pass

class DatabaseManager:
    def __init__(self, db_path=None):
        """Initialize database manager"""
        self.db_path = db_path or "manager_mccode.db"
        logger.info(f"Initialized DatabaseManager with db_path: {self.db_path}")
        self.initialize()

    def initialize(self):
        """Initialize database schema"""
        try:
            conn = self.get_connection()
            try:
                for migration in MIGRATIONS:
                    conn.executescript(migration)
                conn.commit()
                logger.info("Database initialization complete")
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise DatabaseError(f"Failed to initialize database: {e}")

    def get_connection(self):
        """Get a thread-local database connection"""
        # Create new connection for each thread
        if self.db_path != ":memory:":
            db_path = Path(self.db_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            db_path_str = str(db_path)
        else:
            db_path_str = self.db_path

        conn = sqlite3.connect(db_path_str)
        conn.execute("PRAGMA foreign_keys = ON")
        if self.db_path != ":memory:":
            conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    async def cleanup_old_data(self, days: Optional[int] = None) -> Tuple[int, int]:
        """Clean up old data from the database"""
        try:
            retention_days = days or settings.DATA_RETENTION_DAYS
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            # Run all database operations in a thread
            return await asyncio.to_thread(self._do_cleanup_with_connection, cutoff_date)
        except Exception as e:
            logger.error(f"Failed to clean up old data: {e}")
            raise DatabaseError(f"Data cleanup failed: {e}")

    def _do_cleanup_with_connection(self, cutoff_date: datetime) -> Tuple[int, int]:
        """Run cleanup with a fresh connection in the worker thread"""
        conn = self.get_connection()
        try:
            return self._do_cleanup(conn, cutoff_date)
        finally:
            conn.close()

    def _do_cleanup(self, conn: sqlite3.Connection, cutoff_date: datetime) -> Tuple[int, int]:
        """Internal method to perform the actual cleanup"""
        try:
            conn.execute("BEGIN TRANSACTION")
            
            # Get initial size
            initial_size = 0
            if self.db_path != ":memory:":
                initial_size = Path(self.db_path).stat().st_size

            # Delete old records
            cursor = conn.execute("""
                DELETE FROM activity_snapshots 
                WHERE timestamp < ?
            """, [cutoff_date])
            deleted = cursor.rowcount

            conn.commit()

            # Get final size
            final_size = 0
            if self.db_path != ":memory:":
                final_size = Path(self.db_path).stat().st_size
                space_reclaimed = initial_size - final_size
            else:
                space_reclaimed = 0

            return deleted, space_reclaimed

        except Exception as e:
            conn.rollback()
            raise e

    async def cleanup(self) -> None:
        """Cleanup database resources during shutdown"""
        try:
            # Run final cleanup of old data
            await self.cleanup_old_data()
            
            # Run optimizations in a thread
            await asyncio.to_thread(self._optimize_database_with_connection)
                
            logger.info("Database cleanup complete")
        except Exception as e:
            logger.error(f"Error during database cleanup: {e}")
            raise DatabaseError(f"Cleanup failed: {e}")

    def _optimize_database_with_connection(self) -> None:
        """Run optimizations with a fresh connection"""
        conn = self.get_connection()
        try:
            self._optimize_database(conn)
        finally:
            conn.close()

    def _optimize_database(self, conn: sqlite3.Connection) -> None:
        """Run database optimizations"""
        try:
            logger.info("Running database optimizations...")
            
            # Skip VACUUM for in-memory databases
            if self.db_path != ":memory:":
                conn.execute("PRAGMA optimize")
                conn.execute("ANALYZE")
                conn.execute("VACUUM")
            else:
                # Just run basic optimizations for in-memory
                conn.execute("PRAGMA optimize")
                conn.execute("ANALYZE")
            
            logger.info("Database optimizations complete")
        except Exception as e:
            logger.error(f"Failed to optimize database: {e}")
            raise DatabaseError(f"Optimization failed: {e}")

    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                # Get table statistics
                cursor.execute("""
                    SELECT
                        name,
                        (SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND tbl_name=m.name) as index_count,
                        (SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND tbl_name=m.name) as trigger_count
                    FROM sqlite_master m
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)
                
                tables = {}
                for table_name, index_count, trigger_count in cursor.fetchall():
                    # Get row count for each table
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    row_count = cursor.fetchone()[0]
                    
                    tables[table_name] = {
                        "row_count": row_count,
                        "index_count": index_count,
                        "trigger_count": trigger_count
                    }
                
                # Get time range info from activity_snapshots
                cursor.execute("""
                    SELECT
                        MIN(timestamp) as oldest,
                        MAX(timestamp) as newest,
                        COUNT(*) as total
                    FROM activity_snapshots
                """)
                
                time_range = cursor.fetchone()
                
                # Handle in-memory database size
                if self.db_path == ":memory:":
                    db_size = 0
                else:
                    db_size = Path(self.db_path).stat().st_size / (1024 * 1024)
                
                return {
                    "tables": tables,
                    "database_size_mb": db_size,
                    "time_range": {
                        "oldest": time_range[0] if time_range[0] else None,
                        "newest": time_range[1] if time_range[1] else None,
                        "total_records": time_range[2]
                    }
                }
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            raise DatabaseError(f"Failed to get database stats: {e}")

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
            cursor = self.conn.cursor()  # Use existing connection instead of creating new one
            
            # Debug logging
            logger.debug(f"Getting activity for past {hours} hours")
            
            # Simplified query that doesn't rely on relative time
            cursor.execute("""
                SELECT
                    a.timestamp,
                    a.summary,
                    f.state_type as focus_state,
                    f.confidence as focus_confidence,
                    act.name as activity_name,
                    act.category,
                    act.attention_level
                FROM activity_snapshots a
                LEFT JOIN focus_states f ON a.id = f.snapshot_id
                LEFT JOIN activities act ON a.id = act.snapshot_id
                ORDER BY a.timestamp DESC
                LIMIT 100
            """)
            
            results = []
            for row in cursor.fetchall():
                result = {
                    'timestamp': row[0],
                    'summary': row[1],
                    'focus_state': row[2],
                    'focus_confidence': row[3],
                    'activity_name': row[4],
                    'category': row[5],
                    'attention_level': row[6]
                }
                logger.debug(f"Found activity: {result}")
                results.append(result)
            
            logger.debug(f"Retrieved {len(results)} activities")
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
            cursor = self.conn.cursor()
            
            # Start transaction
            cursor.execute("BEGIN TRANSACTION")
            
            try:
                # Insert main snapshot
                cursor.execute("""
                    INSERT INTO activity_snapshots 
                    (timestamp, summary, focus_score)
                    VALUES (?, ?, ?)
                    RETURNING id
                """, (
                    summary.timestamp,
                    summary.summary,
                    0.0  # Default focus score
                ))
                
                snapshot_id = cursor.fetchone()[0]
                
                # Store activities
                for activity in summary.activities:
                    cursor.execute("""
                        INSERT INTO activities 
                        (snapshot_id, name, category, purpose, attention_level,
                         context_switches, workspace_organization)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        snapshot_id,
                        activity.name,
                        activity.category,
                        getattr(activity, 'purpose', ''),
                        activity.focus_indicators.attention_level,
                        activity.focus_indicators.context_switches,
                        activity.focus_indicators.workspace_organization
                    ))
                
                # Store focus state if context exists and has required attributes
                if hasattr(summary, 'context') and summary.context:
                    cursor.execute("""
                        INSERT INTO focus_states 
                        (snapshot_id, state_type, confidence)
                        VALUES (?, ?, ?)
                    """, (
                        snapshot_id,
                        summary.context.attention_state,
                        summary.context.confidence
                    ))
                
                cursor.execute("COMMIT")
                return snapshot_id
                
            except Exception as e:
                cursor.execute("ROLLBACK")
                raise e
                
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

    def get_recent_summaries(self, hours: int = 24) -> List[ScreenSummary]:
        """Get screen summaries from the last N hours"""
        try:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                # Calculate cutoff time
                cutoff = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
                logger.debug(f"Getting summaries since: {cutoff}")
                
                # Get summaries
                cursor.execute("""
                    SELECT COUNT(*) FROM activity_snapshots
                    WHERE timestamp >= ?
                """, [cutoff])
                count = cursor.fetchone()[0]
                logger.debug(f"Found {count} summaries in time range")
                
                cursor.execute("""
                    SELECT * FROM activity_snapshots
                    WHERE timestamp >= ?
                    ORDER BY timestamp DESC
                """, [cutoff])
                
                summaries = []
                for row in cursor.fetchall():
                    logger.debug(f"Processing snapshot {row[0]} from {row[1]}")
                    
                    # Get associated activities
                    cursor.execute("""
                        SELECT COUNT(*) FROM activities
                        WHERE snapshot_id = ?
                    """, [row[0]])
                    activity_count = cursor.fetchone()[0]
                    logger.debug(f"Found {activity_count} activities for snapshot {row[0]}")
                    
                    cursor.execute("""
                        SELECT * FROM activities
                        WHERE snapshot_id = ?
                    """, [row[0]])
                    
                    activities = []
                    for activity_row in cursor.fetchall():
                        activity = Activity(
                            name=activity_row[2],
                            category=activity_row[3],
                            purpose=activity_row[4],
                            focus_indicators=FocusIndicators(
                                attention_level=activity_row[5],
                                context_switches=activity_row[6],
                                workspace_organization=activity_row[7]
                            )
                        )
                        activities.append(activity)
                    
                    summary = ScreenSummary(
                        timestamp=datetime.fromisoformat(row[1].replace(' ', 'T')),
                        summary=row[2],
                        activities=activities
                    )
                    summaries.append(summary)
                
                logger.info(f"Retrieved {len(summaries)} summaries from database")
                return summaries
                
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"Error getting recent summaries: {e}")
            raise DatabaseError(f"Failed to get recent summaries: {e}")

    def get_focus_metrics(self, hours: int = 24) -> Dict:
        """Get focus metrics for the specified time period"""
        try:
            cursor = self.conn.cursor()
            
            # Get activities for analysis
            cursor.execute("""
                SELECT
                    a.name,
                    a.category,
                    a.attention_level,
                    a.context_switches,
                    a.workspace_organization,
                    s.timestamp
                FROM activity_snapshots s
                JOIN activities a ON s.id = a.snapshot_id
                WHERE s.timestamp >= datetime('now', ?)
                ORDER BY s.timestamp DESC
            """, (f'-{hours} hours',))
            
            activities = [
                Activity(
                    name=row[0],
                    category=row[1],
                    purpose="",  # Not used for metrics
                    focus_indicators=FocusIndicators(
                        attention_level=row[2],
                        context_switches=row[3],
                        workspace_organization=row[4]
                    ),
                    timestamp=datetime.fromisoformat(row[5].replace(' ', 'T'))  # Add timestamp
                ) for row in cursor.fetchall()
            ]
            
            if not activities:
                return {
                    'switches_per_hour': 0,
                    'max_focus_duration': 0,
                    'common_triggers': [],
                    'avg_recovery_time': 0,
                    'recovery_activities': [],
                    'environmental_impacts': [],
                    'recommendations': ["Not enough data to generate recommendations"]
                }
                
            # Use analyzer to get metrics
            analyzer = GeminiAnalyzer()
            metrics = analyzer.analyze_focus_patterns(activities)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to get focus metrics: {e}")
            raise DatabaseError(f"Failed to get focus metrics: {e}") 

    def get_snapshots_between(self, start: datetime, end: datetime) -> List[Dict]:
        """Get snapshots between two timestamps"""
        try:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        id,
                        timestamp,
                        summary,
                        window_title,
                        active_app,
                        COALESCE(focus_score, 0.0) as focus_score,
                        batch_id
                    FROM activity_snapshots 
                    WHERE timestamp BETWEEN ? AND ?
                    ORDER BY timestamp DESC
                """, [start.strftime('%Y-%m-%d %H:%M:%S'), 
                     end.strftime('%Y-%m-%d %H:%M:%S')])
                
                snapshots = []
                for row in cursor.fetchall():
                    snapshot = {
                        "id": row[0],
                        "timestamp": datetime.fromisoformat(row[1].replace(' ', 'T')),
                        "summary": row[2],
                        "window_title": row[3] or "",
                        "active_app": row[4] or "",
                        "focus_score": float(row[5]),  # Ensure float
                        "batch_id": row[6],
                        "activities": []  # Initialize empty activities list
                    }
                    
                    # Get associated activities
                    cursor.execute("""
                        SELECT 
                            name,
                            category,
                            purpose,
                            COALESCE(attention_level, 0.0) as attention_level,
                            COALESCE(context_switches, 'low') as context_switches,
                            COALESCE(workspace_organization, 'neutral') as workspace_organization
                        FROM activities
                        WHERE snapshot_id = ?
                    """, [row[0]])
                    
                    activities = []
                    for activity_row in cursor.fetchall():
                        activity = {
                            "name": activity_row[0] or "unknown",
                            "category": activity_row[1] or "unknown",
                            "purpose": activity_row[2] or "",
                            "attention_level": float(activity_row[3]),
                            "context_switches": activity_row[4],
                            "workspace_organization": activity_row[5]
                        }
                        activities.append(activity)
                    
                    snapshot["activities"] = activities
                    snapshots.append(snapshot)
                
                return snapshots
                
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"Error getting snapshots: {e}")
            return []

    def get_activities_between(self, start: datetime, end: datetime) -> List[Dict]:
        """Get all activities between two timestamps"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    a.id,
                    a.name,
                    a.category,
                    a.attention_level,
                    a.context_switches,
                    a.workspace_organization
                FROM activities a
                JOIN activity_snapshots s ON a.snapshot_id = s.id
                WHERE s.timestamp BETWEEN ? AND ?
            """, (start, end))
            
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"Error getting activities: {e}")
            raise DatabaseError(f"Failed to get activities: {e}")

    def get_focus_states_between(self, start: datetime, end: datetime) -> List[Dict]:
        """Get focus states between two timestamps"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    s.id,
                    CASE 
                        WHEN AVG(a.attention_level) >= 70 THEN 'focused'
                        WHEN AVG(a.attention_level) <= 45 THEN 'scattered'
                        ELSE 'neutral'
                    END as state_type,
                    AVG(a.attention_level) as confidence
                FROM activity_snapshots s
                LEFT JOIN activities a ON s.id = a.snapshot_id
                WHERE s.timestamp BETWEEN ? AND ?
                GROUP BY s.id
            """, (start, end))
            
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"Error getting focus states: {e}")
            raise DatabaseError(f"Failed to get focus states: {e}") 

    def store_focus_session(self, session: FocusSession) -> None:
        """Store a focus session in the database"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO focus_sessions (
                    start_time,
                    end_time,
                    duration_minutes,
                    activity_type,
                    interruption_count,
                    context_switches,
                    attention_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                session.start_time.strftime('%Y-%m-%d %H:%M:%S'),  # Format datetime
                session.end_time.strftime('%Y-%m-%d %H:%M:%S') if session.end_time else None,
                session.duration_minutes,
                session.activity_type,
                0,  # interruption_count - will implement later
                session.context_switches,
                session.attention_score
            ))
            
            session_id = cursor.lastrowid
            
            # Store any triggers
            for trigger in session.triggers:
                cursor.execute("""
                    INSERT INTO focus_triggers (
                        session_id,
                        trigger_time,
                        trigger_type,
                        trigger_source,
                        recovery_time_seconds
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    session_id,
                    trigger.timestamp.strftime('%Y-%m-%d %H:%M:%S'),  # Format datetime
                    trigger.type,
                    trigger.source,
                    trigger.recovery_time
                ))
            
            self.conn.commit()
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to store focus session: {e}")
            raise DatabaseError(f"Failed to store focus session: {e}") 

    def get_focus_sessions(self, hours: int = 24) -> List[FocusSession]:
        """Get focus sessions from the last N hours"""
        try:
            cursor = self.conn.cursor()
            
            # Calculate cutoff time
            cutoff = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute("""
                SELECT 
                    id,
                    start_time,
                    end_time,
                    duration_minutes,
                    activity_type,
                    context_switches,
                    attention_score
                FROM focus_sessions
                WHERE start_time >= ?
                ORDER BY start_time DESC
            """, (cutoff,))
            
            sessions = []
            for row in cursor.fetchall():
                session = FocusSession(
                    start_time=datetime.fromisoformat(row[1].replace(' ', 'T')),
                    activity_type=row[4],
                    end_time=datetime.fromisoformat(row[2].replace(' ', 'T')) if row[2] else None,
                    duration_minutes=row[3],
                    context_switches=row[5],
                    attention_score=row[6]
                )
                sessions.append(session)
                
            return sessions
            
        except Exception as e:
            logger.error(f"Failed to get focus sessions: {e}")
            raise DatabaseError(f"Failed to get focus sessions: {e}") 

    def store_summaries(self, summaries: List[ScreenSummary]) -> None:
        """Store screen summaries in the database"""
        try:
            conn = self.get_connection()
            try:
                conn.execute("BEGIN TRANSACTION")
                
                for summary in summaries:
                    # Debug log the summary being stored
                    logger.debug(f"Storing summary from {summary.timestamp}: {summary.summary[:100]}...")
                    
                    cursor = conn.execute("""
                        INSERT INTO activity_snapshots 
                        (timestamp, summary) 
                        VALUES (?, ?)
                        """, (
                            summary.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                            summary.summary
                        )
                    )
                    snapshot_id = cursor.lastrowid
                    
                    # Debug log each activity
                    for activity in summary.activities:
                        logger.debug(f"Storing activity: {activity.name} for snapshot {snapshot_id}")
                        conn.execute("""
                            INSERT INTO activities 
                            (snapshot_id, name, category, purpose, 
                             attention_level, context_switches, workspace_organization)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (
                                snapshot_id,
                                activity.name,
                                activity.category,
                                activity.purpose,
                                activity.focus_indicators.attention_level,
                                activity.focus_indicators.context_switches,
                                activity.focus_indicators.workspace_organization
                            )
                        )
                
                conn.commit()
                logger.info(f"Stored {len(summaries)} summaries in database")
                
                # Verify storage
                cursor = conn.execute("SELECT COUNT(*) FROM activity_snapshots")
                total_snapshots = cursor.fetchone()[0]
                logger.info(f"Total snapshots in database: {total_snapshots}")
                
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"Failed to store summaries: {e}")
            raise DatabaseError(f"Failed to store summaries: {e}") 