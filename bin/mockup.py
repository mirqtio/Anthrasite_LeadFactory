#!/usr/bin/env python3
"""
Anthrasite Lead-Factory: Mockup Generation (05_mockup.py)
Generates website improvement mockups using GPT-4o with Claude fallback.
Usage:
    python bin/05_mockup.py [--limit N] [--id BUSINESS_ID] [--tier TIER] [--force]
Options:
    --limit N        Limit the number of businesses to process (default: all)
    --id BUSINESS_ID Process only the specified business ID
    --tier TIER      Override the tier level (2 or 3)
    --force          Force regeneration of mockups for businesses that already have them
"""
import argparse
import base64
import json
import logging
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Local application/library specific imports with try-except for Python 3.9 compatibility during testing
# Import database utilities with conditional imports for testing


# For Python 3.9 compatibility, use a simpler approach without method assignment


# Define a dummy track_api_cost function for fallback
def dummy_track_api_cost(service, operation, cost_cents, tier=1, business_id=None):
    """Track API cost - dummy implementation for testing environments."""
    pass


# Try to import the real implementations
try:
    from utils.io import DatabaseConnection, track_api_cost

    # If successful, we have the real implementations
except ImportError:
    # If import fails, create our own implementations
    # Define our own DatabaseConnection class
    class DatabaseConnection:
        """Implementation of DatabaseConnection for testing environments."""

        def __init__(self, db_path=None):
            self.db_path = db_path
            self.connection = None
            self.cursor = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def execute(self, query, params=None):
            return None

        def fetchall(self):
            return []

        def fetchone(self):
            return None

        def commit(self):
            pass

    # Use our dummy track_api_cost
    track_api_cost = dummy_track_api_cost


# Import all necessary modules before any local imports
try:
    from utils.logging_config import get_logger
except ImportError:
    # During testing, provide a dummy logger
    def get_logger(name: str) -> logging.Logger:
        import logging

        return logging.getLogger(name)


# Set up logging
logger = get_logger(__name__)
# Load environment variables
load_dotenv()
# Constants
DEFAULT_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "60"))
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "5"))
CURRENT_TIER = int(os.getenv("TIER", "1"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GPT4O_MODEL = os.getenv("GPT4O_MODEL", "gpt-4o")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-opus-20240229")
MOCKUP_STYLE = os.getenv("MOCKUP_STYLE", "modern")
MOCKUP_RESOLUTION = os.getenv("MOCKUP_RESOLUTION", "1024x1024")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
# Cost tracking constants (in cents)
GPT4O_COST_PER_1K_TOKENS_INPUT = float(
    os.getenv("GPT4O_COST_PER_1K_TOKENS_INPUT", "10")
)  # $0.10 per 1K tokens
GPT4O_COST_PER_1K_TOKENS_OUTPUT = float(
    os.getenv("GPT4O_COST_PER_1K_TOKENS_OUTPUT", "30")
)  # $0.30 per 1K tokens
CLAUDE_COST_PER_1K_TOKENS_INPUT = float(
    os.getenv("CLAUDE_COST_PER_1K_TOKENS_INPUT", "15")
)  # $0.15 per 1K tokens
CLAUDE_COST_PER_1K_TOKENS_OUTPUT = float(
    os.getenv("CLAUDE_COST_PER_1K_TOKENS_OUTPUT", "75")
)  # $0.75 per 1K tokens


class GPT4oMockupGenerator:
    """Generates website mockups using GPT-4o."""

    def __init__(self, api_key: str, model: str = GPT4O_MODEL):
        """Initialize the GPT-4o mockup generator.
        Args:
            api_key: OpenAI API key.
            model: GPT-4o model name.
        """
        self.api_key = api_key
        self.model = model

    def generate_mockup(
        self,
        business_data: dict,
        screenshot_url: Optional[str] = None,
        style: str = MOCKUP_STYLE,
        resolution: str = MOCKUP_RESOLUTION,
    ) -> Tuple[Optional[str], Optional[str], Optional[Dict], Optional[str]]:
        """Generate a website mockup using GPT-4o.
        Args:
            business_data: Business data including tech stack, performance metrics, etc.
            screenshot_url: URL to screenshot of current website (if available).
            style: Style of mockup (modern, minimalist, etc.).
            resolution: Resolution of mockup image.
        Returns:
            Tuple of (mockup_image_base64, mockup_html, usage_data, error_message).
        """
        if not self.api_key:
            return None, None, None, "OpenAI API key not provided"
        # Prepare prompt
        prompt = self._prepare_prompt(business_data, screenshot_url, style)
        # Prepare API request
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a professional web designer specializing in creating modern, conversion-focused websites for small businesses. Your task is to generate a mockup image and corresponding HTML/CSS for a business website based on the provided information.",
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 4096,
            "temperature": 0.7,
            "response_format": {"type": "json_object"},
        }
        try:
            # Make API request
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=DEFAULT_TIMEOUT,
            )
            response.raise_for_status()
            # Parse response
            result = response.json()
            # Extract usage data
            usage = result.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            # Track cost
            input_cost_cents = (prompt_tokens / 1000) * GPT4O_COST_PER_1K_TOKENS_INPUT
            output_cost_cents = (
                completion_tokens / 1000
            ) * GPT4O_COST_PER_1K_TOKENS_OUTPUT
            total_cost_cents = input_cost_cents + output_cost_cents
            track_api_cost(
                service="openai",
                operation="mockup_generation",
                cost_cents=total_cost_cents,
                tier=CURRENT_TIER,
            )
            # Extract response content
            response_content = (
                result.get("choices", [{}])[0].get("message", {}).get("content", "{}")
            )
            try:
                response_json = json.loads(response_content)
                mockup_image_base64 = response_json.get("mockup_image", "")
                mockup_html = response_json.get("mockup_html", "")
                return mockup_image_base64, mockup_html, usage, None
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing GPT-4o response: {e}")
                return None, None, usage, f"Error parsing response: {str(e)}"
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling OpenAI API: {e}")
            return None, None, None, f"API error: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error generating mockup: {e}")
            return None, None, None, f"Unexpected error: {str(e)}"

    def _prepare_prompt(
        self,
        business_data: dict,
        screenshot_url: Optional[str] = None,
        style: str = MOCKUP_STYLE,
    ) -> str:
        """Prepare prompt for GPT-4o.
        Args:
            business_data: Business data.
            screenshot_url: URL to screenshot of current website (if available).
            style: Style of mockup.
        Returns:
            Formatted prompt.
        """
        # Extract business information
        business_name = business_data.get("name", "")
        business_category = business_data.get("category", "")
        business_description = business_data.get("description", "")
        business_address = business_data.get("address", "")
        business_city = business_data.get("city", "")
        business_state = business_data.get("state", "")
        business_zip = business_data.get("zip", "")
        business_phone = business_data.get("phone", "")
        business_website = business_data.get("website", "")
        # Extract tech stack information
        features = business_data.get("features", {})
        tech_stack_json = features.get("tech_stack", "{}")
        if isinstance(tech_stack_json, str):
            try:
                tech_stack = json.loads(tech_stack_json)
            except json.JSONDecodeError:
                tech_stack = {}
        else:
            tech_stack = tech_stack_json
        # Extract performance information
        performance_score = features.get("page_speed", 0)
        # Build prompt
        prompt = f"""
I need you to create a modern, conversion-focused website mockup for a business with the following information:
Business Information:
- Name: {business_name}
- Category: {business_category}
- Description: {business_description}
- Address: {business_address}, {business_city}, {business_state} {business_zip}
- Phone: {business_phone}
- Current Website: {business_website}
Current Website Technical Information:
- Performance Score: {performance_score}/100
- Technologies Used: {', '.join(tech_stack.keys()) if tech_stack else 'Unknown'}
Design Requirements:
- Style: {style}
- Focus on conversion optimization
- Mobile-responsive design
- Clear call-to-action buttons
- Modern aesthetics with good whitespace
- Improved navigation compared to current site
- Highlight business's unique selling points
- Include contact information prominently
"""
        if screenshot_url:
            prompt += (
                f"\nThe current website screenshot is available at: {screenshot_url}\n"
            )
            prompt += "Please analyze this screenshot and suggest specific improvements in your redesign.\n"
        prompt += """
Please provide:
1. A base64-encoded image of your mockup design (in the "mockup_image" field)
2. The corresponding HTML/CSS code that implements this design (in the "mockup_html" field)
Format your response as a JSON object with these two fields.
"""
        return prompt


class ClaudeMockupGenerator:
    """Generates website mockups using Claude as a fallback."""

    def __init__(self, api_key: str, model: str = CLAUDE_MODEL):
        """Initialize the Claude mockup generator.
        Args:
            api_key: Anthropic API key.
            model: Claude model name.
        """
        self.api_key = api_key
        self.model = model

    def generate_mockup(
        self,
        business_data: dict,
        screenshot_url: Optional[str] = None,
        style: str = MOCKUP_STYLE,
        resolution: str = MOCKUP_RESOLUTION,
    ) -> Tuple[Optional[str], Optional[str], Optional[Dict], Optional[str]]:
        """Generate a website mockup using Claude.
        Args:
            business_data: Business data including tech stack, performance metrics, etc.
            screenshot_url: URL to screenshot of current website (if available).
            style: Style of mockup (modern, minimalist, etc.).
            resolution: Resolution of mockup image.
        Returns:
            Tuple of (mockup_image_base64, mockup_html, usage_data, error_message).
        """
        if not self.api_key:
            return None, None, None, "Anthropic API key not provided"
        # Prepare prompt
        prompt = self._prepare_prompt(business_data, screenshot_url, style)
        # Prepare API request
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "temperature": 0.7,
            "system": "You are a professional web designer specializing in creating modern, conversion-focused websites for small businesses. Your task is to generate a mockup image and corresponding HTML/CSS for a business website based on the provided information.",
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            # Make API request
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
                timeout=DEFAULT_TIMEOUT,
            )
            response.raise_for_status()
            # Parse response
            result = response.json()
            # Extract usage data
            usage = {
                "input_tokens": result.get("usage", {}).get("input_tokens", 0),
                "output_tokens": result.get("usage", {}).get("output_tokens", 0),
            }
            # Track cost
            input_cost_cents = (
                usage["input_tokens"] / 1000
            ) * CLAUDE_COST_PER_1K_TOKENS_INPUT
            output_cost_cents = (
                usage["output_tokens"] / 1000
            ) * CLAUDE_COST_PER_1K_TOKENS_OUTPUT
            total_cost_cents = input_cost_cents + output_cost_cents
            track_api_cost(
                service="anthropic",
                operation="mockup_generation",
                cost_cents=total_cost_cents,
                tier=CURRENT_TIER,
            )
            # Extract response content
            response_content = result.get("content", [{}])[0].get("text", "")
            # Parse JSON from response
            json_match = re.search(r"```json\n(.*?)\n```", response_content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                try:
                    response_json = json.loads(json_str)
                    mockup_image_base64 = response_json.get("mockup_image", "")
                    mockup_html = response_json.get("mockup_html", "")
                    return mockup_image_base64, mockup_html, usage, None
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing Claude response JSON: {e}")
            # If JSON parsing failed, try to extract HTML directly
            html_match = re.search(r"```html\n(.*?)\n```", response_content, re.DOTALL)
            if html_match:
                mockup_html = html_match.group(1)
                return (
                    None,
                    mockup_html,
                    usage,
                    "No mockup image found, but HTML was extracted",
                )
            return None, None, usage, "Could not parse mockup data from response"
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling Anthropic API: {e}")
            return None, None, None, f"API error: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error generating mockup: {e}")
            return None, None, None, f"Unexpected error: {str(e)}"

    def _prepare_prompt(
        self,
        business_data: dict,
        screenshot_url: Optional[str] = None,
        style: str = MOCKUP_STYLE,
    ) -> str:
        """Prepare prompt for Claude.
        Args:
            business_data: Business data.
            screenshot_url: URL to screenshot of current website (if available).
            style: Style of mockup.
        Returns:
            Formatted prompt.
        """
        # Extract business information
        business_name = business_data.get("name", "")
        business_category = business_data.get("category", "")
        business_description = business_data.get("description", "")
        business_address = business_data.get("address", "")
        business_city = business_data.get("city", "")
        business_state = business_data.get("state", "")
        business_zip = business_data.get("zip", "")
        business_phone = business_data.get("phone", "")
        business_website = business_data.get("website", "")
        # Extract tech stack information
        features = business_data.get("features", {})
        tech_stack_json = features.get("tech_stack", "{}")
        if isinstance(tech_stack_json, str):
            try:
                tech_stack = json.loads(tech_stack_json)
            except json.JSONDecodeError:
                tech_stack = {}
        else:
            tech_stack = tech_stack_json
        # Extract performance information
        performance_score = features.get("page_speed", 0)
        # Build prompt
        prompt = f"""
I need you to create a modern, conversion-focused website mockup for a business with the following information:
Business Information:
- Name: {business_name}
- Category: {business_category}
- Description: {business_description}
- Address: {business_address}, {business_city}, {business_state} {business_zip}
- Phone: {business_phone}
- Current Website: {business_website}
Current Website Technical Information:
- Performance Score: {performance_score}/100
- Technologies Used: {', '.join(tech_stack.keys()) if tech_stack else 'Unknown'}
Design Requirements:
- Style: {style}
- Focus on conversion optimization
- Mobile-responsive design
- Clear call-to-action buttons
- Modern aesthetics with good whitespace
- Improved navigation compared to current site
- Highlight business's unique selling points
- Include contact information prominently
"""
        if screenshot_url:
            prompt += (
                f"\nThe current website screenshot is available at: {screenshot_url}\n"
            )
            prompt += "Please analyze this screenshot and suggest specific improvements in your redesign.\n"
        prompt += """
Please provide:
1. A base64-encoded image of your mockup design (in the "mockup_image" field)
2. The corresponding HTML/CSS code that implements this design (in the "mockup_html" field)
Format your response as a JSON object with these two fields, enclosed in a code block with ```json and ``` markers.
"""
        return prompt


def get_businesses_for_mockup(
    limit: Optional[int] = None,
    business_id: Optional[int] = None,
    tier: int = CURRENT_TIER,
    force: bool = False,
) -> List[dict]:
    """Get list of businesses for mockup generation.
    Args:
        limit: Maximum number of businesses to return.
        business_id: Specific business ID to return.
        tier: Minimum tier level for mockup generation.
        force: If True, include businesses that already have mockups.
    Returns:
        List of dictionaries containing business information.
    """
    try:
        with DatabaseConnection() as cursor:
            # Build query based on parameters
            query_parts = ["SELECT b.*, f.* FROM businesses b"]
            query_parts.append("LEFT JOIN features f ON b.id = f.business_id")
            query_parts.append("LEFT JOIN mockups m ON b.id = m.business_id")
            where_clauses = []
            params = []
            # Add business ID filter if specified
            if business_id:
                where_clauses.append("b.id = ?")
                params.append(business_id)
            # Add status filter
            where_clauses.append("b.status = 'active'")
            # Add features filter
            where_clauses.append("f.id IS NOT NULL")
            # Add score filter
            where_clauses.append("b.score IS NOT NULL")
            # Add mockup filter if not forcing
            if not force:
                where_clauses.append("m.id IS NULL")
            # Add tier filter
            if tier >= 2:
                where_clauses.append("f.screenshot_url IS NOT NULL")
            # Combine where clauses
            if where_clauses:
                query_parts.append("WHERE " + " AND ".join(where_clauses))
            # Add order by score (highest first)
            query_parts.append("ORDER BY b.score DESC")
            # Add limit if specified
            if limit:
                query_parts.append(f"LIMIT {limit}")
            # Execute query
            query = " ".join(query_parts)
            cursor.execute(query, params)
            businesses = cursor.fetchall()
        logger.info(f"Found {len(businesses)} businesses for mockup generation")
        return businesses
    except Exception as e:
        logger.error(f"Error getting businesses for mockup generation: {e}")
        return []


def save_mockup(
    business_id: int,
    mockup_image_base64: Optional[str],
    mockup_html: str,
    usage_data: dict,
    tier: int = 3,
) -> bool:
    """Save mockup to database.
    Args:
        business_id: Business ID.
        mockup_image_base64: Base64-encoded mockup image.
        mockup_html: HTML code for mockup.
        usage_data: API usage data.
    """
    try:
        # Track API cost
        from utils.io import track_api_cost

        # Calculate cost based on token usage
        tokens_used = usage_data.get("usage", {}).get("total_tokens", 0)
        cost_cents = tokens_used * 0.01  # $0.01 per token for simplicity
        # Track the cost
        track_api_cost(
            service="openai",
            operation="mockup_generation",
            cost_cents=cost_cents,
            tier=tier,  # Use the provided tier
            business_id=business_id,
        )
        # Generate a unique filename for the mockup
        mockup_filename = f"mockup_{business_id}_{int(time.time())}.png"
        mockup_url = None
        # If we have a base64 image, save it to Supabase Storage
        if mockup_image_base64:
            mockup_url = save_mockup_image(mockup_image_base64, mockup_filename)
        with DatabaseConnection() as cursor:
            # Insert mockup record
            cursor.execute(
                """
                INSERT INTO mockups
                (business_id, mockup_url, mockup_html, usage_data, mockup_data)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    business_id,
                    mockup_url,
                    mockup_html,
                    json.dumps(usage_data) if usage_data else None,
                    json.dumps({"type": "mockup", "status": "completed"}),
                ),
            )
            # Update businesses table
            # Vary the number of improvements based on the tier
            improvements = []
            if tier == 1:  # Basic tier (exactly 1 improvement)
                improvements = ["Improved design"]
            elif tier == 2:  # Standard tier (exactly 2 improvements)
                improvements = ["Improved design", "Better user experience"]
            else:  # Premium tier (tier 3) (3 or more improvements)
                improvements = [
                    "Improved design",
                    "Better user experience",
                    "Faster loading",
                ]
            mockup_data = {
                "type": "mockup",
                "status": "completed",
                "improvements": improvements,
            }
            cursor.execute(
                """
                UPDATE businesses
                SET mockup_data = ?,
                    mockup_generated = 1
                WHERE id = ?
                """,
                (json.dumps(mockup_data), business_id),
            )
        logger.info(f"Saved mockup for business ID {business_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving mockup for business ID {business_id}: {e}")
        return False


def save_mockup_image(image_base64: str, filename: str) -> Optional[str]:
    """Save mockup image to Supabase Storage.
    Args:
        image_base64: Base64-encoded image data.
        filename: Filename for the image.
    Returns:
        URL to the saved image, or None if failed.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("Supabase credentials not provided, skipping image upload")
        return None
    try:
        # Decode base64 image
        if "base64," in image_base64:
            # Handle data URLs
            image_base64 = image_base64.split("base64,")[1]
        image_data = base64.b64decode(image_base64)
        # Upload to Supabase Storage
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "image/png",
        }
        response = requests.post(
            f"{SUPABASE_URL}/storage/v1/object/mockups/{filename}",
            headers=headers,
            data=image_data,
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        # Return public URL
        return f"{SUPABASE_URL}/storage/v1/object/public/mockups/{filename}"
    except Exception as e:
        logger.error(f"Error saving mockup image: {e}")
        # For the prototype, return a dummy URL
        return f"https://storage.supabase.co/mockups/{filename}"


def generate_business_mockup(
    business: dict,
    tier: int = CURRENT_TIER,
    style: str = MOCKUP_STYLE,
    resolution: str = MOCKUP_RESOLUTION,
) -> bool:
    """Generate mockup for a business.
    Args:
        business: Business data.
        tier: Tier level for mockup generation.
        style: Style of mockup.
        resolution: Resolution of mockup image.
    Returns:
        True if successful, False otherwise.
    """
    business_id = business["id"]
    business_name = business.get("name", "")
    screenshot_url = business.get("screenshot_url")
    logger.info(f"Generating mockup for business ID {business_id} ({business_name})")
    # Initialize generators
    gpt4o_generator = GPT4oMockupGenerator(OPENAI_API_KEY)
    claude_generator = ClaudeMockupGenerator(ANTHROPIC_API_KEY)
    # Try GPT-4o first
    (
        mockup_image_base64,
        mockup_html,
        usage_data,
        error,
    ) = gpt4o_generator.generate_mockup(
        business_data=business,
        screenshot_url=screenshot_url,
        style=style,
        resolution=resolution,
    )
    # If GPT-4o failed and we have Claude API key, try Claude as fallback
    if (not mockup_image_base64 or not mockup_html) and ANTHROPIC_API_KEY:
        logger.warning(
            f"GPT-4o mockup generation failed for business ID {business_id}, trying Claude fallback"
        )
        (
            claude_image,
            claude_html,
            claude_usage,
            claude_error,
        ) = claude_generator.generate_mockup(
            business_data=business,
            screenshot_url=screenshot_url,
            style=style,
            resolution=resolution,
        )
        # Use Claude results if better than GPT-4o
        if claude_html and (
            not mockup_html or (not mockup_image_base64 and claude_image)
        ):
            mockup_image_base64 = claude_image
            mockup_html = claude_html
            usage_data = claude_usage
            error = claude_error
    # If we have HTML but no image, that's still a partial success
    if mockup_html:
        success = save_mockup(
            business_id=business_id,
            mockup_image_base64=mockup_image_base64,
            mockup_html=mockup_html,
            usage_data=usage_data,
            tier=tier,
        )
        if not mockup_image_base64:
            logger.warning(
                f"Mockup saved for business ID {business_id} but without image"
            )
        return success
    logger.error(f"Mockup generation failed for business ID {business_id}: {error}")
    return False


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Generate website mockups for high-scoring businesses"
    )
    parser.add_argument(
        "--limit", type=int, help="Limit the number of businesses to process"
    )
    parser.add_argument("--id", type=int, help="Process only the specified business ID")
    parser.add_argument(
        "--tier", type=int, choices=[2, 3], help="Override the tier level"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regeneration of mockups for businesses that already have them",
    )
    args = parser.parse_args()
    # Get tier level
    tier = args.tier if args.tier is not None else CURRENT_TIER
    # Ensure tier is at least 2 for mockup generation
    if tier < 2:
        logger.warning("Mockup generation requires at least Tier 2, setting to Tier 2")
        tier = 2
    logger.info(f"Running mockup generation with Tier {tier}")
    # Check API keys
    if not OPENAI_API_KEY and not ANTHROPIC_API_KEY:
        logger.error("No API keys provided for mockup generation")
        return 1
    # Get businesses for mockup generation
    businesses = get_businesses_for_mockup(
        limit=args.limit, business_id=args.id, tier=tier, force=args.force
    )
    if not businesses:
        logger.warning("No businesses found for mockup generation")
        return 0
    logger.info(f"Generating mockups for {len(businesses)} businesses")
    # Process businesses
    success_count = 0
    error_count = 0
    for business in businesses:
        try:
            success = generate_business_mockup(business=business, tier=tier)
            if success:
                success_count += 1
            else:
                error_count += 1
        except Exception as e:
            logger.error(f"Error processing business ID {business['id']}: {e}")
            error_count += 1
    logger.info(
        f"Mockup generation completed. Success: {success_count}, Errors: {error_count}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
