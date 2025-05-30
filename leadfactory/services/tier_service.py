"""
Tier-based service layer for conditional API calls.

This module provides the core logic that determines which API endpoints
to call based on the user's tier level, implementing graceful degradation
for lower tiers and enhanced capabilities for higher tiers.
"""

import os
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from leadfactory.config.tier_config import (
    TIER_CONFIG,
    TierLevel,
    get_tier_config,
    is_api_enabled_for_tier,
    is_feature_enabled_for_tier,
)
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class APICallResult:
    """Result of an API call with tier-aware metadata."""

    def __init__(
        self,
        success: bool,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        tier_limited: bool = False,
        api_name: Optional[str] = None,
    ):
        self.success = success
        self.data = data or {}
        self.error = error
        self.tier_limited = tier_limited
        self.api_name = api_name


class TierService:
    """Service layer for tier-based API call management."""

    def __init__(self, tier: int = 1):
        """
        Initialize the tier service.

        Args:
            tier: The current tier level (1, 2, or 3)
        """
        self.tier = tier
        self.tier_level = TierLevel(tier)
        self.config = get_tier_config(self.tier_level)
        logger.info(f"TierService initialized for tier {tier}")

    def can_call_api(self, api_name: str) -> bool:
        """
        Check if an API can be called based on the current tier.

        Args:
            api_name: Name of the API to check

        Returns:
            True if the API is enabled for the current tier
        """
        return is_api_enabled_for_tier(api_name, self.tier_level)

    def can_use_feature(self, feature_name: str, stage: str) -> bool:
        """
        Check if a feature can be used based on the current tier.

        Args:
            feature_name: Name of the feature to check
            stage: Stage name ('enrich' or 'mockup')

        Returns:
            True if the feature is enabled for the current tier
        """
        return is_feature_enabled_for_tier(feature_name, stage, self.tier_level)

    def get_enabled_apis(self) -> List[str]:
        """
        Get list of APIs enabled for the current tier.

        Returns:
            List of enabled API names
        """
        return self.config.enabled_apis

    def get_enabled_features(self, stage: str) -> List[str]:
        """
        Get list of features enabled for the current tier and stage.

        Args:
            stage: Stage name ('enrich' or 'mockup')

        Returns:
            List of enabled feature names
        """
        if stage == "enrich":
            return self.config.enrichment_features
        elif stage == "mockup":
            return self.config.mockup_features
        else:
            logger.warning(f"Unknown stage: {stage}")
            return []

    def call_api_conditionally(
        self, api_name: str, api_function, *args, **kwargs
    ) -> APICallResult:
        """
        Call an API function conditionally based on tier permissions.

        Args:
            api_name: Name of the API being called
            api_function: The API function to call
            *args: Arguments to pass to the API function
            **kwargs: Keyword arguments to pass to the API function

        Returns:
            APICallResult with success status and data/error information
        """
        if not self.can_call_api(api_name):
            logger.info(
                f"API {api_name} not available for tier {self.tier}",
                extra={"tier": self.tier, "api": api_name, "reason": "tier_limited"},
            )
            return APICallResult(
                success=False,
                error=f"API {api_name} not available for tier {self.tier}",
                tier_limited=True,
                api_name=api_name,
            )

        try:
            logger.info(
                f"Calling API {api_name} for tier {self.tier}",
                extra={"tier": self.tier, "api": api_name},
            )

            # Call the API function
            result = api_function(*args, **kwargs)

            # Handle different return formats
            if isinstance(result, tuple):
                # Assume (data, error) format
                data, error = result
                if error:
                    logger.warning(
                        f"API {api_name} returned error: {error}",
                        extra={"tier": self.tier, "api": api_name, "error": error},
                    )
                    return APICallResult(success=False, error=error, api_name=api_name)
                else:
                    logger.info(
                        f"API {api_name} call successful",
                        extra={"tier": self.tier, "api": api_name},
                    )
                    return APICallResult(success=True, data=data, api_name=api_name)
            else:
                # Assume direct data return
                logger.info(
                    f"API {api_name} call successful",
                    extra={"tier": self.tier, "api": api_name},
                )
                return APICallResult(success=True, data=result, api_name=api_name)

        except Exception as e:
            logger.error(
                f"Error calling API {api_name}: {str(e)}",
                extra={
                    "tier": self.tier,
                    "api": api_name,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )
            return APICallResult(
                success=False, error=f"API call failed: {str(e)}", api_name=api_name
            )

    def execute_feature_conditionally(
        self, feature_name: str, stage: str, feature_function, *args, **kwargs
    ) -> APICallResult:
        """
        Execute a feature function conditionally based on tier permissions.

        Args:
            feature_name: Name of the feature being executed
            stage: Stage name ('enrich' or 'mockup')
            feature_function: The feature function to execute
            *args: Arguments to pass to the feature function
            **kwargs: Keyword arguments to pass to the feature function

        Returns:
            APICallResult with success status and data/error information
        """
        if not self.can_use_feature(feature_name, stage):
            logger.info(
                f"Feature {feature_name} not available for tier {self.tier} in stage {stage}",
                extra={
                    "tier": self.tier,
                    "feature": feature_name,
                    "stage": stage,
                    "reason": "tier_limited",
                },
            )
            return APICallResult(
                success=False,
                error=f"Feature {feature_name} not available for tier {self.tier}",
                tier_limited=True,
                api_name=feature_name,
            )

        try:
            logger.info(
                f"Executing feature {feature_name} for tier {self.tier} in stage {stage}",
                extra={"tier": self.tier, "feature": feature_name, "stage": stage},
            )

            result = feature_function(*args, **kwargs)

            logger.info(
                f"Feature {feature_name} execution successful",
                extra={"tier": self.tier, "feature": feature_name, "stage": stage},
            )
            return APICallResult(success=True, data=result, api_name=feature_name)

        except Exception as e:
            logger.error(
                f"Error executing feature {feature_name}: {str(e)}",
                extra={
                    "tier": self.tier,
                    "feature": feature_name,
                    "stage": stage,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )
            return APICallResult(
                success=False,
                error=f"Feature execution failed: {str(e)}",
                api_name=feature_name,
            )

    def get_tier_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current tier configuration.

        Returns:
            Dictionary containing tier information and capabilities
        """
        return {
            "tier": self.tier,
            "tier_level": self.tier_level.name,
            "enabled_apis": self.get_enabled_apis(),
            "enrichment_features": self.get_enabled_features("enrich"),
            "mockup_features": self.get_enabled_features("mockup"),
            "cost_threshold": self.config.cost_threshold_cents,
        }


def get_tier_service(tier: Optional[int] = None) -> TierService:
    """
    Factory function to get a TierService instance.

    Args:
        tier: Optional tier level. If not provided, uses environment variable.

    Returns:
        TierService instance
    """
    if tier is None:
        tier = int(os.getenv("TIER", "1"))

    return TierService(tier)
