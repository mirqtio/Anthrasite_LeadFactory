"""
Advanced Test Monitoring Dashboard for CI Pipeline.

Collects and visualizes test reliability metrics across the CI pipeline,
implementing comprehensive monitoring as specified in Task 14.
"""

import json
import logging
import sqlite3
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class TestExecution:
    """Represents a single test execution."""

    test_id: str
    test_name: str
    test_suite: str
    status: str  # "passed", "failed", "skipped", "error"
    duration: float  # seconds
    timestamp: datetime
    build_id: str
    branch: str
    commit_hash: str
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    retry_count: int = 0


@dataclass
class TestMetrics:
    """Aggregated metrics for a test."""

    test_id: str
    test_name: str
    test_suite: str
    pass_rate: float  # 0.0 to 1.0
    avg_duration: float
    flakiness_score: float  # 0.0 to 1.0 (higher = more flaky)
    execution_count: int
    last_execution: datetime
    trend: str  # "improving", "stable", "degrading"
    reliability_grade: str  # "A", "B", "C", "D", "F"


@dataclass
class TestSuiteMetrics:
    """Aggregated metrics for a test suite."""

    suite_name: str
    total_tests: int
    pass_rate: float
    avg_duration: float
    flaky_tests: int
    critical_failures: int
    last_run: datetime
    health_status: str  # "healthy", "warning", "critical"


class TestMetricsCollector:
    """Collects and processes test execution data."""

    def __init__(self, db_path: str = "test_metrics.db"):
        self.db_path = db_path
        self._init_database()
        self._lock = threading.Lock()

    def _init_database(self):
        """Initialize SQLite database for test metrics."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS test_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_id TEXT NOT NULL,
                    test_name TEXT NOT NULL,
                    test_suite TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    build_id TEXT NOT NULL,
                    branch TEXT NOT NULL,
                    commit_hash TEXT NOT NULL,
                    error_message TEXT,
                    stack_trace TEXT,
                    retry_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS test_metrics_cache (
                    test_id TEXT PRIMARY KEY,
                    test_name TEXT NOT NULL,
                    test_suite TEXT NOT NULL,
                    pass_rate REAL NOT NULL,
                    avg_duration REAL NOT NULL,
                    flakiness_score REAL NOT NULL,
                    execution_count INTEGER NOT NULL,
                    last_execution TEXT NOT NULL,
                    trend TEXT NOT NULL,
                    reliability_grade TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_test_executions_test_id
                ON test_executions(test_id)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_test_executions_timestamp
                ON test_executions(timestamp)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_test_executions_suite
                ON test_executions(test_suite)
            """
            )

    def record_test_execution(self, execution: TestExecution):
        """Record a single test execution."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO test_executions
                    (test_id, test_name, test_suite, status, duration, timestamp,
                     build_id, branch, commit_hash, error_message, stack_trace, retry_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        execution.test_id,
                        execution.test_name,
                        execution.test_suite,
                        execution.status,
                        execution.duration,
                        execution.timestamp.isoformat(),
                        execution.build_id,
                        execution.branch,
                        execution.commit_hash,
                        execution.error_message,
                        execution.stack_trace,
                        execution.retry_count,
                    ),
                )

        # Update metrics cache asynchronously
        self._update_test_metrics_cache(execution.test_id)

    def _update_test_metrics_cache(self, test_id: str):
        """Update cached metrics for a specific test."""
        metrics = self._calculate_test_metrics(test_id)
        if metrics:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO test_metrics_cache
                    (test_id, test_name, test_suite, pass_rate, avg_duration,
                     flakiness_score, execution_count, last_execution, trend,
                     reliability_grade, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                    (
                        metrics.test_id,
                        metrics.test_name,
                        metrics.test_suite,
                        metrics.pass_rate,
                        metrics.avg_duration,
                        metrics.flakiness_score,
                        metrics.execution_count,
                        metrics.last_execution.isoformat(),
                        metrics.trend,
                        metrics.reliability_grade,
                    ),
                )

    def _calculate_test_metrics(
        self, test_id: str, days: int = 30
    ) -> Optional[TestMetrics]:
        """Calculate metrics for a specific test over the last N days."""
        cutoff_date = datetime.now() - timedelta(days=days)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT test_name, test_suite, status, duration, timestamp
                FROM test_executions
                WHERE test_id = ? AND timestamp >= ?
                ORDER BY timestamp ASC
            """,
                (test_id, cutoff_date.isoformat()),
            )

            rows = cursor.fetchall()

            if not rows:
                return None

            test_name = rows[0][0]
            test_suite = rows[0][1]

            # Calculate basic metrics
            total_executions = len(rows)
            passed_executions = sum(1 for row in rows if row[2] == "passed")
            pass_rate = (
                passed_executions / total_executions if total_executions > 0 else 0.0
            )

            durations = [row[3] for row in rows if row[3] is not None]
            avg_duration = statistics.mean(durations) if durations else 0.0

            # Calculate flakiness score
            flakiness_score = self._calculate_flakiness_score(rows)

            # Determine trend
            trend = self._calculate_trend(rows)

            # Calculate reliability grade
            reliability_grade = self._calculate_reliability_grade(
                pass_rate, flakiness_score
            )

            return TestMetrics(
                test_id=test_id,
                test_name=test_name,
                test_suite=test_suite,
                pass_rate=pass_rate,
                avg_duration=avg_duration,
                flakiness_score=flakiness_score,
                execution_count=total_executions,
                last_execution=datetime.fromisoformat(rows[-1][4]),
                trend=trend,
                reliability_grade=reliability_grade,
            )

    def _calculate_flakiness_score(self, execution_data: List[tuple]) -> float:
        """Calculate flakiness score based on execution patterns."""
        if len(execution_data) < 5:
            return 0.0  # Not enough data to determine flakiness

        # Look for patterns of pass/fail alternating
        statuses = [row[2] for row in execution_data]

        # Count status changes
        changes = 0
        for i in range(1, len(statuses)):
            if statuses[i] != statuses[i - 1]:
                changes += 1

        # Calculate flakiness as ratio of changes to possible changes
        max_changes = len(statuses) - 1
        flakiness_ratio = changes / max_changes if max_changes > 0 else 0.0

        # Weight by overall pass rate (lower pass rate = higher flakiness impact)
        pass_rate = sum(1 for status in statuses if status == "passed") / len(statuses)

        # Flakiness score: combination of change frequency and pass rate variance
        flakiness_score = flakiness_ratio * (1.0 - abs(pass_rate - 0.5) * 2)

        return min(1.0, max(0.0, flakiness_score))

    def _calculate_trend(self, execution_data: List[tuple]) -> str:
        """Calculate trend based on recent vs historical performance."""
        if len(execution_data) < 10:
            return "stable"

        # Split data into recent and historical
        split_point = len(execution_data) // 2
        historical = execution_data[:split_point]
        recent = execution_data[split_point:]

        # Calculate pass rates
        historical_pass_rate = sum(1 for row in historical if row[2] == "passed") / len(
            historical
        )
        recent_pass_rate = sum(1 for row in recent if row[2] == "passed") / len(recent)

        # Determine trend based on significant changes
        diff = recent_pass_rate - historical_pass_rate

        if diff > 0.1:
            return "improving"
        elif diff < -0.1:
            return "degrading"
        else:
            return "stable"

    def _calculate_reliability_grade(
        self, pass_rate: float, flakiness_score: float
    ) -> str:
        """Calculate reliability grade based on pass rate and flakiness."""
        # Adjust pass rate based on flakiness (flaky tests get lower grades)
        adjusted_score = pass_rate * (1.0 - flakiness_score * 0.5)

        if adjusted_score >= 0.95:
            return "A"
        elif adjusted_score >= 0.85:
            return "B"
        elif adjusted_score >= 0.70:
            return "C"
        elif adjusted_score >= 0.50:
            return "D"
        else:
            return "F"

    def get_test_metrics(self, test_id: str) -> Optional[TestMetrics]:
        """Get cached metrics for a specific test."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT test_id, test_name, test_suite, pass_rate, avg_duration,
                       flakiness_score, execution_count, last_execution, trend,
                       reliability_grade
                FROM test_metrics_cache
                WHERE test_id = ?
            """,
                (test_id,),
            )

            row = cursor.fetchone()
            if row:
                return TestMetrics(
                    test_id=row[0],
                    test_name=row[1],
                    test_suite=row[2],
                    pass_rate=row[3],
                    avg_duration=row[4],
                    flakiness_score=row[5],
                    execution_count=row[6],
                    last_execution=datetime.fromisoformat(row[7]),
                    trend=row[8],
                    reliability_grade=row[9],
                )
            return None

    def get_suite_metrics(self, suite_name: str) -> TestSuiteMetrics:
        """Get aggregated metrics for a test suite."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT COUNT(*) as total_tests,
                       AVG(pass_rate) as avg_pass_rate,
                       AVG(avg_duration) as avg_duration,
                       SUM(CASE WHEN flakiness_score > 0.3 THEN 1 ELSE 0 END) as flaky_tests,
                       SUM(CASE WHEN reliability_grade IN ('D', 'F') THEN 1 ELSE 0 END) as critical_failures,
                       MAX(last_execution) as last_run
                FROM test_metrics_cache
                WHERE test_suite = ?
            """,
                (suite_name,),
            )

            row = cursor.fetchone()

            if row and row[0] > 0:
                total_tests = row[0]
                avg_pass_rate = row[1] or 0.0
                avg_duration = row[2] or 0.0
                flaky_tests = row[3] or 0
                critical_failures = row[4] or 0
                last_run = datetime.fromisoformat(row[5]) if row[5] else datetime.min

                # Determine health status
                if critical_failures > total_tests * 0.2 or avg_pass_rate < 0.7:
                    health_status = "critical"
                elif flaky_tests > total_tests * 0.1 or avg_pass_rate < 0.85:
                    health_status = "warning"
                else:
                    health_status = "healthy"

                return TestSuiteMetrics(
                    suite_name=suite_name,
                    total_tests=total_tests,
                    pass_rate=avg_pass_rate,
                    avg_duration=avg_duration,
                    flaky_tests=flaky_tests,
                    critical_failures=critical_failures,
                    last_run=last_run,
                    health_status=health_status,
                )

            # Return empty metrics if no data
            return TestSuiteMetrics(
                suite_name=suite_name,
                total_tests=0,
                pass_rate=0.0,
                avg_duration=0.0,
                flaky_tests=0,
                critical_failures=0,
                last_run=datetime.min,
                health_status="unknown",
            )

    def get_all_test_metrics(self, limit: int = 100) -> List[TestMetrics]:
        """Get metrics for all tests, ordered by reliability grade."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT test_id, test_name, test_suite, pass_rate, avg_duration,
                       flakiness_score, execution_count, last_execution, trend,
                       reliability_grade
                FROM test_metrics_cache
                ORDER BY
                    CASE reliability_grade
                        WHEN 'F' THEN 1
                        WHEN 'D' THEN 2
                        WHEN 'C' THEN 3
                        WHEN 'B' THEN 4
                        WHEN 'A' THEN 5
                    END ASC,
                    flakiness_score DESC,
                    pass_rate ASC
                LIMIT ?
            """,
                (limit,),
            )

            return [
                TestMetrics(
                    test_id=row[0],
                    test_name=row[1],
                    test_suite=row[2],
                    pass_rate=row[3],
                    avg_duration=row[4],
                    flakiness_score=row[5],
                    execution_count=row[6],
                    last_execution=datetime.fromisoformat(row[7]),
                    trend=row[8],
                    reliability_grade=row[9],
                )
                for row in cursor.fetchall()
            ]

    def get_problematic_tests(
        self, threshold_pass_rate: float = 0.8, threshold_flakiness: float = 0.3
    ) -> List[TestMetrics]:
        """Get tests that are below reliability thresholds."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT test_id, test_name, test_suite, pass_rate, avg_duration,
                       flakiness_score, execution_count, last_execution, trend,
                       reliability_grade
                FROM test_metrics_cache
                WHERE pass_rate < ? OR flakiness_score > ?
                ORDER BY pass_rate ASC, flakiness_score DESC
            """,
                (threshold_pass_rate, threshold_flakiness),
            )

            return [
                TestMetrics(
                    test_id=row[0],
                    test_name=row[1],
                    test_suite=row[2],
                    pass_rate=row[3],
                    avg_duration=row[4],
                    flakiness_score=row[5],
                    execution_count=row[6],
                    last_execution=datetime.fromisoformat(row[7]),
                    trend=row[8],
                    reliability_grade=row[9],
                )
                for row in cursor.fetchall()
            ]

    def refresh_all_metrics(self):
        """Refresh metrics cache for all tests."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT DISTINCT test_id FROM test_executions")
            test_ids = [row[0] for row in cursor.fetchall()]

        # Use thread pool for parallel processing
        with ThreadPoolExecutor(max_workers=5) as executor:
            executor.map(self._update_test_metrics_cache, test_ids)

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Get summary statistics for the dashboard."""
        with sqlite3.connect(self.db_path) as conn:
            # Overall statistics
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as total_tests,
                    AVG(pass_rate) as overall_pass_rate,
                    AVG(avg_duration) as overall_avg_duration,
                    SUM(CASE WHEN reliability_grade = 'A' THEN 1 ELSE 0 END) as grade_a_count,
                    SUM(CASE WHEN reliability_grade = 'B' THEN 1 ELSE 0 END) as grade_b_count,
                    SUM(CASE WHEN reliability_grade = 'C' THEN 1 ELSE 0 END) as grade_c_count,
                    SUM(CASE WHEN reliability_grade = 'D' THEN 1 ELSE 0 END) as grade_d_count,
                    SUM(CASE WHEN reliability_grade = 'F' THEN 1 ELSE 0 END) as grade_f_count,
                    SUM(CASE WHEN flakiness_score > 0.3 THEN 1 ELSE 0 END) as flaky_tests,
                    SUM(CASE WHEN trend = 'degrading' THEN 1 ELSE 0 END) as degrading_tests
                FROM test_metrics_cache
            """
            )

            stats = cursor.fetchone()

            # Suite-level statistics
            cursor = conn.execute(
                """
                SELECT test_suite, COUNT(*) as test_count, AVG(pass_rate) as suite_pass_rate
                FROM test_metrics_cache
                GROUP BY test_suite
                ORDER BY suite_pass_rate ASC
            """
            )

            suite_stats = cursor.fetchall()

            return {
                "total_tests": stats[0] or 0,
                "overall_pass_rate": stats[1] or 0.0,
                "overall_avg_duration": stats[2] or 0.0,
                "grade_distribution": {
                    "A": stats[3] or 0,
                    "B": stats[4] or 0,
                    "C": stats[5] or 0,
                    "D": stats[6] or 0,
                    "F": stats[7] or 0,
                },
                "flaky_tests": stats[8] or 0,
                "degrading_tests": stats[9] or 0,
                "suite_statistics": [
                    {"suite_name": row[0], "test_count": row[1], "pass_rate": row[2]}
                    for row in suite_stats
                ],
            }


# Global metrics collector instance
metrics_collector = TestMetricsCollector()


def record_test_result(
    test_name: str,
    test_suite: str,
    status: str,
    duration: float,
    build_id: str,
    branch: str = "main",
    commit_hash: str = "",
    error_message: str = None,
    stack_trace: str = None,
):
    """Convenience function to record a test result."""
    test_id = f"{test_suite}::{test_name}"

    execution = TestExecution(
        test_id=test_id,
        test_name=test_name,
        test_suite=test_suite,
        status=status,
        duration=duration,
        timestamp=datetime.now(),
        build_id=build_id,
        branch=branch,
        commit_hash=commit_hash,
        error_message=error_message,
        stack_trace=stack_trace,
    )

    metrics_collector.record_test_execution(execution)


def get_test_health_report() -> Dict[str, Any]:
    """Get a comprehensive test health report."""
    summary = metrics_collector.get_dashboard_summary()
    problematic_tests = metrics_collector.get_problematic_tests()

    return {
        "summary": summary,
        "problematic_tests": [asdict(test) for test in problematic_tests[:20]],
        "generated_at": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    # Example usage and testing
    logger.info("Test Monitoring Dashboard initialized")

    # Example: Record some test results
    record_test_result("test_user_login", "auth_tests", "passed", 2.5, "build_123")
    record_test_result(
        "test_user_logout",
        "auth_tests",
        "failed",
        1.8,
        "build_123",
        error_message="Connection timeout",
    )
    record_test_result(
        "test_data_validation", "validation_tests", "passed", 0.9, "build_123"
    )

    # Generate sample report
    report = get_test_health_report()
    print(json.dumps(report, indent=2, default=str))
