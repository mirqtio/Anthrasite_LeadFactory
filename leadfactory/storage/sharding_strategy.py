"""
Database sharding strategy for LeadFactory.

Implements geographic and source-based sharding for high-volume lead processing.
"""

import hashlib
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ShardingStrategy(Enum):
    """Available sharding strategies."""

    GEOGRAPHIC = "geographic"
    SOURCE_BASED = "source_based"
    HASH_BASED = "hash_based"
    HYBRID = "hybrid"


@dataclass
class ShardConfig:
    """Configuration for a database shard."""

    shard_id: str
    host: str
    port: int
    database: str
    username: str
    password: str
    max_connections: int = 20
    read_replicas: list[dict[str, Any]] = None

    def __post_init__(self):
        if self.read_replicas is None:
            self.read_replicas = []


@dataclass
class ShardingConfig:
    """Overall sharding configuration."""

    strategy: ShardingStrategy
    shards: list[ShardConfig]
    default_shard: str
    replication_factor: int = 2

    def get_shard(self, shard_id: str) -> Optional[ShardConfig]:
        """Get shard configuration by ID."""
        for shard in self.shards:
            if shard.shard_id == shard_id:
                return shard
        return None


class ShardRouter:
    """Routes database operations to appropriate shards."""

    def __init__(self, config: ShardingConfig):
        self.config = config
        self.strategy = config.strategy

        # Build shard lookup maps
        self._geographic_map = self._build_geographic_map()
        self._source_map = self._build_source_map()

        logger.info(
            f"Initialized shard router with {len(config.shards)} shards using {config.strategy.value} strategy"
        )

    def get_shard_for_business(self, business_data: dict[str, Any]) -> str:
        """Determine which shard should store a business record."""
        if self.strategy == ShardingStrategy.GEOGRAPHIC:
            return self._get_geographic_shard(business_data)
        elif self.strategy == ShardingStrategy.SOURCE_BASED:
            return self._get_source_based_shard(business_data)
        elif self.strategy == ShardingStrategy.HASH_BASED:
            return self._get_hash_based_shard(business_data)
        elif self.strategy == ShardingStrategy.HYBRID:
            return self._get_hybrid_shard(business_data)
        else:
            return self.config.default_shard

    def get_shards_for_query(self, query_params: dict[str, Any]) -> list[str]:
        """Determine which shards need to be queried for a given query."""
        if self.strategy == ShardingStrategy.GEOGRAPHIC:
            return self._get_geographic_shards_for_query(query_params)
        elif self.strategy == ShardingStrategy.SOURCE_BASED:
            return self._get_source_shards_for_query(query_params)
        elif self.strategy == ShardingStrategy.HASH_BASED:
            # Hash-based queries typically need to hit all shards
            return [shard.shard_id for shard in self.config.shards]
        elif self.strategy == ShardingStrategy.HYBRID:
            return self._get_hybrid_shards_for_query(query_params)
        else:
            return [self.config.default_shard]

    def get_read_shard(
        self, shard_id: str, prefer_replica: bool = True
    ) -> tuple[str, int, str]:
        """Get read endpoint for a shard (replica if available and preferred)."""
        shard = self.config.get_shard(shard_id)
        if not shard:
            raise ValueError(f"Shard {shard_id} not found")

        # Use read replica if available and preferred
        if prefer_replica and shard.read_replicas:
            replica = shard.read_replicas[0]  # Simple round-robin can be added
            return replica["host"], replica["port"], replica["database"]

        # Fall back to primary
        return shard.host, shard.port, shard.database

    def _get_geographic_shard(self, business_data: dict[str, Any]) -> str:
        """Get shard based on geographic location."""
        # Extract location information
        zip_code = business_data.get("zip", "")
        state = business_data.get("state", "").upper()
        city = business_data.get("city", "").lower()

        # Use zip code for precise mapping
        if zip_code:
            return self._geographic_map.get(zip_code[:3], self.config.default_shard)

        # Fall back to state-based mapping
        if state:
            return self._geographic_map.get(state, self.config.default_shard)

        # Fall back to city-based mapping
        if city:
            return self._geographic_map.get(city, self.config.default_shard)

        return self.config.default_shard

    def _get_source_based_shard(self, business_data: dict[str, Any]) -> str:
        """Get shard based on data source."""
        source = business_data.get("source", "").lower()
        return self._source_map.get(source, self.config.default_shard)

    def _get_hash_based_shard(self, business_data: dict[str, Any]) -> str:
        """Get shard based on hash of business ID."""
        business_id = str(business_data.get("id", business_data.get("source_id", "")))
        if not business_id:
            return self.config.default_shard

        # Use consistent hashing
        hash_value = hashlib.md5(
            business_id.encode(), usedforsecurity=False
        ).hexdigest()  # nosec B324
        shard_index = int(hash_value[:8], 16) % len(self.config.shards)
        return self.config.shards[shard_index].shard_id

    def _get_hybrid_shard(self, business_data: dict[str, Any]) -> str:
        """Get shard using hybrid strategy (geographic + hash)."""
        # First try geographic
        geo_shard = self._get_geographic_shard(business_data)

        # If we have a specific geographic mapping, use it
        if geo_shard != self.config.default_shard:
            return geo_shard

        # Fall back to hash-based for unknown locations
        return self._get_hash_based_shard(business_data)

    def _get_geographic_shards_for_query(
        self, query_params: dict[str, Any]
    ) -> list[str]:
        """Get shards for geographic query."""
        zip_codes = query_params.get("zip_codes", [])
        states = query_params.get("states", [])
        cities = query_params.get("cities", [])

        shards = set()

        # Map zip codes to shards
        for zip_code in zip_codes:
            shard = self._geographic_map.get(zip_code[:3], self.config.default_shard)
            shards.add(shard)

        # Map states to shards
        for state in states:
            shard = self._geographic_map.get(state.upper(), self.config.default_shard)
            shards.add(shard)

        # Map cities to shards
        for city in cities:
            shard = self._geographic_map.get(city.lower(), self.config.default_shard)
            shards.add(shard)

        # If no specific geographic filters, query all shards
        if not (zip_codes or states or cities):
            return [shard.shard_id for shard in self.config.shards]

        return list(shards)

    def _get_source_shards_for_query(self, query_params: dict[str, Any]) -> list[str]:
        """Get shards for source-based query."""
        sources = query_params.get("sources", [])

        if not sources:
            return [shard.shard_id for shard in self.config.shards]

        shards = set()
        for source in sources:
            shard = self._source_map.get(source.lower(), self.config.default_shard)
            shards.add(shard)

        return list(shards)

    def _get_hybrid_shards_for_query(self, query_params: dict[str, Any]) -> list[str]:
        """Get shards for hybrid query."""
        geo_shards = self._get_geographic_shards_for_query(query_params)
        source_shards = self._get_source_shards_for_query(query_params)

        # Return intersection if both filters are present
        if (
            query_params.get("zip_codes")
            or query_params.get("states")
            or query_params.get("cities")
        ):
            if query_params.get("sources"):
                return list(set(geo_shards) & set(source_shards))
            return geo_shards

        return source_shards

    def _build_geographic_map(self) -> dict[str, str]:
        """Build mapping from geographic identifiers to shard IDs."""
        # This is a simplified mapping - in production, this would be more comprehensive
        geographic_map = {
            # Zip code prefixes (first 3 digits)
            "100": "shard_east",  # NYC area
            "101": "shard_east",  # NYC area
            "102": "shard_east",  # NYC area
            "103": "shard_east",  # NYC area
            "104": "shard_east",  # NYC area
            "105": "shard_east",  # NYC area
            "989": "shard_west",  # Washington state
            "990": "shard_west",  # Washington state
            "460": "shard_central",  # Indiana
            "461": "shard_central",  # Indiana
            "462": "shard_central",  # Indiana
            # States
            "NY": "shard_east",
            "NJ": "shard_east",
            "CT": "shard_east",
            "MA": "shard_east",
            "WA": "shard_west",
            "OR": "shard_west",
            "CA": "shard_west",
            "IN": "shard_central",
            "IL": "shard_central",
            "OH": "shard_central",
            # Cities
            "new york": "shard_east",
            "yakima": "shard_west",
            "carmel": "shard_central",
        }

        return geographic_map

    def _build_source_map(self) -> dict[str, str]:
        """Build mapping from data sources to shard IDs."""
        source_map = {
            "yelp": "shard_yelp",
            "google_places": "shard_google",
            "yellowpages": "shard_other",
            "manual": "shard_other",
        }

        return source_map


def create_default_sharding_config() -> ShardingConfig:
    """Create default sharding configuration for development."""
    shards = [
        ShardConfig(
            shard_id="shard_east",
            host="postgres-east",
            port=5432,
            database="leadfactory_east",
            username="leadfactory",
            password="leadfactory_password",  # pragma: allowlist secret
            read_replicas=[
                {
                    "host": "postgres-east-replica1",
                    "port": 5432,
                    "database": "leadfactory_east",
                },
                {
                    "host": "postgres-east-replica2",
                    "port": 5432,
                    "database": "leadfactory_east",
                },
            ],
        ),
        ShardConfig(
            shard_id="shard_west",
            host="postgres-west",
            port=5432,
            database="leadfactory_west",
            username="leadfactory",
            password="leadfactory_password",  # pragma: allowlist secret
            read_replicas=[
                {
                    "host": "postgres-west-replica1",
                    "port": 5432,
                    "database": "leadfactory_west",
                },
            ],
        ),
        ShardConfig(
            shard_id="shard_central",
            host="postgres-central",
            port=5432,
            database="leadfactory_central",
            username="leadfactory",
            password="leadfactory_password",  # pragma: allowlist secret
        ),
    ]

    return ShardingConfig(
        strategy=ShardingStrategy.HYBRID,
        shards=shards,
        default_shard="shard_central",
        replication_factor=2,
    )


# Global shard router instance
_shard_router: Optional[ShardRouter] = None


def get_shard_router() -> ShardRouter:
    """Get global shard router instance."""
    global _shard_router
    if _shard_router is None:
        config = create_default_sharding_config()
        _shard_router = ShardRouter(config)
    return _shard_router


def reset_shard_router():
    """Reset global shard router (useful for testing)."""
    global _shard_router
    _shard_router = None
