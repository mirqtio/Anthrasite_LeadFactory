"""
Unified GPT-4o Node for LeadFactory Pipeline.

This module consolidates mockup and email generation into a single terminal
GPT-4o node, optimizing prompt construction and ensuring all required inputs
flow to this unified endpoint. Now integrated with the LLM fallback system
for robust and cost-effective operations.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from leadfactory.config.node_config import (
    NodeType,
    get_capability_registry,
    get_capability_status,
    get_enabled_capabilities,
)
from leadfactory.llm.integrated_client import IntegratedLLMClient, get_global_llm_client
from leadfactory.llm.provider import LLMError
from leadfactory.storage.factory import get_storage
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class UnifiedGPT4ONode:
    """
    Unified terminal node for generating both mockup and email content using GPT-4o.

    This class consolidates the functionality of separate mockup and email generation
    nodes into a single, optimized endpoint that leverages GPT-4o for both tasks.
    Now integrated with the LLM fallback system for robust operations.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the unified GPT-4o node.

        Args:
            config: Optional configuration dictionary for the node
        """
        self.config = config or {}
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("OPENAI_API_KEY not found in environment variables")

        # LLM client will be initialized lazily
        self.llm_client: Optional[IntegratedLLMClient] = None
        self._use_fallback_system = self.config.get("use_fallback_system", True)

    async def initialize_llm_client(self):
        """Initialize the LLM client if not already done."""
        if self._use_fallback_system and self.llm_client is None:
            try:
                self.llm_client = await get_global_llm_client()
                logger.info("Initialized LLM client with fallback system")
            except Exception as e:
                logger.error(f"Failed to initialize LLM client: {e}")
                logger.info("Falling back to mock implementation")
                self._use_fallback_system = False

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

    def construct_unified_prompt(
        self, business_data: Dict[str, Any], mockup_enabled: bool, email_enabled: bool
    ) -> str:
        """
        Construct an optimized prompt for unified mockup and email generation.

        Args:
            business_data: Dictionary containing business information
            mockup_enabled: Whether mockup generation is enabled
            email_enabled: Whether email generation is enabled

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
        "business_id": {business_data.get('id', 'null')},
        "confidence_score": 0.0,
        "processing_notes": ["note1", "note2"]
    }}
}}

Ensure the output is valid JSON and both the mockup concept and email are highly personalized to this specific business.
"""

        if not mockup_enabled:
            prompt = prompt.replace("TASK 1 - WEBSITE MOCKUP CONCEPT:", "")
            prompt = prompt.replace("mockup_concept", "", 1)
            prompt = prompt.replace("}", "", 1)

        if not email_enabled:
            prompt = prompt.replace("TASK 2 - PERSONALIZED OUTREACH EMAIL:", "")
            prompt = prompt.replace("email_content", "", 1)
            prompt = prompt.replace("}", "", 1)

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
        # Run async generation in sync context
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self._generate_unified_content_async(business_data)
        )

    async def _generate_unified_content_async(
        self, business_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Async implementation of unified content generation.

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

        # Check enabled capabilities for this node
        enabled_capabilities = get_enabled_capabilities(NodeType.FINAL_OUTPUT)
        capability_names = [cap.name for cap in enabled_capabilities]

        # Check if mockup generation is enabled
        mockup_enabled = "mockup_generation" in capability_names
        email_enabled = "email_generation" in capability_names

        logger.info(
            f"Generating unified content for business {business_data.get('id')} "
            f"(mockup: {mockup_enabled}, email: {email_enabled})"
        )

        # Construct the optimized prompt based on enabled capabilities
        prompt = self.construct_unified_prompt(
            business_data, mockup_enabled, email_enabled
        )

        # Initialize LLM client if using fallback system
        await self.initialize_llm_client()

        # Generate content using LLM or fallback to mock
        if self._use_fallback_system and self.llm_client:
            try:
                response = await self._generate_with_llm(
                    prompt, business_data, mockup_enabled, email_enabled
                )
                return response
            except Exception as e:
                logger.error(f"LLM generation failed: {e}")
                logger.info("Falling back to mock implementation")
                # Continue to mock implementation below

        # Mock implementation fallback
        return self._generate_mock_response(
            business_data, mockup_enabled, email_enabled, prompt, validation
        )

    async def _generate_with_llm(
        self,
        prompt: str,
        business_data: Dict[str, Any],
        mockup_enabled: bool,
        email_enabled: bool,
    ) -> Dict[str, Any]:
        """
        Generate content using the LLM client with fallback system.

        Args:
            prompt: The constructed prompt
            business_data: Business data dictionary
            mockup_enabled: Whether mockup generation is enabled
            email_enabled: Whether email generation is enabled

        Returns:
            Dictionary containing generation results
        """
        try:
            # Generate response using LLM client
            llm_response = await self.llm_client.generate_response(
                prompt=prompt,
                parameters={
                    "max_tokens": 2000,
                    "temperature": 0.7,
                    "response_format": {"type": "json_object"},
                },
                request_id=f"unified_gpt4o_{business_data.get('id', 'unknown')}",
            )

            # Parse the JSON response
            try:
                content = json.loads(llm_response.content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {e}")
                # Try to extract JSON from response
                content = self._extract_json_from_response(llm_response.content)

            # Validate and structure the response
            structured_content = self._structure_llm_response(
                content, mockup_enabled, email_enabled, business_data
            )

            # Add LLM metadata
            structured_content["metadata"] = {
                "generation_timestamp": self._get_timestamp(),
                "business_id": business_data.get("id"),
                "confidence_score": 0.9,  # Higher confidence for LLM
                "enabled_capabilities": [
                    cap.name for cap in get_enabled_capabilities(NodeType.FINAL_OUTPUT)
                ],
                "mockup_generated": mockup_enabled,
                "email_generated": email_enabled,
                "llm_provider": llm_response.provider,
                "llm_model": llm_response.model,
                "tokens_used": llm_response.tokens_used,
                "cost": llm_response.cost,
                "latency": llm_response.latency,
                "processing_notes": [
                    f"Generated using {llm_response.provider} ({llm_response.model})",
                    f"Cost: ${llm_response.cost:.4f}",
                    f"Tokens: {llm_response.tokens_used}",
                    f"Latency: {llm_response.latency:.2f}s",
                ],
            }

            return {
                "success": True,
                "content": structured_content,
                "prompt_used": prompt,
                "validation_result": self.validate_inputs(business_data),
                "llm_response": {
                    "provider": llm_response.provider,
                    "model": llm_response.model,
                    "cost": llm_response.cost,
                    "tokens_used": llm_response.tokens_used,
                    "latency": llm_response.latency,
                },
            }

        except LLMError as e:
            logger.error(f"LLM error during generation: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during LLM generation: {e}")
            raise

    def _extract_json_from_response(self, response_text: str) -> Dict[str, Any]:
        """
        Extract JSON from LLM response text.

        Args:
            response_text: The raw response text from LLM

        Returns:
            Extracted JSON dictionary or empty dict if extraction fails
        """
        try:
            # Try to find JSON block in response
            import re

            json_pattern = r"\{.*\}"
            matches = re.findall(json_pattern, response_text, re.DOTALL)

            if matches:
                # Try to parse the first JSON match
                return json.loads(matches[0])
            else:
                logger.warning("No JSON found in LLM response, returning empty dict")
                return {}

        except Exception as e:
            logger.error(f"Failed to extract JSON from response: {e}")
            return {}

    def _structure_llm_response(
        self,
        content: Dict[str, Any],
        mockup_enabled: bool,
        email_enabled: bool,
        business_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Structure and validate LLM response content.

        Args:
            content: Raw content from LLM
            mockup_enabled: Whether mockup generation is enabled
            email_enabled: Whether email generation is enabled
            business_data: Business data dictionary

        Returns:
            Structured content dictionary
        """
        structured = {}

        # Extract mockup content if enabled and present
        if mockup_enabled and "mockup_concept" in content:
            mockup = content["mockup_concept"]
            structured["mockup_concept"] = {
                "design_theme": mockup.get("design_theme", "Modern Professional"),
                "color_scheme": mockup.get(
                    "color_scheme", ["#2C3E50", "#3498DB", "#ECF0F1"]
                ),
                "layout_sections": mockup.get("layout_sections", []),
                "content_recommendations": mockup.get("content_recommendations", []),
                "ux_enhancements": mockup.get("ux_enhancements", []),
                "mobile_considerations": mockup.get("mobile_considerations", []),
                "cta_recommendations": mockup.get("cta_recommendations", []),
            }
        elif mockup_enabled:
            # Provide fallback mockup structure if LLM didn't generate it properly
            structured["mockup_concept"] = {
                "design_theme": "Modern Professional",
                "color_scheme": ["#2C3E50", "#3498DB", "#ECF0F1"],
                "layout_sections": [
                    {
                        "section_name": "Hero Section",
                        "description": "Compelling headline with clear value proposition",
                        "priority": "high",
                    }
                ],
                "content_recommendations": [],
                "ux_enhancements": [],
                "mobile_considerations": [],
                "cta_recommendations": [],
            }

        # Extract email content if enabled and present
        if email_enabled and "email_content" in content:
            email = content["email_content"]
            structured["email_content"] = {
                "subject": email.get(
                    "subject",
                    f"Website improvement ideas for {business_data.get('name', 'your business')}",
                ),
                "greeting": email.get("greeting", "Hi there,"),
                "opening": email.get(
                    "opening",
                    f"I came across {business_data.get('name', 'your website')} and was impressed.",
                ),
                "value_proposition": email.get(
                    "value_proposition",
                    "I noticed opportunities to help you attract more customers online.",
                ),
                "specific_insights": email.get("specific_insights", []),
                "call_to_action": email.get(
                    "call_to_action",
                    "Would you be interested in discussing these ideas?",
                ),
                "closing": email.get("closing", "Best regards,\nYour Web Consultant"),
                "full_email_html": self._generate_email_html(business_data),
            }
        elif email_enabled:
            # Provide fallback email structure if LLM didn't generate it properly
            structured["email_content"] = {
                "subject": f"Website improvement ideas for {business_data.get('name', 'your business')}",
                "greeting": "Hi there,",
                "opening": f"I came across {business_data.get('name', 'your website')} and was impressed.",
                "value_proposition": "I noticed opportunities to help you attract more customers online.",
                "specific_insights": [
                    "Your website has great potential for improvement"
                ],
                "call_to_action": "Would you be interested in discussing these ideas?",
                "closing": "Best regards,\nYour Web Consultant",
                "full_email_html": self._generate_email_html(business_data),
            }

        return structured

    def _generate_mock_response(
        self,
        business_data: Dict[str, Any],
        mockup_enabled: bool,
        email_enabled: bool,
        prompt: str,
        validation: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate mock response for unified content generation.

        Args:
            business_data: Dictionary containing business information
            mockup_enabled: Whether mockup generation is enabled
            email_enabled: Whether email generation is enabled
            prompt: The constructed prompt
            validation: Validation result dictionary

        Returns:
            Dictionary containing mock generation results
        """
        # Mock response structure (replace with actual GPT-4o API call)
        mock_response = {}

        # Only include mockup if capability is enabled
        if mockup_enabled:
            mock_response["mockup_concept"] = {
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
                        "area": "Homepage headline",
                        "current_issue": "Generic messaging",
                        "improvement": "Add specific value proposition",
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
            }

        # Only include email if capability is enabled
        if email_enabled:
            mock_response["email_content"] = {
                "subject": f"Quick website improvement ideas for {business_data.get('name', 'your business')}",
                "greeting": f"Hi there,",
                "opening": f"I came across {business_data.get('name', 'your website')} and was impressed by your work in the {business_data.get('industry', 'industry')}.",
                "value_proposition": "I noticed a few opportunities that could help you attract more customers online.",
                "specific_insights": [
                    "Your website could benefit from a clearer value proposition",
                    "Adding customer testimonials would build trust",
                ],
                "call_to_action": "Would you be interested in a quick 15-minute call to discuss these ideas?",
                "closing": "Best regards,\nYour Web Consultant",
                "full_email_html": self._generate_email_html(business_data),
            }

        # Add metadata about what was generated
        mock_response["metadata"] = {
            "generation_timestamp": self._get_timestamp(),
            "business_id": business_data.get("id"),
            "confidence_score": 0.85,
            "enabled_capabilities": [
                cap.name for cap in get_enabled_capabilities(NodeType.FINAL_OUTPUT)
            ],
            "mockup_generated": mockup_enabled,
            "email_generated": email_enabled,
            "processing_notes": [
                "Mock implementation - replace with actual GPT-4o API call",
                "Validation passed successfully",
                f"Generated content based on enabled capabilities: {', '.join([cap.name for cap in get_enabled_capabilities(NodeType.FINAL_OUTPUT)])}",
            ],
        }

        return {
            "success": True,
            "content": mock_response,
            "prompt_used": prompt,
            "validation_result": validation,
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
        try:
            # Fetch business data
            business_data = self._fetch_business_data(business_id)
            if not business_data:
                return {"success": False, "error": f"Business {business_id} not found"}

            # Generate unified content
            result = self.generate_unified_content(business_data)

            if result["success"]:
                # Save results to database
                save_success = self.save_unified_results(business_id, result["content"])
                result["saved_to_db"] = save_success

            return result

        except Exception as e:
            logger.error(f"Error processing business {business_id}: {e}")
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


# Async versions for better integration with fallback system
async def generate_unified_content_for_business_async(
    business_id: int,
) -> Dict[str, Any]:
    """
    Generate unified content for a single business (async version).

    Args:
        business_id: ID of the business

    Returns:
        Dictionary containing generation results
    """
    node = UnifiedGPT4ONode()

    # Get business data
    storage = get_storage()
    business_data = storage.get_business_data(business_id)

    if not business_data:
        return {"success": False, "error": f"Business {business_id} not found"}

    # Generate content using async method
    result = await node._generate_unified_content_async(business_data)

    # Save results if successful
    if result.get("success"):
        saved = node.save_unified_results(business_id, result["content"])
        result["saved_to_database"] = saved

    return result


async def process_all_businesses_unified_async(
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Process all businesses through the unified GPT-4o node (async version).

    Args:
        limit: Maximum number of businesses to process

    Returns:
        Dictionary containing processing summary
    """
    businesses = get_businesses_needing_unified_processing(limit)

    if not businesses:
        return {
            "success": True,
            "message": "No businesses need unified processing",
            "processed": 0,
            "results": [],
        }

    logger.info(
        f"Processing {len(businesses)} businesses for unified content generation"
    )

    results = []
    successful = 0
    failed = 0

    # Process businesses concurrently with controlled concurrency
    semaphore = asyncio.Semaphore(5)  # Limit concurrent processing

    async def process_business(business):
        async with semaphore:
            try:
                result = await generate_unified_content_for_business_async(
                    business["id"]
                )
                if result.get("success"):
                    successful += 1
                else:
                    failed += 1
                return result
            except Exception as e:
                logger.error(f"Error processing business {business['id']}: {e}")
                failed += 1
                return {
                    "success": False,
                    "business_id": business["id"],
                    "error": str(e),
                }

    # Process all businesses concurrently
    tasks = [process_business(business) for business in businesses]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Count successes and failures
    successful = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
    failed = len(results) - successful

    logger.info(
        f"Unified processing complete: {successful} successful, {failed} failed"
    )

    return {
        "success": True,
        "processed": len(businesses),
        "successful": successful,
        "failed": failed,
        "results": results,
    }


# Enhanced convenience functions with fallback system integration
def get_llm_client_status() -> Dict[str, Any]:
    """
    Get the status of the LLM client and fallback system.

    Returns:
        Dictionary containing status information
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    async def _get_status():
        try:
            from leadfactory.llm.integrated_client import get_global_llm_client

            client = await get_global_llm_client()
            return await client.get_provider_status()
        except Exception as e:
            return {
                "error": f"Failed to get LLM client status: {e}",
                "fallback_available": False,
            }

    return loop.run_until_complete(_get_status())


def get_llm_cost_summary() -> Dict[str, Any]:
    """
    Get cost summary from the LLM fallback system.

    Returns:
        Cost summary dictionary
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    async def _get_cost_summary():
        try:
            from leadfactory.llm.integrated_client import get_global_llm_client

            client = await get_global_llm_client()
            return await client.get_cost_summary()
        except Exception as e:
            return {
                "error": f"Failed to get cost summary: {e}",
                "cost_monitoring_available": False,
            }

    return loop.run_until_complete(_get_cost_summary())


__all__ = [
    "UnifiedGPT4ONode",
    "get_businesses_needing_unified_processing",
    "process_all_businesses_unified",
    "generate_unified_content_for_business",
    "validate_unified_dependencies",
    "generate_unified_content_for_business_async",
    "process_all_businesses_unified_async",
    "get_llm_client_status",
    "get_llm_cost_summary",
]
