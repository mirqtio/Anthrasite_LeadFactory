"""Handoff queue management service for sales team lead distribution.

Implements Feature 5 Extension: TR-4 Bulk Qualify for Handoff.
- Queue management and prioritization
- Sales team assignment logic
- Batch processing for bulk operations
- Integration with qualification engine
"""

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from leadfactory.services.qualification_engine import (
    QualificationEngine,
    QualificationResult,
)
from leadfactory.storage import get_storage_instance
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class HandoffStatus(Enum):
    """Status values for handoff queue entries."""

    QUALIFIED = "qualified"
    ASSIGNED = "assigned"
    CONTACTED = "contacted"
    CLOSED = "closed"
    REJECTED = "rejected"


class BulkOperationType(Enum):
    """Types of bulk operations."""

    QUALIFY = "qualify"
    REJECT = "reject"
    ASSIGN = "assign"
    CONTACT = "contact"
    CLOSE = "close"


@dataclass
class HandoffQueueEntry:
    """Entry in the handoff queue."""

    id: Optional[int]
    business_id: int
    qualification_criteria_id: int
    status: HandoffStatus = HandoffStatus.QUALIFIED
    priority: int = 50
    qualification_score: int = 0
    qualification_details: Dict[str, Any] = None
    assigned_to: Optional[str] = None
    assigned_at: Optional[datetime] = None
    contacted_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    closure_reason: Optional[str] = None
    notes: str = ""
    engagement_summary: Dict[str, Any] = None
    source_campaign_id: Optional[str] = None
    created_at: datetime = None
    updated_at: datetime = None

    def __post_init__(self):
        if self.qualification_details is None:
            self.qualification_details = {}
        if self.engagement_summary is None:
            self.engagement_summary = {}
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        data["status"] = (
            data["status"].value
            if isinstance(data["status"], HandoffStatus)
            else data["status"]
        )

        for date_field in [
            "assigned_at",
            "contacted_at",
            "closed_at",
            "created_at",
            "updated_at",
        ]:
            if data.get(date_field) and isinstance(data[date_field], datetime):
                data[date_field] = data[date_field].isoformat()

        return data


@dataclass
class SalesTeamMember:
    """Sales team member configuration."""

    id: Optional[int]
    user_id: str
    name: str
    email: str
    role: str = "sales_rep"
    specialties: List[str] = None
    max_capacity: int = 50
    current_capacity: int = 0
    is_active: bool = True
    timezone: str = "UTC"
    working_hours: Dict[str, str] = None
    created_at: datetime = None
    updated_at: datetime = None

    def __post_init__(self):
        if self.specialties is None:
            self.specialties = []
        if self.working_hours is None:
            self.working_hours = {"start": "09:00", "end": "17:00"}
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)

        for date_field in ["created_at", "updated_at"]:
            if data.get(date_field) and isinstance(data[date_field], datetime):
                data[date_field] = data[date_field].isoformat()

        return data


@dataclass
class BulkOperation:
    """Bulk operation tracking."""

    operation_id: str
    operation_type: BulkOperationType
    criteria_id: Optional[int]
    business_ids: List[int]
    total_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    operation_details: Dict[str, Any] = None
    performed_by: Optional[str] = None
    performed_at: datetime = None
    completed_at: Optional[datetime] = None
    status: str = "in_progress"

    def __post_init__(self):
        if self.operation_details is None:
            self.operation_details = {}
        if self.performed_at is None:
            self.performed_at = datetime.utcnow()
        self.total_count = len(self.business_ids)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        data["operation_type"] = (
            data["operation_type"].value
            if isinstance(data["operation_type"], BulkOperationType)
            else data["operation_type"]
        )

        for date_field in ["performed_at", "completed_at"]:
            if data.get(date_field) and isinstance(data[date_field], datetime):
                data[date_field] = data[date_field].isoformat()

        return data


class HandoffQueueService:
    """Service for managing handoff queue operations."""

    def __init__(self):
        """Initialize the handoff queue service."""
        self.storage = get_storage_instance()
        self.qualification_engine = QualificationEngine()
        logger.info("Initialized HandoffQueueService")

    def bulk_qualify(
        self,
        business_ids: List[int],
        criteria_id: int,
        performed_by: Optional[str] = None,
        force_rescore: bool = False,
    ) -> str:
        """Qualify multiple businesses and add to handoff queue.

        Args:
            business_ids: List of business IDs to qualify
            criteria_id: Qualification criteria ID
            performed_by: User performing the operation
            force_rescore: Whether to force re-scoring businesses

        Returns:
            Operation ID for tracking
        """
        operation_id = str(uuid.uuid4())

        try:
            logger.info(f"Starting bulk qualification operation {operation_id}")

            # Create operation record
            operation = BulkOperation(
                operation_id=operation_id,
                operation_type=BulkOperationType.QUALIFY,
                criteria_id=criteria_id,
                business_ids=business_ids,
                performed_by=performed_by,
            )

            self._create_bulk_operation(operation)

            # Qualify businesses
            qualification_results = self.qualification_engine.qualify_businesses_bulk(
                business_ids, criteria_id, force_rescore
            )

            success_count = 0
            failure_count = 0

            for result in qualification_results:
                try:
                    if result.status.value == "qualified":
                        # Add to handoff queue
                        queue_entry = HandoffQueueEntry(
                            id=None,
                            business_id=result.business_id,
                            qualification_criteria_id=criteria_id,
                            qualification_score=result.score,
                            qualification_details=result.details,
                            priority=self._calculate_priority(result),
                            notes=result.notes,
                        )

                        entry_id = self._add_to_queue(queue_entry)
                        if entry_id:
                            success_count += 1
                            logger.debug(
                                f"Added business {result.business_id} to handoff queue"
                            )
                        else:
                            failure_count += 1
                            logger.warning(
                                f"Failed to add business {result.business_id} to queue"
                            )
                    else:
                        # Business didn't qualify, still count as processed
                        success_count += 1
                        logger.debug(
                            f"Business {result.business_id} did not qualify: {result.status.value}"
                        )

                except Exception as e:
                    logger.error(
                        f"Error processing qualification result for business {result.business_id}: {e}"
                    )
                    failure_count += 1

            # Update operation status
            operation.success_count = success_count
            operation.failure_count = failure_count
            operation.completed_at = datetime.utcnow()
            operation.status = "completed"
            operation.operation_details = {
                "qualified_count": len(
                    [r for r in qualification_results if r.status.value == "qualified"]
                ),
                "rejected_count": len(
                    [r for r in qualification_results if r.status.value == "rejected"]
                ),
                "insufficient_data_count": len(
                    [
                        r
                        for r in qualification_results
                        if r.status.value == "insufficient_data"
                    ]
                ),
            }

            self._update_bulk_operation(operation)

            logger.info(
                f"Bulk qualification {operation_id} completed: {success_count} success, {failure_count} failed"
            )

            return operation_id

        except Exception as e:
            logger.error(f"Error in bulk qualification {operation_id}: {e}")

            # Update operation as failed
            try:
                operation.status = "failed"
                operation.completed_at = datetime.utcnow()
                operation.operation_details["error"] = str(e)
                self._update_bulk_operation(operation)
            except:
                pass

            raise

    def bulk_assign(
        self,
        queue_entry_ids: List[int],
        assignee_user_id: str,
        performed_by: Optional[str] = None,
    ) -> str:
        """Assign multiple queue entries to a sales team member.

        Args:
            queue_entry_ids: List of handoff queue entry IDs
            assignee_user_id: User ID of sales team member to assign to
            performed_by: User performing the operation

        Returns:
            Operation ID for tracking
        """
        operation_id = str(uuid.uuid4())

        try:
            logger.info(f"Starting bulk assignment operation {operation_id}")

            # Get business IDs for operation tracking
            business_ids = []
            for entry_id in queue_entry_ids:
                entry = self.get_queue_entry(entry_id)
                if entry:
                    business_ids.append(entry.business_id)

            # Create operation record
            operation = BulkOperation(
                operation_id=operation_id,
                operation_type=BulkOperationType.ASSIGN,
                criteria_id=None,
                business_ids=business_ids,
                performed_by=performed_by,
                operation_details={"assignee_user_id": assignee_user_id},
            )

            self._create_bulk_operation(operation)

            # Check assignee capacity
            assignee = self.get_sales_team_member(assignee_user_id)
            if not assignee:
                raise ValueError(f"Sales team member {assignee_user_id} not found")

            if not assignee.is_active:
                raise ValueError(f"Sales team member {assignee_user_id} is not active")

            available_capacity = assignee.max_capacity - assignee.current_capacity
            if len(queue_entry_ids) > available_capacity:
                raise ValueError(
                    f"Assignment would exceed capacity. Available: {available_capacity}, Requested: {len(queue_entry_ids)}"
                )

            success_count = 0
            failure_count = 0

            for entry_id in queue_entry_ids:
                try:
                    success = self.assign_queue_entry(
                        entry_id, assignee_user_id, performed_by
                    )
                    if success:
                        success_count += 1
                    else:
                        failure_count += 1

                except Exception as e:
                    logger.error(f"Error assigning queue entry {entry_id}: {e}")
                    failure_count += 1

            # Update operation status
            operation.success_count = success_count
            operation.failure_count = failure_count
            operation.completed_at = datetime.utcnow()
            operation.status = "completed"

            self._update_bulk_operation(operation)

            logger.info(
                f"Bulk assignment {operation_id} completed: {success_count} success, {failure_count} failed"
            )

            return operation_id

        except Exception as e:
            logger.error(f"Error in bulk assignment {operation_id}: {e}")

            # Update operation as failed
            try:
                operation.status = "failed"
                operation.completed_at = datetime.utcnow()
                operation.operation_details["error"] = str(e)
                self._update_bulk_operation(operation)
            except:
                pass

            raise

    def _calculate_priority(self, qualification_result: QualificationResult) -> int:
        """Calculate priority score for a qualified business.

        Args:
            qualification_result: Qualification result

        Returns:
            Priority score (1-100, higher is more priority)
        """
        base_priority = 50

        # Adjust based on qualification score
        score = qualification_result.score
        if score >= 90:
            base_priority += 30
        elif score >= 80:
            base_priority += 20
        elif score >= 70:
            base_priority += 10

        # Adjust based on engagement data
        engagement_data = qualification_result.details.get("engagement_data", {})
        engagement_summary = engagement_data.get("engagement_summary", {})

        conversions = engagement_summary.get("conversions", 0)
        if conversions > 0:
            base_priority += 15

        page_views = engagement_summary.get("total_page_views", 0)
        if page_views >= 10:
            base_priority += 10
        elif page_views >= 5:
            base_priority += 5

        # Ensure priority is within bounds
        return min(100, max(1, base_priority))

    def _add_to_queue(self, queue_entry: HandoffQueueEntry) -> Optional[int]:
        """Add entry to handoff queue.

        Args:
            queue_entry: Queue entry to add

        Returns:
            Created entry ID or None if failed
        """
        try:
            with self.storage.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO handoff_queue
                    (business_id, qualification_criteria_id, status, priority,
                     qualification_score, qualification_details, notes,
                     engagement_summary, source_campaign_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        queue_entry.business_id,
                        queue_entry.qualification_criteria_id,
                        queue_entry.status.value,
                        queue_entry.priority,
                        queue_entry.qualification_score,
                        json.dumps(queue_entry.qualification_details),
                        queue_entry.notes,
                        json.dumps(queue_entry.engagement_summary),
                        queue_entry.source_campaign_id,
                    ),
                )

                result = cursor.fetchone()
                return result[0] if result else None

        except Exception as e:
            logger.error(f"Error adding to handoff queue: {e}")
            return None

    def get_queue_entry(self, entry_id: int) -> Optional[HandoffQueueEntry]:
        """Get handoff queue entry by ID.

        Args:
            entry_id: Queue entry ID

        Returns:
            HandoffQueueEntry object or None if not found
        """
        try:
            with self.storage.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT * FROM handoff_queue
                    WHERE id = %s
                    """,
                    (entry_id,),
                )

                row = cursor.fetchone()
                if not row:
                    return None

                # Convert row to dictionary
                columns = [desc[0] for desc in cursor.description]
                entry_data = dict(zip(columns, row))

                # Parse JSON fields
                entry_data["qualification_details"] = json.loads(
                    entry_data["qualification_details"] or "{}"
                )
                entry_data["engagement_summary"] = json.loads(
                    entry_data["engagement_summary"] or "{}"
                )

                # Convert status
                entry_data["status"] = HandoffStatus(entry_data["status"])

                return HandoffQueueEntry(**entry_data)

        except Exception as e:
            logger.error(f"Error getting queue entry {entry_id}: {e}")
            return None

    def list_queue_entries(
        self,
        status: Optional[str] = None,
        assigned_to: Optional[str] = None,
        min_priority: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[HandoffQueueEntry]:
        """List handoff queue entries with filtering.

        Args:
            status: Filter by status
            assigned_to: Filter by assignee
            min_priority: Minimum priority threshold
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            List of HandoffQueueEntry objects
        """
        try:
            conditions = []
            params = []

            if status:
                conditions.append("status = %s")
                params.append(status)

            if assigned_to:
                conditions.append("assigned_to = %s")
                params.append(assigned_to)

            if min_priority is not None:
                conditions.append("priority >= %s")
                params.append(min_priority)

            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

            with self.storage.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT * FROM handoff_queue
                    {where_clause}
                    ORDER BY priority DESC, created_at ASC
                    LIMIT %s OFFSET %s
                    """,
                    params + [limit, offset],
                )

                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]

                entries = []
                for row in rows:
                    entry_data = dict(zip(columns, row))

                    # Parse JSON fields
                    entry_data["qualification_details"] = json.loads(
                        entry_data["qualification_details"] or "{}"
                    )
                    entry_data["engagement_summary"] = json.loads(
                        entry_data["engagement_summary"] or "{}"
                    )

                    # Convert status
                    entry_data["status"] = HandoffStatus(entry_data["status"])

                    entries.append(HandoffQueueEntry(**entry_data))

                return entries

        except Exception as e:
            logger.error(f"Error listing queue entries: {e}")
            return []

    def assign_queue_entry(
        self, entry_id: int, assignee_user_id: str, assigned_by: Optional[str] = None
    ) -> bool:
        """Assign a queue entry to a sales team member.

        Args:
            entry_id: Queue entry ID
            assignee_user_id: User ID of assignee
            assigned_by: User who performed the assignment

        Returns:
            True if assignment was successful
        """
        try:
            # Get current entry
            entry = self.get_queue_entry(entry_id)
            if not entry:
                logger.warning(f"Queue entry {entry_id} not found")
                return False

            if entry.status != HandoffStatus.QUALIFIED:
                logger.warning(f"Queue entry {entry_id} is not in qualified status")
                return False

            # Check assignee exists and has capacity
            assignee = self.get_sales_team_member(assignee_user_id)
            if not assignee or not assignee.is_active:
                logger.warning(
                    f"Sales team member {assignee_user_id} not found or inactive"
                )
                return False

            if assignee.current_capacity >= assignee.max_capacity:
                logger.warning(f"Sales team member {assignee_user_id} at full capacity")
                return False

            # Update entry
            with self.storage.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE handoff_queue
                    SET status = %s, assigned_to = %s, assigned_at = %s, updated_at = %s
                    WHERE id = %s
                    """,
                    (
                        HandoffStatus.ASSIGNED.value,
                        assignee_user_id,
                        datetime.utcnow(),
                        datetime.utcnow(),
                        entry_id,
                    ),
                )

                # Record history
                cursor.execute(
                    """
                    INSERT INTO handoff_queue_history
                    (handoff_queue_id, old_status, new_status, old_assigned_to,
                     new_assigned_to, changed_by, change_reason)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        entry_id,
                        entry.status.value,
                        HandoffStatus.ASSIGNED.value,
                        entry.assigned_to,
                        assignee_user_id,
                        assigned_by,
                        "Manual assignment",
                    ),
                )

                # Update assignee capacity
                cursor.execute(
                    """
                    UPDATE sales_team_members
                    SET current_capacity = current_capacity + 1, updated_at = %s
                    WHERE user_id = %s
                    """,
                    (datetime.utcnow(), assignee_user_id),
                )

            logger.info(f"Assigned queue entry {entry_id} to {assignee_user_id}")
            return True

        except Exception as e:
            logger.error(f"Error assigning queue entry {entry_id}: {e}")
            return False

    def get_sales_team_member(self, user_id: str) -> Optional[SalesTeamMember]:
        """Get sales team member by user ID.

        Args:
            user_id: User ID

        Returns:
            SalesTeamMember object or None if not found
        """
        try:
            with self.storage.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT * FROM sales_team_members
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )

                row = cursor.fetchone()
                if not row:
                    return None

                # Convert row to dictionary
                columns = [desc[0] for desc in cursor.description]
                member_data = dict(zip(columns, row))

                # Parse JSON fields
                member_data["specialties"] = json.loads(
                    member_data["specialties"] or "[]"
                )
                member_data["working_hours"] = json.loads(
                    member_data["working_hours"] or "{}"
                )

                return SalesTeamMember(**member_data)

        except Exception as e:
            logger.error(f"Error getting sales team member {user_id}: {e}")
            return None

    def _create_bulk_operation(self, operation: BulkOperation) -> bool:
        """Create bulk operation record.

        Args:
            operation: BulkOperation object

        Returns:
            True if created successfully
        """
        try:
            with self.storage.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO bulk_qualification_operations
                    (operation_id, operation_type, criteria_id, business_ids,
                     total_count, operation_details, performed_by, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        operation.operation_id,
                        operation.operation_type.value,
                        operation.criteria_id,
                        operation.business_ids,
                        operation.total_count,
                        json.dumps(operation.operation_details),
                        operation.performed_by,
                        operation.status,
                    ),
                )

            return True

        except Exception as e:
            logger.error(f"Error creating bulk operation: {e}")
            return False

    def _update_bulk_operation(self, operation: BulkOperation) -> bool:
        """Update bulk operation record.

        Args:
            operation: BulkOperation object

        Returns:
            True if updated successfully
        """
        try:
            with self.storage.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE bulk_qualification_operations
                    SET success_count = %s, failure_count = %s,
                        operation_details = %s, completed_at = %s, status = %s
                    WHERE operation_id = %s
                    """,
                    (
                        operation.success_count,
                        operation.failure_count,
                        json.dumps(operation.operation_details),
                        operation.completed_at,
                        operation.status,
                        operation.operation_id,
                    ),
                )

            return True

        except Exception as e:
            logger.error(f"Error updating bulk operation: {e}")
            return False
