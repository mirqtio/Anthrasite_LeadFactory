"""
A/B Test Manager - Core orchestration for A/B testing framework.

This module provides centralized management of A/B tests including creation,
execution, monitoring, and result analysis.
"""

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from leadfactory.utils.logging import get_logger


class TestStatus(Enum):
    """A/B test status enumeration."""

    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class TestType(Enum):
    """A/B test type enumeration."""

    EMAIL_SUBJECT = "email_subject"
    PRICING = "pricing"
    EMAIL_CONTENT = "email_content"
    CTA_BUTTON = "cta_button"


@dataclass
class ABTestConfig:
    """Configuration for an A/B test."""

    id: str
    name: str
    description: str
    test_type: TestType
    status: TestStatus
    start_date: datetime
    end_date: Optional[datetime]
    target_sample_size: int
    significance_threshold: float
    minimum_effect_size: float
    variants: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


@dataclass
class TestAssignment:
    """User assignment to a specific test variant."""

    user_id: str
    test_id: str
    variant_id: str
    assigned_at: datetime
    metadata: Dict[str, Any]


@dataclass
class TestConversion:
    """Conversion event for an A/B test."""

    id: str
    test_id: str
    variant_id: str
    user_id: str
    conversion_type: str
    conversion_value: Optional[float]
    timestamp: datetime
    metadata: Dict[str, Any]


class ABTestManager:
    """Central manager for A/B testing framework."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize A/B test manager.

        Args:
            db_path: Path to SQLite database for test storage
        """
        self.db_path = db_path or "ab_tests.db"
        self.logger = get_logger(f"{__name__}.ABTestManager")
        self._init_database()

    def _init_database(self):
        """Initialize database schema for A/B testing."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS ab_tests (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    test_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'draft',
                    start_date DATETIME,
                    end_date DATETIME,
                    target_sample_size INTEGER NOT NULL DEFAULT 1000,
                    significance_threshold REAL NOT NULL DEFAULT 0.05,
                    minimum_effect_size REAL NOT NULL DEFAULT 0.1,
                    variants TEXT NOT NULL,  -- JSON array
                    metadata TEXT,  -- JSON object
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS test_assignments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    test_id TEXT NOT NULL,
                    variant_id TEXT NOT NULL,
                    assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT,  -- JSON object
                    FOREIGN KEY (test_id) REFERENCES ab_tests (id) ON DELETE CASCADE,
                    UNIQUE(user_id, test_id)
                );

                CREATE TABLE IF NOT EXISTS test_conversions (
                    id TEXT PRIMARY KEY,
                    test_id TEXT NOT NULL,
                    variant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    conversion_type TEXT NOT NULL,
                    conversion_value REAL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT,  -- JSON object
                    FOREIGN KEY (test_id) REFERENCES ab_tests (id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_assignments_user_test ON test_assignments(user_id, test_id);
                CREATE INDEX IF NOT EXISTS idx_assignments_test ON test_assignments(test_id);
                CREATE INDEX IF NOT EXISTS idx_conversions_test ON test_conversions(test_id);
                CREATE INDEX IF NOT EXISTS idx_conversions_variant ON test_conversions(test_id, variant_id);
                CREATE INDEX IF NOT EXISTS idx_conversions_timestamp ON test_conversions(timestamp);
                CREATE INDEX IF NOT EXISTS idx_tests_status ON ab_tests(status);
                CREATE INDEX IF NOT EXISTS idx_tests_type ON ab_tests(test_type);
            """
            )

        self.logger.info(f"A/B testing database initialized at {self.db_path}")

    def create_test(
        self,
        name: str,
        description: str,
        test_type: TestType,
        variants: List[Dict[str, Any]],
        target_sample_size: int = 1000,
        significance_threshold: float = 0.05,
        minimum_effect_size: float = 0.1,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new A/B test.

        Args:
            name: Test name
            description: Test description
            test_type: Type of test (email_subject, pricing, etc.)
            variants: List of test variants
            target_sample_size: Target number of participants
            significance_threshold: Statistical significance threshold (p-value)
            minimum_effect_size: Minimum detectable effect size
            start_date: Test start date (defaults to now)
            end_date: Test end date (optional)
            metadata: Additional test metadata

        Returns:
            Test ID
        """
        test_id = str(uuid.uuid4())

        if not start_date:
            start_date = datetime.utcnow()

        # Validate variants
        self._validate_variants(variants, test_type)

        test_config = ABTestConfig(
            id=test_id,
            name=name,
            description=description,
            test_type=test_type,
            status=TestStatus.DRAFT,
            start_date=start_date,
            end_date=end_date,
            target_sample_size=target_sample_size,
            significance_threshold=significance_threshold,
            minimum_effect_size=minimum_effect_size,
            variants=variants,
            metadata=metadata or {},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO ab_tests (
                    id, name, description, test_type, status, start_date, end_date,
                    target_sample_size, significance_threshold, minimum_effect_size,
                    variants, metadata, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    test_id,
                    name,
                    description,
                    test_type.value,
                    TestStatus.DRAFT.value,
                    start_date,
                    end_date,
                    target_sample_size,
                    significance_threshold,
                    minimum_effect_size,
                    json.dumps(variants),
                    json.dumps(metadata or {}),
                    test_config.created_at,
                    test_config.updated_at,
                ),
            )

        self.logger.info(f"Created A/B test: {test_id} ({name})")
        return test_id

    def _validate_variants(self, variants: List[Dict[str, Any]], test_type: TestType):
        """Validate test variants based on test type."""
        if not variants or len(variants) < 2:
            raise ValueError("Test must have at least 2 variants")

        total_weight = sum(v.get("weight", 1 / len(variants)) for v in variants)
        if abs(total_weight - 1.0) > 0.01:
            raise ValueError(f"Variant weights must sum to 1.0, got {total_weight}")

        # Type-specific validation
        if test_type == TestType.EMAIL_SUBJECT:
            for variant in variants:
                if "subject" not in variant:
                    raise ValueError("Email subject variants must have 'subject' field")

        elif test_type == TestType.PRICING:
            for variant in variants:
                if "price" not in variant:
                    raise ValueError("Pricing variants must have 'price' field")
                if not isinstance(variant["price"], (int, float)):
                    raise ValueError("Price must be a number")

    def start_test(self, test_id: str) -> bool:
        """Start an A/B test.

        Args:
            test_id: Test identifier

        Returns:
            True if test was started successfully
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT status FROM ab_tests WHERE id = ?", (test_id,)
            )
            row = cursor.fetchone()

            if not row:
                raise ValueError(f"Test not found: {test_id}")

            if row[0] != TestStatus.DRAFT.value:
                raise ValueError(f"Cannot start test in status: {row[0]}")

            conn.execute(
                """
                UPDATE ab_tests
                SET status = ?, start_date = ?, updated_at = ?
                WHERE id = ?
            """,
                (
                    TestStatus.ACTIVE.value,
                    datetime.utcnow(),
                    datetime.utcnow(),
                    test_id,
                ),
            )

        self.logger.info(f"Started A/B test: {test_id}")
        return True

    def stop_test(self, test_id: str) -> bool:
        """Stop an active A/B test.

        Args:
            test_id: Test identifier

        Returns:
            True if test was stopped successfully
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT status FROM ab_tests WHERE id = ?", (test_id,)
            )
            row = cursor.fetchone()

            if not row:
                raise ValueError(f"Test not found: {test_id}")

            if row[0] != TestStatus.ACTIVE.value:
                raise ValueError(f"Cannot stop test in status: {row[0]}")

            conn.execute(
                """
                UPDATE ab_tests
                SET status = ?, end_date = ?, updated_at = ?
                WHERE id = ?
            """,
                (
                    TestStatus.COMPLETED.value,
                    datetime.utcnow(),
                    datetime.utcnow(),
                    test_id,
                ),
            )

        self.logger.info(f"Stopped A/B test: {test_id}")
        return True

    def assign_user_to_variant(
        self, user_id: str, test_id: str, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Assign a user to a test variant.

        Args:
            user_id: User identifier
            test_id: Test identifier
            metadata: Additional assignment metadata

        Returns:
            Variant ID assigned to user
        """
        # Check if user is already assigned
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT variant_id FROM test_assignments
                WHERE user_id = ? AND test_id = ?
            """,
                (user_id, test_id),
            )

            existing = cursor.fetchone()
            if existing:
                return existing[0]

            # Get test configuration
            cursor = conn.execute(
                """
                SELECT variants, status FROM ab_tests WHERE id = ?
            """,
                (test_id,),
            )

            test_row = cursor.fetchone()
            if not test_row:
                raise ValueError(f"Test not found: {test_id}")

            if test_row[1] != TestStatus.ACTIVE.value:
                raise ValueError(f"Test is not active: {test_id}")

            variants = json.loads(test_row[0])

            # Assign variant using consistent hashing
            variant_id = self._assign_variant(user_id, test_id, variants)

            # Store assignment
            conn.execute(
                """
                INSERT INTO test_assignments (user_id, test_id, variant_id, metadata)
                VALUES (?, ?, ?, ?)
            """,
                (user_id, test_id, variant_id, json.dumps(metadata or {})),
            )

        self.logger.debug(
            f"Assigned user {user_id} to variant {variant_id} in test {test_id}"
        )
        return variant_id

    def _assign_variant(
        self, user_id: str, test_id: str, variants: List[Dict[str, Any]]
    ) -> str:
        """Assign a variant using consistent hashing for stability."""
        # Create a hash based on user_id and test_id for consistency
        hash_input = f"{user_id}:{test_id}".encode()
        hash_value = int(hashlib.md5(hash_input, usedforsecurity=False).hexdigest(), 16)

        # Normalize to [0, 1) range
        normalized = (hash_value % 10000) / 10000.0

        # Assign based on variant weights
        cumulative_weight = 0.0
        for i, variant in enumerate(variants):
            weight = variant.get("weight", 1.0 / len(variants))
            cumulative_weight += weight

            if normalized <= cumulative_weight:
                return f"variant_{i}"

        # Fallback to last variant
        return f"variant_{len(variants) - 1}"

    def record_conversion(
        self,
        test_id: str,
        user_id: str,
        conversion_type: str,
        conversion_value: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a conversion event for an A/B test.

        Args:
            test_id: Test identifier
            user_id: User identifier
            conversion_type: Type of conversion (email_open, purchase, etc.)
            conversion_value: Monetary value of conversion
            metadata: Additional conversion metadata

        Returns:
            Conversion ID
        """
        conversion_id = str(uuid.uuid4())

        with sqlite3.connect(self.db_path) as conn:
            # Get user's variant assignment
            cursor = conn.execute(
                """
                SELECT variant_id FROM test_assignments
                WHERE user_id = ? AND test_id = ?
            """,
                (user_id, test_id),
            )

            assignment = cursor.fetchone()
            if not assignment:
                raise ValueError(f"User {user_id} not assigned to test {test_id}")

            variant_id = assignment[0]

            # Record conversion
            conn.execute(
                """
                INSERT INTO test_conversions (
                    id, test_id, variant_id, user_id, conversion_type,
                    conversion_value, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    conversion_id,
                    test_id,
                    variant_id,
                    user_id,
                    conversion_type,
                    conversion_value,
                    json.dumps(metadata or {}),
                ),
            )

        self.logger.debug(
            f"Recorded conversion {conversion_type} for user {user_id} in test {test_id}"
        )
        return conversion_id

    def get_test_config(self, test_id: str) -> Optional[ABTestConfig]:
        """Get test configuration by ID.

        Args:
            test_id: Test identifier

        Returns:
            Test configuration or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM ab_tests WHERE id = ?", (test_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return ABTestConfig(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                test_type=TestType(row["test_type"]),
                status=TestStatus(row["status"]),
                start_date=(
                    datetime.fromisoformat(row["start_date"])
                    if row["start_date"]
                    else None
                ),
                end_date=(
                    datetime.fromisoformat(row["end_date"]) if row["end_date"] else None
                ),
                target_sample_size=row["target_sample_size"],
                significance_threshold=row["significance_threshold"],
                minimum_effect_size=row["minimum_effect_size"],
                variants=json.loads(row["variants"]),
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )

    def get_active_tests(
        self, test_type: Optional[TestType] = None
    ) -> List[ABTestConfig]:
        """Get all active A/B tests.

        Args:
            test_type: Filter by test type (optional)

        Returns:
            List of active test configurations
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if test_type:
                cursor = conn.execute(
                    """
                    SELECT * FROM ab_tests
                    WHERE status = ? AND test_type = ?
                    ORDER BY created_at DESC
                """,
                    (TestStatus.ACTIVE.value, test_type.value),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM ab_tests
                    WHERE status = ?
                    ORDER BY created_at DESC
                """,
                    (TestStatus.ACTIVE.value,),
                )

            tests = []
            for row in cursor:
                test_config = ABTestConfig(
                    id=row["id"],
                    name=row["name"],
                    description=row["description"],
                    test_type=TestType(row["test_type"]),
                    status=TestStatus(row["status"]),
                    start_date=(
                        datetime.fromisoformat(row["start_date"])
                        if row["start_date"]
                        else None
                    ),
                    end_date=(
                        datetime.fromisoformat(row["end_date"])
                        if row["end_date"]
                        else None
                    ),
                    target_sample_size=row["target_sample_size"],
                    significance_threshold=row["significance_threshold"],
                    minimum_effect_size=row["minimum_effect_size"],
                    variants=json.loads(row["variants"]),
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
                tests.append(test_config)

            return tests

    def get_test_results(self, test_id: str) -> Dict[str, Any]:
        """Get comprehensive results for an A/B test.

        Args:
            test_id: Test identifier

        Returns:
            Dictionary with test results and statistics
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get test configuration
            test_config = self.get_test_config(test_id)
            if not test_config:
                raise ValueError(f"Test not found: {test_id}")

            # Get assignments by variant
            cursor = conn.execute(
                """
                SELECT variant_id, COUNT(*) as assignments
                FROM test_assignments
                WHERE test_id = ?
                GROUP BY variant_id
            """,
                (test_id,),
            )

            assignments = {row["variant_id"]: row["assignments"] for row in cursor}

            # Get conversions by variant
            cursor = conn.execute(
                """
                SELECT
                    variant_id,
                    conversion_type,
                    COUNT(*) as conversions,
                    SUM(conversion_value) as total_value,
                    AVG(conversion_value) as avg_value
                FROM test_conversions
                WHERE test_id = ?
                GROUP BY variant_id, conversion_type
            """,
                (test_id,),
            )

            conversions = {}
            for row in cursor:
                variant_id = row["variant_id"]
                conversion_type = row["conversion_type"]

                if variant_id not in conversions:
                    conversions[variant_id] = {}

                conversions[variant_id][conversion_type] = {
                    "count": row["conversions"],
                    "total_value": row["total_value"] or 0,
                    "avg_value": row["avg_value"] or 0,
                }

            # Calculate conversion rates
            variant_results = {}
            for variant_id, assignment_count in assignments.items():
                variant_conversions = conversions.get(variant_id, {})

                # Calculate rates for each conversion type
                conversion_rates = {}
                for conv_type, conv_data in variant_conversions.items():
                    conversion_rates[conv_type] = {
                        "rate": (
                            conv_data["count"] / assignment_count
                            if assignment_count > 0
                            else 0
                        ),
                        "count": conv_data["count"],
                        "total_value": conv_data["total_value"],
                        "avg_value": conv_data["avg_value"],
                    }

                variant_results[variant_id] = {
                    "assignments": assignment_count,
                    "conversions": variant_conversions,
                    "conversion_rates": conversion_rates,
                }

            return {
                "test_id": test_id,
                "test_config": test_config,
                "variant_results": variant_results,
                "total_assignments": sum(assignments.values()),
                "start_date": test_config.start_date,
                "end_date": test_config.end_date,
                "status": test_config.status.value,
            }


# Global instance
ab_test_manager = ABTestManager()
