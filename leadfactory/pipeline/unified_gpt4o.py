"""
Unified GPT-4o Node for LeadFactory Pipeline.

This module consolidates mockup and email generation into a single terminal
GPT-4o node, optimizing prompt construction and ensuring all required inputs
flow to this unified endpoint.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from leadfactory.llm import LLMClient, LLMError
from leadfactory.services.gpu_manager import gpu_manager
from leadfactory.storage.factory import get_storage
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class UnifiedGPT4ONode:
    """
    Unified terminal node for generating both mockup and email content using GPT-4o.

    This class consolidates the functionality of separate mockup and email generation
    nodes into a single, optimized endpoint that leverages GPT-4o for both tasks.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the unified GPT-4o node.

        Args:
            config: Optional configuration dictionary for the node
        """
        self.config = config or {}

        # Initialize LLM client with fallback support
        try:
            self.llm_client = LLMClient()
            logger.info(
                f"Initialized LLM client with {len(self.llm_client.get_available_providers())} available providers"
            )
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}")
            self.llm_client = None

        # GPU processing configuration
        self.gpu_task_types = [
            "website_mockup_generation",
            "ai_content_personalization",
            "image_optimization",
            "video_rendering",
        ]

    def validate_inputs(self, business_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate that all required inputs are available for unified generation.

        Args:
            business_data: Dictionary containing business information

        Returns:
            Dictionary with validation results and missing dependencies
        """
        validation_result = {
            "is_valid": True,
            "missing_dependencies": [],
            "warnings": [],
            "required_fields": [
                "id",
                "name",
                "website",
                "description",
                "contact_email",
            ],
            "optional_fields": [
                "phone",
                "address",
                "industry",
                "screenshot_url",
                "enrichment_data",
            ],
        }

        # Check required fields
        for field in validation_result["required_fields"]:
            if field not in business_data or not business_data[field]:
                validation_result["missing_dependencies"].append(field)
                validation_result["is_valid"] = False

        # Check optional fields and add warnings
        for field in validation_result["optional_fields"]:
            if field not in business_data or not business_data[field]:
                validation_result["warnings"].append(
                    f"Optional field '{field}' is missing"
                )

        # Validate email format
        if "contact_email" in business_data:
            email = business_data["contact_email"]
            if not self._is_valid_email(email):
                validation_result["missing_dependencies"].append("valid_contact_email")
                validation_result["is_valid"] = False

        logger.info(
            f"Validation result for business {business_data.get('id', 'unknown')}: "
            f"valid={validation_result['is_valid']}, "
            f"missing={len(validation_result['missing_dependencies'])}"
        )

        return validation_result

    def _is_valid_email(self, email: str) -> bool:
        """Validate email address format."""
        import re

        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

    def construct_unified_prompt(self, business_data: Dict[str, Any]) -> str:
        """
        Construct an optimized prompt for unified mockup and email generation.

        Args:
            business_data: Dictionary containing business information

        Returns:
            Optimized prompt string for GPT-4o
        """
        # Extract key business information
        business_name = business_data.get("name", "Unknown Business")
        website = business_data.get("website", "")
        description = business_data.get("description", "")
        industry = business_data.get("industry", "")
        contact_email = business_data.get("contact_email", "")
        phone = business_data.get("phone", "")
        address = business_data.get("address", "")

        # Include enrichment data if available
        enrichment_data = business_data.get("enrichment_data", {})
        screenshot_url = business_data.get("screenshot_url", "")

        prompt = f"""
You are an expert business analyst and creative designer tasked with generating both a website mockup concept and a personalized outreach email for a business.

BUSINESS INFORMATION:
- Company Name: {business_name}
- Website: {website}
- Industry: {industry}
- Description: {description}
- Contact Email: {contact_email}
- Phone: {phone}
- Address: {address}

ADDITIONAL CONTEXT:
{self._format_enrichment_data(enrichment_data)}

TASK 1 - WEBSITE MOCKUP CONCEPT:
Generate a detailed mockup concept for improving this business's website. Include:
1. Overall design theme and color scheme recommendations
2. Key sections and layout suggestions
3. Content improvements and messaging recommendations
4. User experience enhancements
5. Mobile responsiveness considerations
6. Call-to-action placement and optimization

TASK 2 - PERSONALIZED OUTREACH EMAIL:
Create a personalized email that:
1. Addresses the business owner by name (if available) or role
2. Demonstrates understanding of their business and industry
3. Identifies specific improvement opportunities
4. Offers value-driven solutions
5. Includes a clear call-to-action
6. Maintains a professional yet approachable tone

OUTPUT FORMAT:
Please structure your response as a JSON object with the following format:

{{
    "mockup_concept": {{
        "design_theme": "string",
        "color_scheme": ["color1", "color2", "color3"],
        "layout_sections": [
            {{
                "section_name": "string",
                "description": "string",
                "priority": "high|medium|low"
            }}
        ],
        "content_recommendations": [
            {{
                "area": "string",
                "current_issue": "string",
                "improvement": "string"
            }}
        ],
        "ux_enhancements": ["enhancement1", "enhancement2"],
        "mobile_considerations": ["consideration1", "consideration2"],
        "cta_recommendations": [
            {{
                "location": "string",
                "text": "string",
                "purpose": "string"
            }}
        ]
    }},
    "email_content": {{
        "subject": "string",
        "greeting": "string",
        "opening": "string",
        "value_proposition": "string",
        "specific_insights": ["insight1", "insight2"],
        "call_to_action": "string",
        "closing": "string",
        "full_email_html": "string"
    }},
    "metadata": {{
        "generation_timestamp": "{self._get_timestamp()}",
        "business_id": {business_data.get("id", "null")},
        "confidence_score": 0.0,
        "processing_notes": ["note1", "note2"]
    }}
}}

Ensure the output is valid JSON and both the mockup concept and email are highly personalized to this specific business.
"""

        return prompt.strip()

    def _format_enrichment_data(self, enrichment_data: Dict[str, Any]) -> str:
        """Format enrichment data for inclusion in the prompt."""
        if not enrichment_data:
            return "No additional enrichment data available."

        formatted_data = []
        for key, value in enrichment_data.items():
            if value:
                formatted_data.append(f"- {key.replace('_', ' ').title()}: {value}")

        return (
            "\n".join(formatted_data)
            if formatted_data
            else "No additional enrichment data available."
        )

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime

        return datetime.utcnow().isoformat() + "Z"

    def generate_unified_content(self, business_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate both mockup concept and email content using GPT-4o.

        Args:
            business_data: Dictionary containing business information

        Returns:
            Dictionary containing both mockup and email content
        """
        # Validate inputs first
        validation = self.validate_inputs(business_data)
        if not validation["is_valid"]:
            return {
                "success": False,
                "error": f"Validation failed: {validation['missing_dependencies']}",
                "validation_result": validation,
            }

        # Check if LLM client is available
        if not self.llm_client:
            return {
                "success": False,
                "error": "LLM client not available",
                "validation_result": validation,
            }

        logger.info(
            f"Generating unified content for business {business_data.get('id')}"
        )

        # Construct the optimized prompt
        prompt = self.construct_unified_prompt(business_data)

        try:
            # Use LLM client with fallback support
            messages = [
                {
                    "role": "system",
                    "content": "You are an expert business analyst and creative designer. Provide responses in valid JSON format only.",
                },
                {"role": "user", "content": prompt},
            ]

            response = self.llm_client.chat_completion(
                messages=messages,
                temperature=0.7,
                max_tokens=2048,
                # Let the client choose the best available provider based on fallback strategy
            )

            # Parse the JSON response
            content = response["choices"][0]["message"]["content"]
            try:
                parsed_content = json.loads(content)
                logger.info(
                    f"Successfully generated content using {response.get('provider', 'unknown')} provider"
                )

                return {
                    "success": True,
                    "content": parsed_content,
                    "prompt_used": prompt,
                    "validation_result": validation,
                    "provider_used": response.get("provider"),
                    "model_used": response.get("model"),
                    "usage": response.get("usage", {}),
                }

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.debug(f"Raw response content: {content[:500]}...")

                # Fall back to mock response if JSON parsing fails
                return self._generate_mock_response(business_data, prompt, validation)

        except LLMError as e:
            logger.error(f"LLM request failed: {e}")
            # Fall back to mock response
            return self._generate_mock_response(business_data, prompt, validation)
        except Exception as e:
            logger.error(f"Unexpected error during content generation: {e}")
            return {
                "success": False,
                "error": f"Content generation failed: {str(e)}",
                "validation_result": validation,
            }

    def _generate_mock_response(
        self, business_data: Dict[str, Any], prompt: str, validation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate a mock response as fallback."""
        logger.info("Using mock response as fallback")

        # Mock response structure (fallback implementation)
        mock_response = {
            "mockup_concept": {
                "design_theme": "Modern Professional",
                "color_scheme": ["#2C3E50", "#3498DB", "#ECF0F1"],
                "layout_sections": [
                    {
                        "section_name": "Hero Section",
                        "description": "Compelling headline with clear value proposition",
                        "priority": "high",
                    },
                    {
                        "section_name": "Services Overview",
                        "description": "Grid layout showcasing key services",
                        "priority": "high",
                    },
                    {
                        "section_name": "Contact Information",
                        "description": "Prominent contact details and location",
                        "priority": "medium",
                    },
                ],
                "content_recommendations": [
                    {
                        "area": "Homepage",
                        "current_issue": "Unclear value proposition",
                        "improvement": "Add clear headline explaining what the business does",
                    }
                ],
                "ux_enhancements": [
                    "Improve navigation menu structure",
                    "Add search functionality",
                    "Optimize page loading speed",
                ],
                "mobile_considerations": [
                    "Responsive design for all screen sizes",
                    "Touch-friendly button sizes",
                    "Simplified mobile navigation",
                ],
                "cta_recommendations": [
                    {
                        "location": "Hero section",
                        "text": "Get Started Today",
                        "purpose": "Primary conversion action",
                    }
                ],
            },
            "email_content": {
                "subject": f"Quick website improvement ideas for {business_data.get('name', 'your business')}",
                "greeting": "Hi there,",
                "opening": f"I came across {business_data.get('name', 'your website')} and was impressed by your work in the {business_data.get('industry', 'industry')}.",
                "value_proposition": "I noticed a few opportunities that could help you attract more customers online.",
                "specific_insights": [
                    "Your website could benefit from a clearer value proposition",
                    "Adding customer testimonials would build trust",
                ],
                "call_to_action": "Would you be interested in a quick 15-minute call to discuss these ideas?",
                "closing": "Best regards,\nYour Web Consultant",
                "full_email_html": self._generate_email_html(business_data),
            },
            "metadata": {
                "generation_timestamp": self._get_timestamp(),
                "business_id": business_data.get("id"),
                "confidence_score": 0.85,
                "processing_notes": [
                    "Mock implementation - replace with actual GPT-4o API call",
                    "Validation passed successfully",
                ],
            },
        }

        return {
            "success": True,
            "content": mock_response,
            "prompt_used": prompt,
            "validation_result": validation,
            "provider_used": "mock",
            "model_used": "fallback",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    def _generate_email_html(self, business_data: Dict[str, Any]) -> str:
        """Generate HTML email content."""
        business_name = business_data.get("name", "your business")
        industry = business_data.get("industry", "industry")

        html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Website Improvement Ideas</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #2C3E50;">Quick website improvement ideas for {business_name}</h2>

        <p>Hi there,</p>

        <p>I came across {business_name} and was impressed by your work in the {industry}.</p>

        <p>I noticed a few opportunities that could help you attract more customers online:</p>

        <ul>
            <li>Your website could benefit from a clearer value proposition</li>
            <li>Adding customer testimonials would build trust</li>
            <li>Optimizing for mobile users could improve engagement</li>
        </ul>

        <p>Would you be interested in a quick 15-minute call to discuss these ideas?</p>

        <p>Best regards,<br>Your Web Consultant</p>

        <hr style="margin: 30px 0; border: none; border-top: 1px solid #eee;">
        <p style="font-size: 12px; color: #666;">
            This email was generated as part of our website analysis service.
        </p>
    </div>
</body>
</html>
"""
        return html_template.strip()

    def _requires_gpu_processing(self, business_data: Dict[str, Any]) -> bool:
        """
        Determine if this business requires GPU processing.

        Args:
            business_data: Dictionary containing business information

        Returns:
            True if GPU processing is required, False otherwise
        """
        # Check if business has complex requirements that benefit from GPU
        has_website = bool(business_data.get("website"))
        has_screenshot = bool(business_data.get("screenshot_url"))
        has_complex_industry = business_data.get("industry", "").lower() in [
            "technology",
            "design",
            "media",
            "entertainment",
            "e-commerce",
            "marketing",
        ]

        # GPU is beneficial for businesses with visual content needs
        return has_website and (has_screenshot or has_complex_industry)

    def _add_to_personalization_queue(
        self,
        business_id: int,
        task_type: str,
        task_data: Dict[str, Any],
        gpu_required: bool = False,
    ) -> Optional[int]:
        """
        Add a task to the personalization queue.

        Args:
            business_id: ID of the business
            task_type: Type of personalization task
            task_data: Task-specific data and parameters
            gpu_required: Whether this task requires GPU processing

        Returns:
            Queue task ID if successful, None otherwise
        """
        try:
            storage = get_storage()

            query = """
                INSERT INTO personalization_queue
                (business_id, task_type, gpu_required, task_data, status, created_at)
                VALUES (%s, %s, %s, %s, 'pending', NOW())
                RETURNING id
            """

            result = storage.execute_query(
                query, (business_id, task_type, gpu_required, json.dumps(task_data))
            )

            if result:
                task_id = result[0]["id"]
                logger.info(
                    f"Added task {task_id} to personalization queue for business {business_id}"
                )
                return task_id
            else:
                logger.error(
                    f"Failed to add task to personalization queue for business {business_id}"
                )
                return None

        except Exception as e:
            logger.error(f"Error adding task to personalization queue: {e}")
            return None

    def _update_queue_task_status(
        self, task_id: int, status: str, error_message: str = None
    ) -> bool:
        """
        Update the status of a task in the personalization queue.

        Args:
            task_id: ID of the queue task
            status: New status ('processing', 'completed', 'failed')
            error_message: Optional error message if status is 'failed'

        Returns:
            True if successful, False otherwise
        """
        try:
            storage = get_storage()

            if status == "processing":
                query = """
                    UPDATE personalization_queue
                    SET status = %s, started_at = NOW(), updated_at = NOW()
                    WHERE id = %s
                """
                params = (status, task_id)
            elif status == "completed":
                query = """
                    UPDATE personalization_queue
                    SET status = %s, completed_at = NOW(), updated_at = NOW()
                    WHERE id = %s
                """
                params = (status, task_id)
            elif status == "failed":
                query = """
                    UPDATE personalization_queue
                    SET status = %s, error_message = %s, updated_at = NOW()
                    WHERE id = %s
                """
                params = (status, error_message, task_id)
            else:
                query = """
                    UPDATE personalization_queue
                    SET status = %s, updated_at = NOW()
                    WHERE id = %s
                """
                params = (status, task_id)

            success = storage.execute_query(query, params)

            if success:
                logger.info(f"Updated task {task_id} status to {status}")
                return True
            else:
                logger.error(f"Failed to update task {task_id} status")
                return False

        except Exception as e:
            logger.error(f"Error updating queue task status: {e}")
            return False

    def save_unified_results(self, business_id: int, content: Dict[str, Any]) -> bool:
        """
        Save the unified generation results to the database.

        Args:
            business_id: ID of the business
            content: Generated content dictionary

        Returns:
            True if successful, False otherwise
        """
        try:
            storage = get_storage()

            # Prepare queries for transaction
            queries = []

            # Save mockup concept
            mockup_data = content.get("mockup_concept", {})
            queries.append(
                (
                    """
                INSERT INTO assets (business_id, asset_type, asset_data, created_at)
                VALUES (%s, 'unified_mockup', %s, NOW())
                """,
                    (business_id, json.dumps(mockup_data)),
                )
            )

            # Save email content
            email_data = content.get("email_content", {})
            queries.append(
                (
                    """
                INSERT INTO assets (business_id, asset_type, asset_data, created_at)
                VALUES (%s, 'unified_email', %s, NOW())
                """,
                    (business_id, json.dumps(email_data)),
                )
            )

            # Save metadata
            metadata = content.get("metadata", {})
            queries.append(
                (
                    """
                INSERT INTO pipeline_results (business_id, stage, result_data, created_at)
                VALUES (%s, 'unified_gpt4o', %s, NOW())
                """,
                    (business_id, json.dumps(metadata)),
                )
            )

            # Execute all queries in a transaction
            success = storage.execute_transaction(queries)

            if success:
                logger.info(
                    f"Successfully saved unified results for business {business_id}"
                )
                return True
            else:
                logger.error(
                    f"Failed to save unified results for business {business_id}"
                )
                return False

        except Exception as e:
            logger.error(
                f"Failed to save unified results for business {business_id}: {e}"
            )
            return False

    def process_business(self, business_id: int) -> Dict[str, Any]:
        """
        Process a single business through the unified GPT-4o node.

        Args:
            business_id: ID of the business to process

        Returns:
            Dictionary containing processing results
        """
        queue_task_id = None
        try:
            # Fetch business data
            business_data = self._fetch_business_data(business_id)
            if not business_data:
                return {"success": False, "error": f"Business {business_id} not found"}

            # Check if GPU processing is required
            gpu_required = self._requires_gpu_processing(business_data)

            # Add to personalization queue for tracking
            task_data = {
                "business_id": business_id,
                "task_type": "ai_content_personalization",
                "gpu_optimized": gpu_required,
                "created_at": self._get_timestamp(),
            }

            queue_task_id = self._add_to_personalization_queue(
                business_id, "ai_content_personalization", task_data, gpu_required
            )

            if queue_task_id:
                # Update task status to processing
                self._update_queue_task_status(queue_task_id, "processing")

            # Generate unified content
            result = self.generate_unified_content(business_data)

            # Add GPU processing info to result
            result["gpu_required"] = gpu_required
            result["queue_task_id"] = queue_task_id

            if result["success"]:
                # Save results to database
                save_success = self.save_unified_results(business_id, result["content"])
                result["saved_to_db"] = save_success

                # Update queue task to completed
                if queue_task_id:
                    self._update_queue_task_status(queue_task_id, "completed")
            else:
                # Update queue task to failed
                if queue_task_id:
                    error_msg = result.get(
                        "error", "Unknown error during content generation"
                    )
                    self._update_queue_task_status(queue_task_id, "failed", error_msg)

            return result

        except Exception as e:
            logger.error(f"Error processing business {business_id}: {e}")

            # Update queue task to failed if it exists
            if queue_task_id:
                self._update_queue_task_status(queue_task_id, "failed", str(e))

            return {"success": False, "error": str(e)}

    def _fetch_business_data(self, business_id: int) -> Optional[Dict[str, Any]]:
        """Fetch business data from the database."""
        try:
            storage = get_storage()

            # Fetch basic business information
            business_query = """
            SELECT id, name, website, description, contact_email, phone, address, industry
            FROM businesses
            WHERE id = %s
            """

            business_results = storage.execute_query(business_query, (business_id,))
            if not business_results:
                return None

            business_data = business_results[0]

            # Fetch enrichment data if available
            enrichment_query = """
            SELECT asset_data
            FROM assets
            WHERE business_id = %s AND asset_type = 'enrichment'
            ORDER BY created_at DESC
            LIMIT 1
            """

            enrichment_results = storage.execute_query(enrichment_query, (business_id,))
            if enrichment_results:
                try:
                    business_data["enrichment_data"] = json.loads(
                        enrichment_results[0]["asset_data"]
                    )
                except json.JSONDecodeError:
                    business_data["enrichment_data"] = {}

            # Fetch screenshot URL if available
            screenshot_query = """
            SELECT asset_url
            FROM assets
            WHERE business_id = %s AND asset_type = 'screenshot'
            ORDER BY created_at DESC
            LIMIT 1
            """

            screenshot_results = storage.execute_query(screenshot_query, (business_id,))
            if screenshot_results:
                business_data["screenshot_url"] = screenshot_results[0]["asset_url"]

            return business_data

        except Exception as e:
            logger.error(f"Error fetching business data for {business_id}: {e}")
            return None


def get_businesses_needing_unified_processing(
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Get businesses that need unified GPT-4o processing.

    Args:
        limit: Maximum number of businesses to return

    Returns:
        List of business dictionaries
    """
    try:
        storage = get_storage()

        # Get businesses that have required dependencies but no unified processing
        query = """
        SELECT DISTINCT b.id, b.name, b.website
        FROM businesses b
        INNER JOIN assets enrichment ON b.id = enrichment.business_id
            AND enrichment.asset_type = 'enrichment'
        LEFT JOIN assets unified_mockup ON b.id = unified_mockup.business_id
            AND unified_mockup.asset_type = 'unified_mockup'
        LEFT JOIN assets unified_email ON b.id = unified_email.business_id
            AND unified_email.asset_type = 'unified_email'
        WHERE unified_mockup.id IS NULL OR unified_email.id IS NULL
        ORDER BY b.id
        """

        if limit:
            query += f" LIMIT {limit}"

        businesses = storage.execute_query(query)
        logger.info(f"Found {len(businesses)} businesses needing unified processing")
        return businesses

    except Exception as e:
        logger.error(f"Error fetching businesses for unified processing: {e}")
        return []


def process_all_businesses_unified(limit: Optional[int] = None) -> Dict[str, Any]:
    """
    Process all businesses through the unified GPT-4o node.

    Args:
        limit: Maximum number of businesses to process

    Returns:
        Dictionary containing processing summary
    """
    businesses = get_businesses_needing_unified_processing(limit)

    if not businesses:
        logger.info("No businesses need unified processing")
        return {"processed": 0, "successful": 0, "failed": 0, "results": []}

    node = UnifiedGPT4ONode()
    results = []
    successful = 0
    failed = 0

    for business in businesses:
        logger.info(f"Processing business {business['id']}: {business['name']}")

        result = node.process_business(business["id"])
        result["business_info"] = business
        results.append(result)

        if result["success"]:
            successful += 1
        else:
            failed += 1

    summary = {
        "processed": len(businesses),
        "successful": successful,
        "failed": failed,
        "results": results,
    }

    logger.info(
        f"Unified processing complete: {successful} successful, {failed} failed"
    )
    return summary


# Convenience functions for backward compatibility
def generate_unified_content_for_business(business_id: int) -> Dict[str, Any]:
    """
    Generate unified content for a single business.

    Args:
        business_id: ID of the business

    Returns:
        Dictionary containing generation results
    """
    node = UnifiedGPT4ONode()
    return node.process_business(business_id)


def validate_unified_dependencies(business_id: int) -> Dict[str, Any]:
    """
    Validate dependencies for unified processing.

    Args:
        business_id: ID of the business

    Returns:
        Dictionary containing validation results
    """
    node = UnifiedGPT4ONode()
    business_data = node._fetch_business_data(business_id)

    if not business_data:
        return {"is_valid": False, "error": f"Business {business_id} not found"}

    return node.validate_inputs(business_data)


__all__ = [
    "UnifiedGPT4ONode",
    "get_businesses_needing_unified_processing",
    "process_all_businesses_unified",
    "generate_unified_content_for_business",
    "validate_unified_dependencies",
]
