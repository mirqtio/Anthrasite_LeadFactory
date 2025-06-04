"""
Automated follow-up email workflow system.

This module implements an automated follow-up email system that sends
reminders based on user interactions with the initial email.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from leadfactory.email.delivery import EmailDeliveryService, EmailStatus
from leadfactory.email.secure_links import SecureLinkGenerator
from leadfactory.email.templates import EmailPersonalization, EmailTemplateEngine
from leadfactory.storage.factory import get_storage_instance

logger = logging.getLogger(__name__)


class WorkflowTrigger(str, Enum):
    """Workflow trigger types."""

    REPORT_PURCHASED = "report_purchased"
    LINK_NOT_CLICKED = "link_not_clicked"
    REPORT_VIEWED = "report_viewed"
    NO_AGENCY_CONNECTION = "no_agency_connection"
    AGENCY_CONNECTED = "agency_connected"


class WorkflowStatus(str, Enum):
    """Workflow execution status."""

    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class WorkflowStep(BaseModel):
    """Individual workflow step configuration."""

    step_id: str = Field(..., description="Unique step identifier")
    name: str = Field(..., description="Step name")
    trigger: WorkflowTrigger = Field(..., description="Trigger condition")
    delay_hours: int = Field(..., description="Delay before execution in hours")
    template_name: str = Field(..., description="Email template to use")
    conditions: Dict = Field(default_factory=dict, description="Additional conditions")
    max_attempts: int = Field(default=1, description="Maximum execution attempts")


class WorkflowExecution(BaseModel):
    """Workflow execution record."""

    execution_id: str = Field(..., description="Unique execution identifier")
    user_id: str = Field(..., description="Target user ID")
    report_id: str = Field(..., description="Associated report ID")
    purchase_id: str = Field(..., description="Purchase identifier")
    workflow_name: str = Field(..., description="Workflow name")
    status: WorkflowStatus = Field(
        default=WorkflowStatus.PENDING, description="Execution status"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation timestamp"
    )
    started_at: Optional[datetime] = Field(None, description="Start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    current_step: Optional[str] = Field(None, description="Current step ID")
    metadata: Dict = Field(default_factory=dict, description="Workflow metadata")


class WorkflowStepExecution(BaseModel):
    """Individual step execution record."""

    step_execution_id: str = Field(..., description="Unique step execution ID")
    execution_id: str = Field(..., description="Parent workflow execution ID")
    step_id: str = Field(..., description="Step identifier")
    status: WorkflowStatus = Field(
        default=WorkflowStatus.PENDING, description="Step status"
    )
    scheduled_at: datetime = Field(..., description="Scheduled execution time")
    executed_at: Optional[datetime] = Field(None, description="Actual execution time")
    email_id: Optional[str] = Field(None, description="Sent email ID")
    attempt_count: int = Field(default=0, description="Number of attempts")
    error_message: Optional[str] = Field(None, description="Error message if failed")


class EmailWorkflowEngine:
    """Engine for managing automated email workflows."""

    def __init__(self):
        """Initialize the workflow engine."""
        self.storage = get_storage_instance()
        self.email_service = EmailDeliveryService()
        self.template_engine = EmailTemplateEngine()
        self.link_generator = SecureLinkGenerator()

        # Define default workflows
        self.workflows = {
            "report_delivery": self._get_report_delivery_workflow(),
            "agency_conversion": self._get_agency_conversion_workflow(),
        }

    def _get_report_delivery_workflow(self) -> List[WorkflowStep]:
        """Get the report delivery workflow steps."""
        return [
            WorkflowStep(
                step_id="initial_delivery",
                name="Initial Report Delivery",
                trigger=WorkflowTrigger.REPORT_PURCHASED,
                delay_hours=0,
                template_name="report_delivery",
            ),
            WorkflowStep(
                step_id="access_reminder",
                name="Report Access Reminder",
                trigger=WorkflowTrigger.LINK_NOT_CLICKED,
                delay_hours=72,  # 3 days
                template_name="report_reminder",
                conditions={"report_accessed": False},
            ),
            WorkflowStep(
                step_id="agency_followup",
                name="Agency Connection Follow-up",
                trigger=WorkflowTrigger.NO_AGENCY_CONNECTION,
                delay_hours=120,  # 5 days
                template_name="agency_followup",
                conditions={"agency_connected": False},
            ),
        ]

    def _get_agency_conversion_workflow(self) -> List[WorkflowStep]:
        """Get the agency conversion workflow steps."""
        return [
            WorkflowStep(
                step_id="post_view_followup",
                name="Post-View Agency Follow-up",
                trigger=WorkflowTrigger.REPORT_VIEWED,
                delay_hours=24,  # 1 day
                template_name="agency_followup",
                conditions={"agency_connected": False},
            ),
            WorkflowStep(
                step_id="final_conversion_push",
                name="Final Conversion Push",
                trigger=WorkflowTrigger.NO_AGENCY_CONNECTION,
                delay_hours=168,  # 7 days
                template_name="final_agency_push",
                conditions={"agency_connected": False},
            ),
        ]

    async def start_workflow(
        self,
        workflow_name: str,
        user_id: str,
        report_id: str,
        purchase_id: str,
        user_email: str,
        user_name: str,
        report_title: str,
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Start a new workflow execution.

        Args:
            workflow_name: Name of the workflow to execute
            user_id: Target user ID
            report_id: Associated report ID
            purchase_id: Purchase identifier
            user_email: User email address
            user_name: User name
            report_title: Report title
            metadata: Additional metadata

        Returns:
            Workflow execution ID
        """
        execution_id = str(uuid4())

        try:
            # Create workflow execution record
            execution = WorkflowExecution(
                execution_id=execution_id,
                user_id=user_id,
                report_id=report_id,
                purchase_id=purchase_id,
                workflow_name=workflow_name,
                metadata={
                    "user_email": user_email,
                    "user_name": user_name,
                    "report_title": report_title,
                    **(metadata or {}),
                },
            )

            # Store execution record
            await self._store_workflow_execution(execution)

            # Schedule workflow steps
            workflow_steps = self.workflows.get(workflow_name, [])
            for step in workflow_steps:
                await self._schedule_workflow_step(execution_id, step)

            # Start execution
            execution.status = WorkflowStatus.ACTIVE
            execution.started_at = datetime.utcnow()
            await self._store_workflow_execution(execution)

            logger.info(
                f"Started workflow {workflow_name} for user {user_id}: {execution_id}"
            )
            return execution_id

        except Exception as e:
            logger.error(f"Failed to start workflow {workflow_name}: {str(e)}")
            raise

    async def _schedule_workflow_step(
        self, execution_id: str, step: WorkflowStep
    ) -> None:
        """Schedule a workflow step for execution."""
        try:
            step_execution_id = str(uuid4())
            scheduled_at = datetime.utcnow() + timedelta(hours=step.delay_hours)

            step_execution = WorkflowStepExecution(
                step_execution_id=step_execution_id,
                execution_id=execution_id,
                step_id=step.step_id,
                scheduled_at=scheduled_at,
            )

            await self._store_step_execution(step_execution)

        except Exception as e:
            logger.error(f"Failed to schedule workflow step {step.step_id}: {str(e)}")

    async def process_pending_steps(self) -> int:
        """
        Process all pending workflow steps that are due for execution.

        Returns:
            Number of steps processed
        """
        try:
            # Get pending steps that are due
            query = """
                SELECT se.*, we.user_id, we.report_id, we.purchase_id, we.metadata
                FROM workflow_step_executions se
                JOIN workflow_executions we ON se.execution_id = we.execution_id
                WHERE se.status = 'pending'
                AND se.scheduled_at <= $1
                AND we.status = 'active'
                ORDER BY se.scheduled_at
            """

            pending_steps = await self.storage.fetch_all(query, datetime.utcnow())

            processed_count = 0
            for step_data in pending_steps:
                try:
                    await self._execute_workflow_step(step_data)
                    processed_count += 1
                except Exception as e:
                    logger.error(
                        f"Failed to execute step {step_data['step_execution_id']}: {str(e)}"
                    )

            return processed_count

        except Exception as e:
            logger.error(f"Failed to process pending steps: {str(e)}")
            return 0

    async def _execute_workflow_step(self, step_data: Dict) -> None:
        """Execute a single workflow step."""
        step_execution_id = step_data["step_execution_id"]
        execution_id = step_data["execution_id"]
        step_id = step_data["step_id"]

        try:
            # Update step status to active
            await self._update_step_status(
                step_execution_id, WorkflowStatus.ACTIVE, executed_at=datetime.utcnow()
            )

            # Get workflow and step configuration
            workflow_name = await self._get_workflow_name(execution_id)
            workflow_steps = self.workflows.get(workflow_name, [])
            step_config = next(
                (s for s in workflow_steps if s.step_id == step_id), None
            )

            if not step_config:
                raise ValueError(f"Step configuration not found: {step_id}")

            # Check step conditions
            if not await self._check_step_conditions(step_data, step_config):
                await self._update_step_status(
                    step_execution_id, WorkflowStatus.COMPLETED
                )
                return

            # Generate personalization data
            personalization = await self._create_personalization(step_data)

            # Render email template
            template = self.template_engine.render_template(
                step_config.template_name, personalization
            )

            # Send email
            email_id = await self.email_service.send_email(
                template,
                personalization,
                metadata={"workflow_execution_id": execution_id, "step_id": step_id},
            )

            # Update step with email ID
            await self._update_step_email_id(step_execution_id, email_id)

            # Mark step as completed
            await self._update_step_status(step_execution_id, WorkflowStatus.COMPLETED)

            logger.info(
                f"Executed workflow step {step_id} for execution {execution_id}"
            )

        except Exception as e:
            # Mark step as failed
            await self._update_step_status(
                step_execution_id, WorkflowStatus.FAILED, error_message=str(e)
            )
            raise

    async def _check_step_conditions(
        self, step_data: Dict, step_config: WorkflowStep
    ) -> bool:
        """Check if step conditions are met."""
        try:
            conditions = step_config.conditions
            if not conditions:
                return True

            # Check report access condition
            if "report_accessed" in conditions:
                expected_accessed = conditions["report_accessed"]
                actual_accessed = await self._check_report_accessed(
                    step_data["user_id"], step_data["report_id"]
                )
                if actual_accessed != expected_accessed:
                    return False

            # Check agency connection condition
            if "agency_connected" in conditions:
                expected_connected = conditions["agency_connected"]
                actual_connected = await self._check_agency_connected(
                    step_data["user_id"]
                )
                if actual_connected != expected_connected:
                    return False

            return True

        except Exception as e:
            logger.error(f"Failed to check step conditions: {str(e)}")
            return False

    async def _check_report_accessed(self, user_id: str, report_id: str) -> bool:
        """Check if user has accessed the report."""
        try:
            # Check for click events on report links
            query = """
                SELECT COUNT(*) as click_count
                FROM email_events ee
                JOIN email_deliveries ed ON ee.email_id = ed.email_id
                WHERE ed.user_id = $1
                AND ee.event_type = 'click'
                AND ee.url LIKE '%report%'
                AND ed.metadata->>'report_id' = $2
            """

            result = await self.storage.fetch_one(query, user_id, report_id)
            return (result["click_count"] if result else 0) > 0

        except Exception as e:
            logger.error(f"Failed to check report access: {str(e)}")
            return False

    async def _check_agency_connected(self, user_id: str) -> bool:
        """Check if user has connected with an agency."""
        try:
            # Check for agency connection events
            query = """
                SELECT COUNT(*) as connection_count
                FROM email_events ee
                JOIN email_deliveries ed ON ee.email_id = ed.email_id
                WHERE ed.user_id = $1
                AND ee.event_type = 'click'
                AND ee.url LIKE '%agency%'
            """

            result = await self.storage.fetch_one(query, user_id)
            return (result["connection_count"] if result else 0) > 0

        except Exception as e:
            logger.error(f"Failed to check agency connection: {str(e)}")
            return False

    async def _create_personalization(self, step_data: Dict) -> EmailPersonalization:
        """Create email personalization from step data."""
        metadata = step_data.get("metadata", {})

        # Generate secure links
        report_link = self.link_generator.generate_secure_link(
            report_id=step_data["report_id"],
            user_id=step_data["user_id"],
            purchase_id=step_data["purchase_id"],
            base_url="https://app.anthrasite.com/reports",
        )

        agency_cta_link = self.link_generator.create_tracking_link(
            original_url="https://app.anthrasite.com/connect-agency",
            user_id=step_data["user_id"],
            campaign_id=step_data["execution_id"],
            link_type="agency_cta",
        )

        return EmailPersonalization(
            user_name=metadata.get("user_name", "Valued Customer"),
            user_email=metadata.get("user_email", ""),
            report_title=metadata.get("report_title", "Your Audit Report"),
            report_link=report_link,
            agency_cta_link=agency_cta_link,
            company_name=metadata.get("company_name"),
            purchase_date=datetime.utcnow(),  # TODO: Get actual purchase date
            expiry_date=datetime.utcnow() + timedelta(days=7),
        )

    async def _store_workflow_execution(self, execution: WorkflowExecution) -> None:
        """Store workflow execution record."""
        try:
            query = """
                INSERT INTO workflow_executions
                (execution_id, user_id, report_id, purchase_id, workflow_name,
                 status, created_at, started_at, completed_at, current_step, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (execution_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    started_at = EXCLUDED.started_at,
                    completed_at = EXCLUDED.completed_at,
                    current_step = EXCLUDED.current_step,
                    metadata = EXCLUDED.metadata
            """

            await self.storage.execute_query(
                query,
                execution.execution_id,
                execution.user_id,
                execution.report_id,
                execution.purchase_id,
                execution.workflow_name,
                execution.status.value,
                execution.created_at,
                execution.started_at,
                execution.completed_at,
                execution.current_step,
                execution.metadata,
            )

        except Exception as e:
            logger.error(f"Failed to store workflow execution: {str(e)}")

    async def _store_step_execution(
        self, step_execution: WorkflowStepExecution
    ) -> None:
        """Store workflow step execution record."""
        try:
            query = """
                INSERT INTO workflow_step_executions
                (step_execution_id, execution_id, step_id, status, scheduled_at,
                 executed_at, email_id, attempt_count, error_message)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (step_execution_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    executed_at = EXCLUDED.executed_at,
                    email_id = EXCLUDED.email_id,
                    attempt_count = EXCLUDED.attempt_count,
                    error_message = EXCLUDED.error_message
            """

            await self.storage.execute_query(
                query,
                step_execution.step_execution_id,
                step_execution.execution_id,
                step_execution.step_id,
                step_execution.status.value,
                step_execution.scheduled_at,
                step_execution.executed_at,
                step_execution.email_id,
                step_execution.attempt_count,
                step_execution.error_message,
            )

        except Exception as e:
            logger.error(f"Failed to store step execution: {str(e)}")

    async def _update_step_status(
        self,
        step_execution_id: str,
        status: WorkflowStatus,
        executed_at: Optional[datetime] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Update workflow step status."""
        try:
            query = """
                UPDATE workflow_step_executions
                SET status = $1, executed_at = COALESCE($2, executed_at),
                    error_message = $3, attempt_count = attempt_count + 1
                WHERE step_execution_id = $4
            """

            await self.storage.execute_query(
                query, status.value, executed_at, error_message, step_execution_id
            )

        except Exception as e:
            logger.error(f"Failed to update step status: {str(e)}")

    async def _update_step_email_id(
        self, step_execution_id: str, email_id: str
    ) -> None:
        """Update step execution with email ID."""
        try:
            query = """
                UPDATE workflow_step_executions
                SET email_id = $1
                WHERE step_execution_id = $2
            """

            await self.storage.execute_query(query, email_id, step_execution_id)

        except Exception as e:
            logger.error(f"Failed to update step email ID: {str(e)}")

    async def _get_workflow_name(self, execution_id: str) -> str:
        """Get workflow name for execution."""
        try:
            query = (
                "SELECT workflow_name FROM workflow_executions WHERE execution_id = $1"
            )
            result = await self.storage.fetch_one(query, execution_id)
            return result["workflow_name"] if result else ""

        except Exception as e:
            logger.error(f"Failed to get workflow name: {str(e)}")
            return ""

    async def cancel_workflow(self, execution_id: str) -> None:
        """Cancel a workflow execution."""
        try:
            # Update execution status
            query = """
                UPDATE workflow_executions
                SET status = 'cancelled', completed_at = $1
                WHERE execution_id = $2
            """
            await self.storage.execute_query(query, datetime.utcnow(), execution_id)

            # Cancel pending steps
            query = """
                UPDATE workflow_step_executions
                SET status = 'cancelled'
                WHERE execution_id = $1 AND status = 'pending'
            """
            await self.storage.execute_query(query, execution_id)

            logger.info(f"Cancelled workflow execution: {execution_id}")

        except Exception as e:
            logger.error(f"Failed to cancel workflow: {str(e)}")


def get_email_workflow_engine() -> EmailWorkflowEngine:
    """Get a configured email workflow engine instance."""
    return EmailWorkflowEngine()
