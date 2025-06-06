"""Mockup QA service for managing quality assurance workflows."""

from typing import Any, Optional

from leadfactory.storage import get_storage_instance
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class MockupQAService:
    """Service for managing mockup quality assurance workflows."""

    def __init__(self):
        """Initialize the mockup QA service."""
        self.storage = get_storage_instance()
        logger.info("Initialized MockupQAService")

    def evaluate_mockup_quality(self, mockup_content: dict[str, Any]) -> dict[str, Any]:
        """Evaluate the quality of a mockup using automated checks.

        Args:
            mockup_content: The mockup content to evaluate

        Returns:
            Dictionary with quality evaluation results
        """
        try:
            evaluation = {
                "overall_score": 5.0,
                "quality_factors": {},
                "recommendations": [],
                "requires_human_review": False,
            }

            mockup = mockup_content.get("mockup", {})
            layout_elements = mockup.get("layout_elements", [])
            content_recommendations = mockup.get("content_recommendations", [])

            # Factor 1: Layout completeness (30% weight)
            layout_score = self._evaluate_layout_completeness(layout_elements)
            evaluation["quality_factors"]["layout_completeness"] = layout_score

            # Factor 2: Content quality (25% weight)
            content_score = self._evaluate_content_quality(content_recommendations)
            evaluation["quality_factors"]["content_quality"] = content_score

            # Factor 3: AI confidence (20% weight)
            ai_confidence = mockup.get("ai_confidence_score", 0.5)
            evaluation["quality_factors"]["ai_confidence"] = ai_confidence * 10

            # Factor 4: Specificity and detail (25% weight)
            detail_score = self._evaluate_detail_level(
                layout_elements, content_recommendations
            )
            evaluation["quality_factors"]["detail_level"] = detail_score

            # Calculate weighted overall score
            weights = {
                "layout_completeness": 0.30,
                "content_quality": 0.25,
                "ai_confidence": 0.20,
                "detail_level": 0.25,
            }

            overall_score = sum(
                evaluation["quality_factors"][factor] * weight
                for factor, weight in weights.items()
            )

            evaluation["overall_score"] = round(overall_score, 1)

            # Determine if human review is required (score < 5)
            evaluation["requires_human_review"] = overall_score < 5.0

            # Generate recommendations based on weak areas
            evaluation["recommendations"] = self._generate_recommendations(
                evaluation["quality_factors"]
            )

            logger.info(f"Evaluated mockup quality: {overall_score}/10")
            return evaluation

        except Exception as e:
            logger.error(f"Error evaluating mockup quality: {e}")
            return {
                "overall_score": 0.0,
                "quality_factors": {},
                "recommendations": ["Error occurred during quality evaluation"],
                "requires_human_review": True,
            }

    def _evaluate_layout_completeness(self, layout_elements: list[dict]) -> float:
        """Evaluate layout completeness (0-10 scale)."""
        if not layout_elements:
            return 2.0

        # Essential sections for a good mockup
        essential_sections = ["header", "hero", "navigation", "contact", "footer"]
        found_sections = set()

        for element in layout_elements:
            section_name = element.get("section_name", "").lower()
            for essential in essential_sections:
                if essential in section_name:
                    found_sections.add(essential)

        # Score based on coverage of essential sections
        coverage_ratio = len(found_sections) / len(essential_sections)
        base_score = coverage_ratio * 8  # Up to 8 points for coverage

        # Bonus points for having more than minimum elements
        if len(layout_elements) >= 5:
            base_score += 1
        if len(layout_elements) >= 8:
            base_score += 1

        return min(10.0, base_score)

    def _evaluate_content_quality(self, content_recommendations: list[dict]) -> float:
        """Evaluate content quality (0-10 scale)."""
        if not content_recommendations:
            return 3.0

        total_score = 0
        for rec in content_recommendations:
            rec_score = 0

            # Check for specific and actionable improvements
            improvement = rec.get("improvement", "").lower()
            current_issue = rec.get("current_issue", "").lower()

            # Higher score for specific, actionable language
            if any(
                word in improvement
                for word in ["add", "create", "implement", "include"]
            ):
                rec_score += 2
            if any(
                word in improvement
                for word in ["specific", "clear", "detailed", "prominent"]
            ):
                rec_score += 1
            if len(improvement) > 20:  # Detailed recommendations
                rec_score += 1
            if len(current_issue) > 10:  # Identifies specific issues
                rec_score += 1

            total_score += min(5, rec_score)

        # Average and scale to 10
        avg_score = total_score / len(content_recommendations)
        return min(10.0, avg_score * 2)

    def _evaluate_detail_level(
        self, layout_elements: list[dict], content_recommendations: list[dict]
    ) -> float:
        """Evaluate level of detail and specificity (0-10 scale)."""
        detail_score = 0

        # Layout detail
        for element in layout_elements:
            description = element.get("description", "")
            if len(description) > 30:  # Detailed descriptions
                detail_score += 1
            if element.get("priority"):  # Has priority assigned
                detail_score += 0.5

        # Content detail
        for rec in content_recommendations:
            if len(rec.get("improvement", "")) > 30:  # Detailed improvements
                detail_score += 1
            if rec.get("area"):  # Specific area identified
                detail_score += 0.5

        # Scale to 10
        max_possible = len(layout_elements) * 1.5 + len(content_recommendations) * 1.5
        if max_possible > 0:
            return min(10.0, (detail_score / max_possible) * 10)
        else:
            return 5.0

    def _generate_recommendations(self, quality_factors: dict[str, float]) -> list[str]:
        """Generate improvement recommendations based on quality factors."""
        recommendations = []

        if quality_factors.get("layout_completeness", 5) < 6:
            recommendations.append(
                "Consider adding more essential layout sections (header, navigation, hero, contact, footer)"
            )

        if quality_factors.get("content_quality", 5) < 6:
            recommendations.append(
                "Improve content recommendations with more specific and actionable suggestions"
            )

        if quality_factors.get("ai_confidence", 5) < 6:
            recommendations.append(
                "AI confidence is low - consider manual review or prompt refinement"
            )

        if quality_factors.get("detail_level", 5) < 6:
            recommendations.append(
                "Add more detailed descriptions and specific implementation guidance"
            )

        return recommendations

    def trigger_mockup_regeneration(
        self,
        business_id: int,
        revised_prompt: str,
        original_mockup_id: Optional[int] = None,
    ) -> Optional[int]:
        """Trigger regeneration of a mockup with revised prompt.

        Args:
            business_id: Business ID to regenerate mockup for
            revised_prompt: Revised prompt for regeneration
            original_mockup_id: Original mockup ID for versioning

        Returns:
            New mockup ID if successful, None otherwise
        """
        try:
            # Get business data
            business = self.storage.get_business_by_id(business_id)
            if not business:
                logger.error(f"Business {business_id} not found for regeneration")
                return None

            # Get latest version for this business
            existing_versions = self.storage.get_mockup_versions_by_business(
                business_id
            )
            next_version = max([v["version"] for v in existing_versions], default=0) + 1

            # Import GPT node for regeneration
            from leadfactory.pipeline.unified_gpt4o import UnifiedGPT4ONode

            node = UnifiedGPT4ONode()

            # Add revised prompt to business data
            business["revised_prompt"] = revised_prompt
            business["regeneration_request"] = True

            # Generate new content
            logger.info(
                f"Regenerating mockup for business {business_id} with revised prompt"
            )
            result = node.generate_unified_content(business)

            if result.get("success") and result.get("content"):
                # Create new mockup version
                content = result["content"]
                ai_confidence = content.get("mockup", {}).get(
                    "ai_confidence_score", 0.5
                )

                mockup_id = self.storage.create_mockup(
                    business_id=business_id,
                    content=content,
                    version=next_version,
                    status="pending",
                    ai_confidence=ai_confidence,
                )

                if mockup_id:
                    logger.info(
                        f"Created new mockup version {next_version} (ID: {mockup_id}) for business {business_id}"
                    )
                    return mockup_id

            logger.error(f"Failed to generate content for business {business_id}")
            return None

        except Exception as e:
            logger.error(f"Error triggering mockup regeneration: {e}")
            return None

    def auto_approve_high_quality_mockups(self) -> int:
        """Automatically approve mockups with high quality scores.

        Returns:
            Number of mockups automatically approved
        """
        try:
            # Get pending mockups
            pending_mockups = self.storage.list_mockups(status="pending", limit=100)

            approved_count = 0
            for mockup in pending_mockups:
                # Evaluate quality
                evaluation = self.evaluate_mockup_quality(mockup["content"])

                # Auto-approve if score >= 8 and doesn't require human review
                if (
                    evaluation["overall_score"] >= 8.0
                    and not evaluation["requires_human_review"]
                ):

                    success = self.storage.apply_qa_override(
                        mockup_id=mockup["id"],
                        new_status="approved",
                        qa_score=evaluation["overall_score"],
                        reviewer_notes="Automatically approved based on high quality score",
                    )

                    if success:
                        approved_count += 1
                        logger.info(
                            f"Auto-approved mockup {mockup['id']} with score {evaluation['overall_score']}"
                        )

            logger.info(f"Auto-approved {approved_count} high-quality mockups")
            return approved_count

        except Exception as e:
            logger.error(f"Error in auto-approval process: {e}")
            return 0

    def flag_low_quality_mockups(self) -> int:
        """Flag mockups with low quality scores for human review.

        Returns:
            Number of mockups flagged for review
        """
        try:
            # Get pending mockups
            pending_mockups = self.storage.list_mockups(status="pending", limit=100)

            flagged_count = 0
            for mockup in pending_mockups:
                # Evaluate quality
                evaluation = self.evaluate_mockup_quality(mockup["content"])

                # Flag if score < 4 or requires human review
                if (
                    evaluation["overall_score"] < 4.0
                    or evaluation["requires_human_review"]
                ):

                    # Update with quality evaluation
                    recommendations_text = "; ".join(evaluation["recommendations"])

                    success = self.storage.apply_qa_override(
                        mockup_id=mockup["id"],
                        new_status="needs_revision",
                        qa_score=evaluation["overall_score"],
                        reviewer_notes=f"Flagged for review: {recommendations_text}",
                    )

                    if success:
                        flagged_count += 1
                        logger.info(
                            f"Flagged mockup {mockup['id']} for review with score {evaluation['overall_score']}"
                        )

            logger.info(f"Flagged {flagged_count} low-quality mockups for review")
            return flagged_count

        except Exception as e:
            logger.error(f"Error in flagging process: {e}")
            return 0

    def get_qa_dashboard_stats(self) -> dict[str, Any]:
        """Get statistics for the QA dashboard.

        Returns:
            Dictionary with QA statistics
        """
        try:
            stats = {
                "total_mockups": 0,
                "by_status": {},
                "avg_qa_score": 0.0,
                "pending_review": 0,
                "auto_approved": 0,
                "needs_revision": 0,
            }

            # Get all mockups
            all_mockups = self.storage.list_mockups(limit=1000)
            stats["total_mockups"] = len(all_mockups)

            # Count by status
            status_counts = {}
            qa_scores = []

            for mockup in all_mockups:
                status = mockup["status"]
                status_counts[status] = status_counts.get(status, 0) + 1

                if mockup["qa_score"]:
                    qa_scores.append(mockup["qa_score"])

            stats["by_status"] = status_counts
            stats["pending_review"] = status_counts.get("pending", 0)
            stats["auto_approved"] = status_counts.get("approved", 0)
            stats["needs_revision"] = status_counts.get("needs_revision", 0)

            # Calculate average QA score
            if qa_scores:
                stats["avg_qa_score"] = round(sum(qa_scores) / len(qa_scores), 1)

            return stats

        except Exception as e:
            logger.error(f"Error getting QA dashboard stats: {e}")
            return {
                "total_mockups": 0,
                "by_status": {},
                "avg_qa_score": 0.0,
                "pending_review": 0,
                "auto_approved": 0,
                "needs_revision": 0,
            }
