"""
Tests for sharding strategy module.

This module tests the ShardingStrategy, ShardConfig, and ShardRouter classes,
ensuring proper shard routing and configuration handling.
"""

import pytest
from dataclasses import dataclass
from typing import Dict, List, Optional

from leadfactory.storage.sharding_strategy import (
    ShardingStrategy,
    ShardConfig,
    ShardingConfig,
    ShardRouter
)


class TestShardingStrategy:
    """Test cases for ShardingStrategy enum."""

    def test_sharding_strategy_values(self):
        """Test that all sharding strategies are defined."""
        assert ShardingStrategy.GEOGRAPHIC.value == "geographic"
        assert ShardingStrategy.SOURCE_BASED.value == "source_based"
        assert ShardingStrategy.HASH_BASED.value == "hash_based"
        assert ShardingStrategy.HYBRID.value == "hybrid"


class TestShardConfig:
    """Test cases for ShardConfig dataclass."""

    def test_shard_config_creation(self):
        """Test creating ShardConfig instances."""
        config = ShardConfig(
            shard_id=1,
            host="localhost",
            port=5432,
            database="shard1",
            regions=["us-west", "us-east"],
            sources=["yelp", "google"],
            weight=0.5,
            read_replicas=[
                {"host": "replica1", "port": 5432, "database": "shard1"},
                {"host": "replica2", "port": 5432, "database": "shard1"}
            ]
        )

        assert config.shard_id == 1
        assert config.host == "localhost"
        assert config.port == 5432
        assert config.database == "shard1"
        assert "us-west" in config.regions
        assert "yelp" in config.sources
        assert config.weight == 0.5
        assert len(config.read_replicas) == 2

    def test_shard_config_defaults(self):
        """Test ShardConfig with default values."""
        config = ShardConfig(
            shard_id=1,
            host="localhost",
            port=5432,
            database="shard1"
        )

        assert config.regions == []
        assert config.sources == []
        assert config.weight == 1.0
        assert config.read_replicas == []


class TestShardingConfig:
    """Test cases for ShardingConfig dataclass."""

    def test_sharding_config_creation(self):
        """Test creating ShardingConfig instances."""
        shard1 = ShardConfig(
            shard_id=1,
            host="shard1.example.com",
            port=5432,
            database="leadfactory_shard1",
            regions=["us-west"]
        )

        shard2 = ShardConfig(
            shard_id=2,
            host="shard2.example.com",
            port=5432,
            database="leadfactory_shard2",
            regions=["us-east"]
        )

        config = ShardingConfig(
            strategy=ShardingStrategy.GEOGRAPHIC,
            shards=[shard1, shard2]
        )

        assert config.strategy == ShardingStrategy.GEOGRAPHIC
        assert len(config.shards) == 2
        assert config.shards[0].shard_id == 1
        assert config.shards[1].shard_id == 2


class TestShardRouter:
    """Test cases for ShardRouter class."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create test shards
        self.shard_west = ShardConfig(
            shard_id=1,
            host="west.example.com",
            port=5432,
            database="west_db",
            regions=["us-west", "us-northwest"],
            sources=["yelp"],
            weight=0.6,
            read_replicas=[
                {"host": "west-replica1", "port": 5432, "database": "west_db"}
            ]
        )

        self.shard_east = ShardConfig(
            shard_id=2,
            host="east.example.com",
            port=5432,
            database="east_db",
            regions=["us-east", "us-northeast"],
            sources=["google"],
            weight=0.4,
            read_replicas=[
                {"host": "east-replica1", "port": 5432, "database": "east_db"}
            ]
        )

        self.shard_central = ShardConfig(
            shard_id=3,
            host="central.example.com",
            port=5432,
            database="central_db",
            regions=["us-central"],
            sources=["manual"],
            weight=1.0
        )

    def test_geographic_sharding(self):
        """Test geographic sharding strategy."""
        config = ShardingConfig(
            strategy=ShardingStrategy.GEOGRAPHIC,
            shards=[self.shard_west, self.shard_east, self.shard_central]
        )
        router = ShardRouter(config)

        # Test single region routing
        result = router.get_shard({"zip": "90210"})  # California
        assert result.shard_id == 1  # West shard

        # Test query routing for multiple regions
        results = router.get_shards_for_query({"region": "us-west"})
        assert len(results) == 1
        assert results[0].shard_id == 1

    def test_source_based_sharding(self):
        """Test source-based sharding strategy."""
        config = ShardingConfig(
            strategy=ShardingStrategy.SOURCE_BASED,
            shards=[self.shard_west, self.shard_east, self.shard_central]
        )
        router = ShardRouter(config)

        # Test routing by source
        result = router.get_shard({"source": "yelp"})
        assert result.shard_id == 1  # West shard has yelp

        result = router.get_shard({"source": "google"})
        assert result.shard_id == 2  # East shard has google

        # Test query routing for specific source
        results = router.get_shards_for_query({"source": "manual"})
        assert len(results) == 1
        assert results[0].shard_id == 3

    def test_hash_based_sharding(self):
        """Test hash-based sharding strategy."""
        config = ShardingConfig(
            strategy=ShardingStrategy.HASH_BASED,
            shards=[self.shard_west, self.shard_east]
        )
        router = ShardRouter(config)

        # Test consistent hashing
        result1 = router.get_shard({"id": 12345})
        result2 = router.get_shard({"id": 12345})
        assert result1.shard_id == result2.shard_id  # Same ID should route to same shard

        # Test distribution
        shard_counts = {1: 0, 2: 0}
        for i in range(1000):
            shard = router.get_shard({"id": i})
            shard_counts[shard.shard_id] += 1

        # Both shards should get some data
        assert shard_counts[1] > 0
        assert shard_counts[2] > 0

    def test_hybrid_sharding(self):
        """Test hybrid sharding strategy."""
        config = ShardingConfig(
            strategy=ShardingStrategy.HYBRID,
            shards=[self.shard_west, self.shard_east, self.shard_central]
        )
        router = ShardRouter(config)

        # Test with both geographic and source hints
        result = router.get_shard({
            "zip": "90210",  # California
            "source": "yelp"
        })
        assert result.shard_id == 1  # West shard (matches both)

        # Test with conflicting hints (should fall back to hash)
        result = router.get_shard({
            "zip": "10001",  # New York
            "source": "yelp",  # But yelp is on west shard
            "id": 12345
        })
        assert result.shard_id in [1, 2, 3]  # Any shard possible

    def test_read_replica_selection(self):
        """Test read replica selection."""
        config = ShardingConfig(
            strategy=ShardingStrategy.GEOGRAPHIC,
            shards=[self.shard_west, self.shard_east]
        )
        router = ShardRouter(config)

        # Test getting read shard (should include replicas)
        read_config = router.get_read_shard({"zip": "90210"})

        # Should get either primary or replica
        assert read_config["host"] in ["west.example.com", "west-replica1"]

        # Test round-robin behavior
        hosts_seen = set()
        for _ in range(10):
            read_config = router.get_read_shard({"zip": "90210"})
            hosts_seen.add(read_config["host"])

        # Should see both primary and replica
        assert len(hosts_seen) >= 2

    def test_weighted_sharding(self):
        """Test weighted shard selection."""
        # Create shards with different weights
        light_shard = ShardConfig(
            shard_id=1,
            host="light.example.com",
            port=5432,
            database="light_db",
            weight=0.2  # 20% of traffic
        )

        heavy_shard = ShardConfig(
            shard_id=2,
            host="heavy.example.com",
            port=5432,
            database="heavy_db",
            weight=0.8  # 80% of traffic
        )

        config = ShardingConfig(
            strategy=ShardingStrategy.HASH_BASED,
            shards=[light_shard, heavy_shard]
        )
        router = ShardRouter(config)

        # Test weight distribution
        shard_counts = {1: 0, 2: 0}
        for i in range(1000):
            shard = router.get_shard({"id": i + 10000})  # Different IDs
            shard_counts[shard.shard_id] += 1

        # Heavy shard should get approximately 80% of traffic
        heavy_percentage = shard_counts[2] / 1000
        assert 0.75 <= heavy_percentage <= 0.85  # Allow some variance

    def test_fallback_behavior(self):
        """Test fallback behavior when no shard matches criteria."""
        config = ShardingConfig(
            strategy=ShardingStrategy.SOURCE_BASED,
            shards=[self.shard_west, self.shard_east]
        )
        router = ShardRouter(config)

        # Test with unknown source
        result = router.get_shard({"source": "unknown_source"})
        assert result.shard_id in [1, 2]  # Should fall back to any shard

        # Test query with no matches
        results = router.get_shards_for_query({"source": "unknown_source"})
        assert len(results) == 2  # Should return all shards

    def test_geographic_region_mapping(self):
        """Test ZIP code to region mapping."""
        config = ShardingConfig(
            strategy=ShardingStrategy.GEOGRAPHIC,
            shards=[self.shard_west, self.shard_east, self.shard_central]
        )
        router = ShardRouter(config)

        # Test various ZIP codes
        test_cases = [
            ("90210", 1),  # California -> West
            ("10001", 2),  # New York -> East
            ("60601", 3),  # Chicago -> Central
            ("98101", 1),  # Seattle -> West (northwest)
            ("33101", 2),  # Miami -> East
            ("75201", 3),  # Dallas -> Central
        ]

        for zip_code, expected_shard in test_cases:
            result = router.get_shard({"zip": zip_code})
            assert result.shard_id == expected_shard, f"ZIP {zip_code} routed incorrectly"

    def test_missing_routing_data(self):
        """Test behavior when routing data is missing."""
        config = ShardingConfig(
            strategy=ShardingStrategy.GEOGRAPHIC,
            shards=[self.shard_west, self.shard_east]
        )
        router = ShardRouter(config)

        # Test with no geographic data
        result = router.get_shard({})
        assert result.shard_id in [1, 2]  # Should fall back to any shard

        # Test with empty data
        result = router.get_shard({"zip": "", "source": None})
        assert result.shard_id in [1, 2]

    def test_query_routing_complex(self):
        """Test complex query routing scenarios."""
        config = ShardingConfig(
            strategy=ShardingStrategy.HYBRID,
            shards=[self.shard_west, self.shard_east, self.shard_central]
        )
        router = ShardRouter(config)

        # Test query that could match multiple shards
        results = router.get_shards_for_query({
            "zip": ["90210", "10001", "60601"],  # Multiple regions
            "source": ["yelp", "google"]  # Multiple sources
        })

        # Should return all shards that match any criteria
        assert len(results) >= 2

        # Test with AND logic (intersection)
        results = router.get_shards_for_query({
            "region": "us-west",
            "source": "yelp"
        })
        assert len(results) == 1
        assert results[0].shard_id == 1  # Only west shard matches both
