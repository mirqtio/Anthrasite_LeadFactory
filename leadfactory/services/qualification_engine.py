"""Qualification criteria engine for handoff queue management.

Implements Feature 5 Extension: TR-4 Bulk Qualify for Handoff.
- Configurable qualification criteria
- Integration with scoring engine and engagement analytics
- Batch processing capabilities
- Rule-based qualification logic
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from leadfactory.monitoring.engagement_analytics import EngagementAnalytics
from leadfactory.scoring.scoring_engine import ScoringEngine
from leadfactory.storage import get_storage_instance
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class QualificationStatus(Enum):
    """Status values for qualification results."""

    QUALIFIED = "qualified"
    REJECTED = "rejected"
    PENDING_REVIEW = "pending_review"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass
class QualificationCriteria:
    """Qualification criteria configuration."""

    id: int
    name: str
    description: str
    min_score: int = 0
    max_score: Optional[int] = None
    required_fields: List[str] = None
    engagement_requirements: Dict[str, Any] = None
    custom_rules: Dict[str, Any] = None
    is_active: bool = True
    created_at: datetime = None
    updated_at: datetime = None

    def __post_init__(self):
        if self.required_fields is None:
            self.required_fields = []
        if self.engagement_requirements is None:
            self.engagement_requirements = {}
        if self.custom_rules is None:
            self.custom_rules = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        if isinstance(data.get("created_at"), datetime):
            data["created_at"] = data["created_at"].isoformat()
        if isinstance(data.get("updated_at"), datetime):
            data["updated_at"] = data["updated_at"].isoformat()
        return data


@dataclass
class QualificationResult:
    """Result of business qualification."""

    business_id: int
    status: QualificationStatus
    score: int
    criteria_id: int
    details: Dict[str, Any]
    qualified_at: datetime = None
    notes: str = ""

    def __post_init__(self):
        if self.qualified_at is None:
            self.qualified_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        data["status"] = (
            data["status"].value
            if isinstance(data["status"], QualificationStatus)
            else data["status"]
        )
        if isinstance(data.get("qualified_at"), datetime):
            data["qualified_at"] = data["qualified_at"].isoformat()
        return data


class QualificationEngine:
    """Engine for evaluating business qualification criteria."""

    def __init__(self):
        """Initialize the qualification engine."""
        self.storage = get_storage_instance()
        self.engagement_analytics = EngagementAnalytics()
        self.scoring_engine = ScoringEngine()
        logger.info("Initialized QualificationEngine")

    def qualify_business(
        self, business_id: int, criteria_id: int, force_rescore: bool = False
    ) -> QualificationResult:
        """Qualify a single business against criteria.

        Args:
            business_id: Business ID to qualify
            criteria_id: Qualification criteria ID
            force_rescore: Whether to force re-scoring the business

        Returns:
            QualificationResult with qualification status and details
        """
        try:
            # Get business data
            business = self.storage.get_business_by_id(business_id)
            if not business:
                return QualificationResult(
                    business_id=business_id,
                    status=QualificationStatus.REJECTED,
                    score=0,
                    criteria_id=criteria_id,
                    details={"error": "Business not found"},
                    notes="Business not found in database",
                )

            # Get qualification criteria
            criteria = self.get_criteria_by_id(criteria_id)
            if not criteria:
                return QualificationResult(
                    business_id=business_id,
                    status=QualificationStatus.REJECTED,
                    score=0,
                    criteria_id=criteria_id,
                    details={"error": "Criteria not found"},
                    notes="Qualification criteria not found",
                )

            if not criteria.is_active:
                return QualificationResult(
                    business_id=business_id,
                    status=QualificationStatus.REJECTED,
                    score=0,
                    criteria_id=criteria_id,
                    details={"error": "Criteria inactive"},
                    notes="Qualification criteria is not active",
                )

            # Evaluate qualification
            result = self._evaluate_qualification(business, criteria, force_rescore)

            logger.info(
                f"Qualified business {business_id} with criteria {criteria_id}: {result.status.value}"
            )

            return result

        except Exception as e:
            logger.error(f"Error qualifying business {business_id}: {e}")
            return QualificationResult(
                business_id=business_id,
                status=QualificationStatus.REJECTED,
                score=0,
                criteria_id=criteria_id,
                details={"error": str(e)},
                notes=f"Error during qualification: {e}",
            )

    def qualify_businesses_bulk(
        self, business_ids: List[int], criteria_id: int, force_rescore: bool = False
    ) -> List[QualificationResult]:
        """Qualify multiple businesses in bulk.

        Args:
            business_ids: List of business IDs to qualify
            criteria_id: Qualification criteria ID
            force_rescore: Whether to force re-scoring businesses

        Returns:
            List of QualificationResult objects
        """
        results = []

        logger.info(f"Starting bulk qualification of {len(business_ids)} businesses")

        for business_id in business_ids:
            try:
                result = self.qualify_business(business_id, criteria_id, force_rescore)
                results.append(result)
            except Exception as e:
                logger.error(
                    f"Error in bulk qualification for business {business_id}: {e}"
                )
                results.append(
                    QualificationResult(
                        business_id=business_id,
                        status=QualificationStatus.REJECTED,
                        score=0,
                        criteria_id=criteria_id,
                        details={"error": str(e)},
                        notes=f"Error during bulk qualification: {e}",
                    )
                )

        qualified_count = len(
            [r for r in results if r.status == QualificationStatus.QUALIFIED]
        )
        logger.info(
            f"Bulk qualification completed: {qualified_count}/{len(results)} qualified"
        )

        return results

    def _evaluate_qualification(
        self,
        business: Dict[str, Any],
        criteria: QualificationCriteria,
        force_rescore: bool = False,
    ) -> QualificationResult:
        """Evaluate a business against qualification criteria.

        Args:
            business: Business data dictionary
            criteria: Qualification criteria
            force_rescore: Whether to force re-scoring

        Returns:
            QualificationResult with evaluation details
        """
        details = {
            "criteria_name": criteria.name,
            "business_name": business.get("name", "Unknown"),
            "checks": {},
            "engagement_data": {},
            "custom_rule_results": {},
        }

        business_id = business["id"]

        # 1. Check required fields
        missing_fields = self._check_required_fields(business, criteria.required_fields)
        details["checks"]["required_fields"] = {
            "required": criteria.required_fields,
            "missing": missing_fields,
            "passed": len(missing_fields) == 0,
        }

        if missing_fields:
            return QualificationResult(
                business_id=business_id,
                status=QualificationStatus.INSUFFICIENT_DATA,
                score=0,
                criteria_id=criteria.id,
                details=details,
                notes=f"Missing required fields: {', '.join(missing_fields)}",
            )

        # 2. Check business score
        current_score = business.get("score", 0)
        if force_rescore or current_score == 0:
            try:
                # Re-score the business
                self.scoring_engine.load_rules()
                score_result = self.scoring_engine.score_business(business)
                current_score = score_result.get("score", 0)

                # Update business score in storage
                self.storage.update_business_score(business_id, current_score)

            except Exception as e:
                logger.warning(f"Could not re-score business {business_id}: {e}")

        score_passed = current_score >= criteria.min_score and (
            criteria.max_score is None or current_score <= criteria.max_score
        )

        details["checks"]["score"] = {
            "current_score": current_score,
            "min_required": criteria.min_score,
            "max_allowed": criteria.max_score,
            "passed": score_passed,
        }

        if not score_passed:
            return QualificationResult(
                business_id=business_id,
                status=QualificationStatus.REJECTED,
                score=current_score,
                criteria_id=criteria.id,
                details=details,
                notes=f"Score {current_score} does not meet criteria (min: {criteria.min_score})",
            )

        # 3. Check engagement requirements
        engagement_passed = True
        if criteria.engagement_requirements:
            engagement_data = self._check_engagement_requirements(
                business_id, criteria.engagement_requirements
            )
            details["engagement_data"] = engagement_data

            engagement_passed = engagement_data.get("passed", False)
            if not engagement_passed:
                return QualificationResult(
                    business_id=business_id,
                    status=QualificationStatus.REJECTED,
                    score=current_score,
                    criteria_id=criteria.id,
                    details=details,
                    notes="Does not meet engagement requirements",
                )

        # 4. Check custom rules
        custom_rules_passed = True
        if criteria.custom_rules:
            custom_results = self._check_custom_rules(business, criteria.custom_rules)
            details["custom_rule_results"] = custom_results

            custom_rules_passed = custom_results.get("passed", False)
            if not custom_rules_passed:
                return QualificationResult(
                    business_id=business_id,
                    status=QualificationStatus.REJECTED,
                    score=current_score,
                    criteria_id=criteria.id,
                    details=details,
                    notes=f"Failed custom rules: {custom_results.get('failed_rules', [])}",
                )

        # All checks passed - business is qualified
        return QualificationResult(
            business_id=business_id,
            status=QualificationStatus.QUALIFIED,
            score=current_score,
            criteria_id=criteria.id,
            details=details,
            notes="All qualification criteria met",
        )

    def _check_required_fields(
        self, business: Dict[str, Any], required_fields: List[str]
    ) -> List[str]:
        """Check which required fields are missing.

        Args:
            business: Business data dictionary
            required_fields: List of required field names

        Returns:
            List of missing field names
        """
        missing_fields = []

        for field in required_fields:
            value = business.get(field)
            if value is None or (isinstance(value, str) and value.strip() == ""):
                missing_fields.append(field)

        return missing_fields

    def _check_engagement_requirements(
        self, business_id: int, requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check engagement requirements for a business.

        Args:
            business_id: Business ID to check
            requirements: Engagement requirements dictionary

        Returns:
            Dictionary with engagement check results
        """
        try:
            # Use business_id as user_id for engagement tracking
            # In a real system, you'd have a proper mapping
            user_id = f"business_{business_id}"

            # Get engagement summary
            engagement_summary = self.engagement_analytics.get_user_engagement_summary(
                user_id, days=30
            )

            results = {
                "engagement_summary": engagement_summary,
                "requirements": requirements,
                "checks": {},
                "passed": True,
            }

            # Check minimum page views
            min_page_views = requirements.get("min_page_views", 0)
            actual_page_views = engagement_summary.get("total_page_views", 0)
            page_views_passed = actual_page_views >= min_page_views

            results["checks"]["page_views"] = {
                "required": min_page_views,
                "actual": actual_page_views,
                "passed": page_views_passed,
            }

            if not page_views_passed:
                results["passed"] = False

            # Check minimum session duration
            min_session_duration = requirements.get("min_session_duration", 0)
            actual_session_duration = engagement_summary.get("avg_session_duration", 0)
            session_duration_passed = actual_session_duration >= min_session_duration

            results["checks"]["session_duration"] = {
                "required": min_session_duration,
                "actual": actual_session_duration,
                "passed": session_duration_passed,
            }

            if not session_duration_passed:
                results["passed"] = False

            # Check for conversions
            if requirements.get("has_conversions", False):
                actual_conversions = engagement_summary.get("conversions", 0)
                conversions_passed = actual_conversions > 0

                results["checks"]["conversions"] = {
                    "required": True,
                    "actual": actual_conversions,
                    "passed": conversions_passed,
                }

                if not conversions_passed:
                    results["passed"] = False

            # Check for multiple sessions
            if requirements.get("multiple_sessions", False):
                actual_sessions = engagement_summary.get("total_sessions", 0)
                multiple_sessions_passed = actual_sessions > 1

                results["checks"]["multiple_sessions"] = {
                    "required": True,
                    "actual": actual_sessions,
                    "passed": multiple_sessions_passed,
                }

                if not multiple_sessions_passed:
                    results["passed"] = False

            return results

        except Exception as e:
            logger.error(
                f"Error checking engagement requirements for business {business_id}: {e}"
            )
            return {"error": str(e), "passed": False}

    def _check_custom_rules(
        self, business: Dict[str, Any], custom_rules: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check custom qualification rules.

        Args:
            business: Business data dictionary
            custom_rules: Custom rules dictionary

        Returns:
            Dictionary with custom rule check results
        """
        results = {
            "rules": custom_rules,
            "checks": {},
            "passed": True,
            "failed_rules": [],
        }

        try:
            # Check if has website
            if custom_rules.get("has_website", False):
                website = business.get("website", "").strip()
                has_website_passed = bool(website and website != "")

                results["checks"]["has_website"] = {
                    "required": True,
                    "actual": bool(website),
                    "passed": has_website_passed,
                }

                if not has_website_passed:
                    results["passed"] = False
                    results["failed_rules"].append("has_website")

            # Check minimum business score (different from criteria min_score)
            min_business_score = custom_rules.get("min_business_score")
            if min_business_score is not None:
                actual_score = business.get("score", 0)
                score_passed = actual_score >= min_business_score

                results["checks"]["min_business_score"] = {
                    "required": min_business_score,
                    "actual": actual_score,
                    "passed": score_passed,
                }

                if not score_passed:
                    results["passed"] = False
                    results["failed_rules"].append("min_business_score")

            # Check complete profile
            if custom_rules.get("has_complete_profile", False):
                required_profile_fields = [
                    "name",
                    "email",
                    "website",
                    "phone",
                    "address",
                ]
                missing_profile_fields = self._check_required_fields(
                    business, required_profile_fields
                )
                complete_profile_passed = len(missing_profile_fields) == 0

                results["checks"]["has_complete_profile"] = {
                    "required": True,
                    "missing_fields": missing_profile_fields,
                    "passed": complete_profile_passed,
                }

                if not complete_profile_passed:
                    results["passed"] = False
                    results["failed_rules"].append("has_complete_profile")

            # Check enterprise indicators
            if custom_rules.get("enterprise_indicators", False):
                # Check for enterprise indicators like employee count, revenue, etc.
                enterprise_passed = (
                    business.get("employee_count", 0) >= 100
                    or business.get("annual_revenue", 0) >= 1000000
                    or any(
                        keyword in business.get("category", "").lower()
                        for keyword in ["enterprise", "corporation", "inc", "llc"]
                    )
                )

                results["checks"]["enterprise_indicators"] = {
                    "required": True,
                    "actual": enterprise_passed,
                    "passed": enterprise_passed,
                }

                if not enterprise_passed:
                    results["passed"] = False
                    results["failed_rules"].append("enterprise_indicators")

            return results

        except Exception as e:
            logger.error(f"Error checking custom rules: {e}")
            results["error"] = str(e)
            results["passed"] = False
            return results

    def get_criteria_by_id(self, criteria_id: int) -> Optional[QualificationCriteria]:
        """Get qualification criteria by ID.

        Args:
            criteria_id: Criteria ID

        Returns:
            QualificationCriteria object or None if not found
        """
        try:
            with self.storage.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT * FROM handoff_qualification_criteria
                    WHERE id = %s
                    """,
                    (criteria_id,),
                )

                row = cursor.fetchone()
                if not row:
                    return None

                # Convert row to dictionary
                columns = [desc[0] for desc in cursor.description]
                criteria_data = dict(zip(columns, row))

                # Parse JSON fields
                criteria_data["required_fields"] = json.loads(
                    criteria_data["required_fields"] or "[]"
                )
                criteria_data["engagement_requirements"] = json.loads(
                    criteria_data["engagement_requirements"] or "{}"
                )
                criteria_data["custom_rules"] = json.loads(
                    criteria_data["custom_rules"] or "{}"
                )

                return QualificationCriteria(**criteria_data)

        except Exception as e:
            logger.error(f"Error getting criteria {criteria_id}: {e}")
            return None

    def list_criteria(self, active_only: bool = True) -> List[QualificationCriteria]:
        """List all qualification criteria.

        Args:
            active_only: Whether to return only active criteria

        Returns:
            List of QualificationCriteria objects
        """
        try:
            with self.storage.cursor() as cursor:
                query = """
                    SELECT * FROM handoff_qualification_criteria
                """
                if active_only:
                    query += " WHERE is_active = TRUE"
                query += " ORDER BY name"

                cursor.execute(query)
                rows = cursor.fetchall()

                criteria_list = []
                columns = [desc[0] for desc in cursor.description]

                for row in rows:
                    criteria_data = dict(zip(columns, row))

                    # Parse JSON fields
                    criteria_data["required_fields"] = json.loads(
                        criteria_data["required_fields"] or "[]"
                    )
                    criteria_data["engagement_requirements"] = json.loads(
                        criteria_data["engagement_requirements"] or "{}"
                    )
                    criteria_data["custom_rules"] = json.loads(
                        criteria_data["custom_rules"] or "{}"
                    )

                    criteria_list.append(QualificationCriteria(**criteria_data))

                return criteria_list

        except Exception as e:
            logger.error(f"Error listing criteria: {e}")
            return []

    def create_criteria(
        self,
        name: str,
        description: str,
        min_score: int = 0,
        max_score: Optional[int] = None,
        required_fields: List[str] = None,
        engagement_requirements: Dict[str, Any] = None,
        custom_rules: Dict[str, Any] = None,
    ) -> Optional[int]:
        """Create new qualification criteria.

        Args:
            name: Criteria name (must be unique)
            description: Criteria description
            min_score: Minimum business score required
            max_score: Maximum business score allowed
            required_fields: List of required business fields
            engagement_requirements: Engagement tracking requirements
            custom_rules: Custom qualification rules

        Returns:
            Created criteria ID or None if failed
        """
        try:
            with self.storage.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO handoff_qualification_criteria
                    (name, description, min_score, max_score, required_fields,
                     engagement_requirements, custom_rules)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        name,
                        description,
                        min_score,
                        max_score,
                        json.dumps(required_fields or []),
                        json.dumps(engagement_requirements or {}),
                        json.dumps(custom_rules or {}),
                    ),
                )

                result = cursor.fetchone()
                criteria_id = result[0] if result else None

                if criteria_id:
                    logger.info(
                        f"Created qualification criteria: {name} (ID: {criteria_id})"
                    )

                return criteria_id

        except Exception as e:
            logger.error(f"Error creating criteria: {e}")
            return None
