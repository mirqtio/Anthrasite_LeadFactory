#!/usr/bin/env python3
"""
Anthrasite Lead-Factory: Deduplication Logic (03_dedupe.py)
Identifies and merges duplicate business records using Levenshtein distance
pre-filtering and Llama-3 8B for final verification.
Usage:
    python bin/03_dedupe.py [--limit N] [--threshold T] [--dry-run]
Options:
    --limit N        Limit the number of potential duplicates to process (default: all)
    --threshold T    Levenshtein distance threshold (default: 0.85)
    --dry-run        Run without making changes to the database
"""
import argparse
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

import Levenshtein
import requests
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Import utility functions
from utils.io import DatabaseConnection, track_api_cost
# Import logging configuration first
from utils.logging_config import get_logger

# Load environment variables
load_dotenv()
# Set up logger
logger = get_logger(__name__)
# Constants
DEFAULT_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "5"))
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3:8b")
LEVENSHTEIN_THRESHOLD = float(os.getenv("LEVENSHTEIN_THRESHOLD", "0.85"))
OLLAMA_COST_PER_1K_TOKENS = float(os.getenv("OLLAMA_COST_PER_1K_TOKENS", "0.01"))  # $0.01 per 1K tokens


class LevenshteinMatcher:
    """Identifies potential duplicate businesses using Levenshtein distance."""

    def __init__(self, threshold: float = LEVENSHTEIN_THRESHOLD):
        """Initialize the Levenshtein matcher.
        Args:
            threshold: Similarity threshold (0.0 to 1.0) for considering records as potential duplicates.
        """
        self.threshold = threshold

    @staticmethod
    def normalize_string(text: str) -> str:
        """Normalize a string for comparison.
        Args:
            text: Input string.
        Returns:
            Normalized string.
        """
        if not text:
            return ""
        # Convert to lowercase
        text = text.lower()
        # Remove special characters and extra whitespace
        text = re.sub(r"[^\w\s]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def normalize_phone(phone: str) -> str:
        """Normalize a phone number for comparison.
        Args:
            phone: Phone number string.
        Returns:
            Normalized phone number (digits only).
        """
        if not phone:
            return ""
        # Keep only digits
        return re.sub(r"\D", "", phone)

    def calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate the similarity between two strings using Levenshtein distance.
        Args:
            str1: First string.
            str2: Second string.
        Returns:
            Similarity score (0.0 to 1.0).
        """
        if not str1 and not str2:
            return 1.0
        if not str1 or not str2:
            return 0.0
        # Normalize strings
        str1_norm = self.normalize_string(str1)
        str2_norm = self.normalize_string(str2)
        if not str1_norm and not str2_norm:
            return 1.0
        if not str1_norm or not str2_norm:
            return 0.0
        # Calculate Levenshtein distance
        distance = Levenshtein.distance(str1_norm, str2_norm)
        max_len = max(len(str1_norm), len(str2_norm))
        # Convert to similarity score (0.0 to 1.0)
        return 1.0 - (distance / max_len)

    def are_potential_duplicates(self, business1: Dict, business2: Dict) -> bool:
        """Check if two businesses are potential duplicates.
        Args:
            business1: First business record.
            business2: Second business record.
        Returns:
            True if businesses are potential duplicates, False otherwise.
        """
        # Skip if same business
        if business1["id"] == business2["id"]:
            return False
        # Compare business names
        name_similarity = self.calculate_similarity(business1["name"], business2["name"])
        # Compare phone numbers (if available)
        phone_similarity = 0.0
        if business1.get("phone") and business2.get("phone"):
            phone1 = self.normalize_phone(business1["phone"])
            phone2 = self.normalize_phone(business2["phone"])
            if phone1 and phone2:
                # Exact match for phone numbers
                phone_similarity = 1.0 if phone1 == phone2 else 0.0
        # Compare addresses (if available)
        address_similarity = 0.0
        if business1.get("address") and business2.get("address"):
            address_similarity = self.calculate_similarity(business1["address"], business2["address"])
        # Calculate combined similarity score
        # Weight: 50% name, 30% phone, 20% address
        combined_similarity = 0.5 * name_similarity + 0.3 * phone_similarity + 0.2 * address_similarity
        # Consider as potential duplicates if combined similarity exceeds threshold
        return combined_similarity >= self.threshold


class OllamaVerifier:
    """Verifies duplicate businesses using Ollama LLM."""

    def __init__(self, model: str = OLLAMA_MODEL, api_url: str = OLLAMA_URL):
        """Initialize the Ollama verifier.
        Args:
            model: Ollama model name.
            api_url: Ollama API URL.
        """
        self.model = model
        self.api_url = api_url

    def verify_duplicates(self, business1: Dict, business2: Dict) -> Tuple[bool, float, str]:
        """Verify if two businesses are duplicates using Ollama LLM.
        Args:
            business1: First business record.
            business2: Second business record.
        Returns:
            Tuple of (is_duplicate, confidence, reasoning).
        """
        # Prepare prompt
        prompt = self._prepare_prompt(business1, business2)
        try:
            # Call Ollama API
            response = requests.post(
                f"{self.api_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 512},
                },
                timeout=DEFAULT_TIMEOUT,
            )
            response.raise_for_status()
            # Parse response
            result = response.json()
            response_text = result.get("response", "")
            # Track token usage
            prompt_tokens = result.get("prompt_eval_count", 0)
            completion_tokens = result.get("eval_count", 0)
            total_tokens = prompt_tokens + completion_tokens
            # Track cost
            cost_dollars = (total_tokens / 1000) * OLLAMA_COST_PER_1K_TOKENS
            cost_cents = cost_dollars * 100
            track_api_cost(
                service="ollama",
                operation="dedupe_verification",
                cost_cents=cost_cents,
                tier=1,  # Always use tier 1 for deduplication
            )
            # Parse the response to extract decision
            is_duplicate, confidence, reasoning = self._parse_response(response_text)
            logger.info(f"Ollama verification result: is_duplicate={is_duplicate}, confidence={confidence:.2f}")
            return is_duplicate, confidence, reasoning
        except Exception as e:
            logger.error(f"Error calling Ollama API: {e}")
            return False, 0.0, f"Error: {str(e)}"

    def _prepare_prompt(self, business1: Dict, business2: Dict) -> str:
        """Prepare prompt for Ollama LLM.
        Args:
            business1: First business record.
            business2: Second business record.
        Returns:
            Formatted prompt.
        """
        return f"""You are a business data analyst tasked with identifying duplicate business records.
Given the following two business records, determine if they represent the same business.
Business 1:
- Name: {business1.get('name', 'N/A')}
- Address: {business1.get('address', 'N/A')}
- City: {business1.get('city', 'N/A')}
- State: {business1.get('state', 'N/A')}
- ZIP: {business1.get('zip', 'N/A')}
- Phone: {business1.get('phone', 'N/A')}
- Website: {business1.get('website', 'N/A')}
- Category: {business1.get('category', 'N/A')}
Business 2:
- Name: {business2.get('name', 'N/A')}
- Address: {business2.get('address', 'N/A')}
- City: {business2.get('city', 'N/A')}
- State: {business2.get('state', 'N/A')}
- ZIP: {business2.get('zip', 'N/A')}
- Phone: {business2.get('phone', 'N/A')}
- Website: {business2.get('website', 'N/A')}
- Category: {business2.get('category', 'N/A')}
Analyze the records and respond in the following format:
DUPLICATE: [YES/NO]
CONFIDENCE: [0-100]
REASONING: [Your detailed reasoning]
Consider the following:
1. Business names might have slight variations but still be the same business
2. Phone numbers and websites are strong indicators if they match
3. Addresses might have formatting differences but still be the same location
4. Businesses might have multiple locations with the same name
5. Different categories might indicate different businesses, but some businesses span multiple categories
Provide your analysis:
"""

    def _parse_response(self, response_text: str) -> Tuple[bool, float, str]:
        """Parse Ollama response to extract decision.
        Args:
            response_text: Response text from Ollama.
        Returns:
            Tuple of (is_duplicate, confidence, reasoning).
        """
        # Extract decision
        duplicate_match = re.search(r"DUPLICATE:\s*(YES|NO)", response_text, re.IGNORECASE)
        is_duplicate = duplicate_match and duplicate_match.group(1).upper() == "YES"
        # Extract confidence
        confidence_match = re.search(r"CONFIDENCE:\s*(\d+)", response_text)
        confidence = float(confidence_match.group(1)) / 100 if confidence_match else 0.5
        # Extract reasoning
        reasoning_match = re.search(r"REASONING:\s*(.*?)(?=$|\n\n)", response_text, re.DOTALL)
        reasoning = reasoning_match.group(1).strip() if reasoning_match else ""
        return is_duplicate, confidence, reasoning


def get_potential_duplicates(limit: Optional[int] = None) -> List[Dict]:
    """Get list of potential duplicate pairs from the database.
    Args:
        limit: Maximum number of potential duplicate pairs to return.
    Returns:
        List of dictionaries containing potential duplicate pairs.
    """
    try:
        with DatabaseConnection() as cursor:
            query = """
                SELECT * FROM candidate_duplicate_pairs
            """
            if limit:
                query += f" LIMIT {limit}"
            cursor.execute(query)
            duplicate_pairs = cursor.fetchall()
        logger.info(f"Found {len(duplicate_pairs)} potential duplicate pairs")
        return duplicate_pairs
    except Exception as e:
        logger.error(f"Error getting potential duplicate pairs: {e}")
        return []


def get_business_by_id(business_id: int) -> Optional[Dict]:
    """Get business record by ID.
    Args:
        business_id: Business ID.
    Returns:
        Business record as dictionary, or None if not found.
    """
    try:
        with DatabaseConnection() as cursor:
            cursor.execute(
                """
                SELECT * FROM businesses WHERE id = ?
                """,
                (business_id,),
            )
            business = cursor.fetchone()
        return business
    except Exception as e:
        logger.error(f"Error getting business by ID {business_id}: {e}")
        return None


def merge_businesses(business1: Dict, business2: Dict, is_dry_run: bool = False) -> Optional[int]:
    """Merge two business records.
    Args:
        business1: First business record.
        business2: Second business record.
        is_dry_run: If True, don't actually merge the records.
    Returns:
        ID of the merged business record, or None if merge failed.
    """
    # Determine which business to keep (primary) and which to merge (secondary)
    # Prefer the business with more complete information
    primary_id, secondary_id = select_primary_business(business1, business2)
    if is_dry_run:
        logger.info(f"[DRY RUN] Would merge business ID {secondary_id} into {primary_id}")
        return primary_id
    try:
        with DatabaseConnection() as cursor:
            # Start transaction
            cursor.execute("BEGIN TRANSACTION")
            # Update references in features table
            cursor.execute(
                """
                UPDATE features SET business_id = ?
                WHERE business_id = ? AND business_id != ?
                """,
                (primary_id, secondary_id, primary_id),
            )
            # Update references in mockups table
            cursor.execute(
                """
                UPDATE mockups SET business_id = ?
                WHERE business_id = ? AND business_id != ?
                """,
                (primary_id, secondary_id, primary_id),
            )
            # Update references in emails table
            cursor.execute(
                """
                UPDATE emails SET business_id = ?
                WHERE business_id = ? AND business_id != ?
                """,
                (primary_id, secondary_id, primary_id),
            )
            # Mark secondary business as merged
            cursor.execute(
                """
                UPDATE businesses SET
                    status = 'merged',
                    merged_into = ?
                WHERE id = ?
                """,
                (primary_id, secondary_id),
            )
            # Commit transaction
            cursor.execute("COMMIT")
        logger.info(f"Successfully merged business ID {secondary_id} into {primary_id}")
        return primary_id
    except Exception as e:
        logger.error(f"Error merging businesses {primary_id} and {secondary_id}: {e}")
        return None


def select_primary_business(business1: Dict, business2: Dict) -> Tuple[int, int]:
    """Select which business should be the primary (kept) and which should be secondary (merged).
    Args:
        business1: First business record.
        business2: Second business record.
    Returns:
        Tuple of (primary_id, secondary_id).
    """
    # Calculate completeness score for each business
    score1 = calculate_completeness_score(business1)
    score2 = calculate_completeness_score(business2)
    # Select business with higher completeness score as primary
    if score1 >= score2:
        return business1["id"], business2["id"]
    else:
        return business2["id"], business1["id"]


def calculate_completeness_score(business: Dict) -> float:
    """Calculate completeness score for a business record.
    Args:
        business: Business record.
    Returns:
        Completeness score (0.0 to 1.0).
    """
    # Fields to check for completeness
    fields = [
        "name",
        "address",
        "city",
        "state",
        "zip",
        "phone",
        "website",
        "category",
        "description",
        "email",
    ]
    # Calculate score based on field presence and non-emptiness
    score = 0.0
    for field in fields:
        if field in business and business[field]:
            score += 1.0
    # Normalize score
    return score / len(fields)


def flag_for_review(business1_id: int, business2_id: int, reason: str, similarity_score: float = None) -> None:
    """Flag a pair of businesses for manual review.
    Args:
        business1_id: ID of the first business.
        business2_id: ID of the second business.
        reason: Reason for flagging for review.
        similarity_score: Optional similarity score between the businesses.
    """
    try:
        with DatabaseConnection() as cursor:
            # Ensure business1_id is always the smaller ID for consistency
            if business1_id > business2_id:
                business1_id, business2_id = business2_id, business1_id
            cursor.execute(
                """
                INSERT OR REPLACE INTO candidate_duplicate_pairs
                (business1_id, business2_id, status, llm_reasoning, similarity_score, verified_by_llm)
                VALUES (?, ?, 'review', ?, ?, 1)
            """,
                (business1_id, business2_id, reason, similarity_score),
            )
            logger.info(f"Flagged businesses {business1_id} and {business2_id} " f"for manual review: {reason}")
    except Exception as e:
        logger.error(f"Error flagging businesses {business1_id} and {business2_id} " f"for review: {e}")


def process_duplicate_pair(
    duplicate_pair: Dict,
    matcher: LevenshteinMatcher,
    verifier: OllamaVerifier,
    is_dry_run: bool = False,
) -> Tuple[bool, Optional[int]]:
    """Process a potential duplicate pair.
    Args:
        duplicate_pair: Potential duplicate pair record.
        matcher: LevenshteinMatcher instance.
        verifier: OllamaVerifier instance.
        is_dry_run: If True, don't actually merge the records.
    Returns:
        Tuple of (success, merged_business_id).
    """
    business1_id = duplicate_pair["business1_id"]
    business2_id = duplicate_pair["business2_id"]
    # Get business records
    business1 = get_business_by_id(business1_id)
    business2 = get_business_by_id(business2_id)
    if not business1 or not business2:
        logger.warning(f"Could not retrieve businesses {business1_id} and/or {business2_id}")
        return False, None
    # Check if businesses are potential duplicates using Levenshtein distance
    if not matcher.are_potential_duplicates(business1, business2):
        logger.info(
            f"Businesses {business1_id} and {business2_id} are not potential duplicates based on Levenshtein distance"
        )
        return False, None
    # Verify duplicates using Ollama LLM
    is_duplicate, confidence, reasoning = verifier.verify_duplicates(business1, business2)
    logger.info(
        f"Duplicate verification for businesses {business1_id} and {business2_id}: "
        f"is_duplicate={is_duplicate}, confidence={confidence:.2f}, reasoning='{reasoning[:100]}...'"
    )
    # If verified as duplicates with sufficient confidence, merge them
    if is_duplicate and confidence >= 0.7:  # Require high confidence for merging
        merged_id = merge_businesses(business1, business2, is_dry_run)
        return merged_id is not None, merged_id
    else:
        # If not duplicates but same name with different addresses, flag for review
        if business1["name"] == business2["name"] and business1["address"] != business2["address"]:
            if not is_dry_run:
                flag_for_review(
                    business1_id,
                    business2_id,
                    f"Same name but different addresses: '{reasoning}'",
                    duplicate_pair.get("similarity_score", 0.0),
                )
            logger.info(
                f"Flagged businesses {business1_id} and {business2_id} for review: "
                f"Same name but different addresses"
            )
            return True, None
    return False, None


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Identify and merge duplicate business records")
    parser.add_argument("--limit", type=int, help="Limit the number of potential duplicates to process")
    parser.add_argument(
        "--threshold",
        type=float,
        default=LEVENSHTEIN_THRESHOLD,
        help="Levenshtein distance threshold",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without making changes to the database",
    )
    args = parser.parse_args()
    # Initialize matchers and verifiers
    matcher = LevenshteinMatcher(threshold=args.threshold)
    verifier = OllamaVerifier()
    # Get potential duplicate pairs
    duplicate_pairs = get_potential_duplicates(limit=args.limit)
    if not duplicate_pairs:
        logger.warning("No potential duplicate pairs found")
        return 0
    logger.info(f"Processing {len(duplicate_pairs)} potential duplicate pairs")
    # Process duplicate pairs
    success_count = 0
    error_count = 0
    skipped_count = 0
    for duplicate_pair in duplicate_pairs:
        # Skip already processed pairs
        if duplicate_pair["status"] != "pending":
            logger.info(
                f"Skipping already processed pair {duplicate_pair['id']} with status '{duplicate_pair['status']}'"
            )
            skipped_count += 1
            continue
        try:
            success, merged_id = process_duplicate_pair(
                duplicate_pair=duplicate_pair,
                matcher=matcher,
                verifier=verifier,
                is_dry_run=args.dry_run,
            )
            if success:
                success_count += 1
            else:
                error_count += 1
        except Exception as e:
            logger.error(f"Error processing duplicate pair {duplicate_pair['id']}: {e}")
            error_count += 1
    logger.info(f"Deduplication completed. Success: {success_count}, Errors: {error_count}, Skipped: {skipped_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
