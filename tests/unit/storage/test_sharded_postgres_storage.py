"""
Tests for sharded PostgreSQL storage implementation.

This module tests the ShardedPostgresStorage class, including connection pool
management, shard routing, distributed operations, and failover mechanisms.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, Mock, call, patch

import psycopg2
import pytest
from psycopg2.pool import SimpleConnectionPool

from leadfactory.storage.sharded_postgres_storage import ShardedPostgresStorage
from leadfactory.storage.sharding_strategy import (
    ShardConfig,
    ShardingConfig,
    ShardingStrategy,
    ShardRouter,
)


class TestShardedPostgresStorage:
    """Test cases for ShardedPostgresStorage implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create test shard configurations
        self.shard1_config = ShardConfig(
            shard_id=1,
            host="shard1.example.com",
            port=5432,
            database="leadfactory_shard1",
            regions=["us-west"],
            sources=["yelp"],
            read_replicas=[
                {"host": "shard1-replica.example.com", "port": 5432, "database": "leadfactory_shard1"}
            ]
        )

        self.shard2_config = ShardConfig(
            shard_id=2,
            host="shard2.example.com",
            port=5432,
            database="leadfactory_shard2",
            regions=["us-east"],
            sources=["google"]
        )

        self.sharding_config = ShardingConfig(
            strategy=ShardingStrategy.GEOGRAPHIC,
            shards=[self.shard1_config, self.shard2_config]
        )

        self.storage = ShardedPostgresStorage(self.sharding_config)

    def teardown_method(self):
        """Clean up after tests."""
        if hasattr(self, "storage"):
            self.storage.close_all_pools()

    @patch("psycopg2.pool.SimpleConnectionPool")
    def test_initialize_pools(self, mock_pool_class):
        """Test connection pool initialization."""
        mock_pool_instance = MagicMock()
        mock_pool_class.return_value = mock_pool_instance

        storage = ShardedPostgresStorage(self.sharding_config)
        storage._initialize_pools()

        # Should create pools for both shards
        assert mock_pool_class.call_count == 2

        # Verify pool configuration
        calls = mock_pool_class.call_args_list
        for call in calls:
            kwargs = call[1]
            assert kwargs["minconn"] == 1
            assert kwargs["maxconn"] == 10
            assert "host" in kwargs
            assert "port" in kwargs
            assert "database" in kwargs

    @patch("psycopg2.pool.SimpleConnectionPool")
    def test_create_pool_for_shard(self, mock_pool_class):
        """Test creating connection pool for a specific shard."""
        mock_pool = MagicMock()
        mock_pool_class.return_value = mock_pool

        pool = self.storage._create_pool_for_shard(self.shard1_config)

        assert pool == mock_pool
        mock_pool_class.assert_called_once_with(
            1, 10,
            host="shard1.example.com",
            port=5432,
            database="leadfactory_shard1",
            user=None,
            password=None
        )

    def test_close_all_pools(self):
        """Test closing all connection pools."""
        # Create mock pools
        mock_pool1 = MagicMock()
        mock_pool2 = MagicMock()
        self.storage._pools = {
            1: mock_pool1,
            2: mock_pool2
        }

        self.storage.close_all_pools()

        mock_pool1.closeall.assert_called_once()
        mock_pool2.closeall.assert_called_once()
        assert len(self.storage._pools) == 0

    @patch.object(ShardedPostgresStorage, "_get_pool_for_shard")
    def test_execute_on_shard(self, mock_get_pool):
        """Test executing query on a specific shard."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_get_pool.return_value = mock_pool
        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [{"id": 1, "name": "Test"}]

        result = self.storage.execute_on_shard(
            1, "SELECT * FROM businesses WHERE id = %s", (1,)
        )

        assert result == [{"id": 1, "name": "Test"}]
        mock_cursor.execute.assert_called_once_with(
            "SELECT * FROM businesses WHERE id = %s", (1,)
        )
        mock_pool.putconn.assert_called_once_with(mock_conn)

    @patch.object(ShardedPostgresStorage, "_get_pool_for_shard")
    def test_execute_on_shard_error_handling(self, mock_get_pool):
        """Test error handling in execute_on_shard."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_get_pool.return_value = mock_pool
        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = psycopg2.DatabaseError("Query failed")

        with pytest.raises(psycopg2.DatabaseError):
            self.storage.execute_on_shard(1, "SELECT * FROM businesses", ())

        # Connection should still be returned to pool
        mock_pool.putconn.assert_called_once_with(mock_conn)

    @patch.object(ShardedPostgresStorage, "execute_on_shard")
    def test_execute_on_multiple_shards(self, mock_execute):
        """Test executing query on multiple shards."""
        mock_execute.side_effect = [
            [{"id": 1, "name": "Business 1"}],
            [{"id": 2, "name": "Business 2"}]
        ]

        result = self.storage.execute_on_multiple_shards(
            [1, 2], "SELECT * FROM businesses", ()
        )

        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["id"] == 2

        # Verify both shards were queried
        assert mock_execute.call_count == 2

    @patch.object(ShardRouter, "get_shard")
    @patch.object(ShardedPostgresStorage, "execute_on_shard")
    def test_insert_business(self, mock_execute, mock_get_shard):
        """Test inserting business with shard routing."""
        mock_get_shard.return_value = self.shard1_config
        mock_execute.return_value = [{"id": 123}]

        business_data = {
            "name": "Test Business",
            "zip": "90210",
            "source": "yelp"
        }

        result = self.storage.insert_business(business_data)

        assert result == 123
        mock_get_shard.assert_called_once_with(business_data)
        mock_execute.assert_called_once()

    @patch.object(ShardRouter, "get_shard")
    @patch.object(ShardedPostgresStorage, "execute_on_shard")
    def test_get_business_by_id_with_hint(self, mock_execute, mock_get_shard):
        """Test getting business by ID with shard hint."""
        mock_get_shard.return_value = self.shard1_config
        mock_execute.return_value = [{"id": 1, "name": "Test Business"}]

        result = self.storage.get_business_by_id(1, shard_hint={"source": "yelp"})

        assert result["id"] == 1
        mock_get_shard.assert_called_once_with({"source": "yelp"})

    @patch.object(ShardedPostgresStorage, "execute_on_multiple_shards")
    def test_get_business_by_id_without_hint(self, mock_execute_multiple):
        """Test getting business by ID without shard hint (searches all shards)."""
        mock_execute_multiple.return_value = [{"id": 1, "name": "Test Business"}]

        result = self.storage.get_business_by_id(1)

        assert result["id"] == 1
        # Should search all shards
        mock_execute_multiple.assert_called_once()
        args = mock_execute_multiple.call_args[0]
        assert len(args[0]) == 2  # Both shards

    @patch.object(ShardRouter, "get_shards_for_query")
    @patch.object(ShardedPostgresStorage, "execute_on_multiple_shards")
    def test_search_businesses(self, mock_execute_multiple, mock_get_shards):
        """Test searching businesses across shards."""
        mock_get_shards.return_value = [self.shard1_config, self.shard2_config]
        mock_execute_multiple.return_value = [
            {"id": 1, "name": "Business 1"},
            {"id": 2, "name": "Business 2"}
        ]

        criteria = {"zip": ["90210", "10001"]}
        result = self.storage.search_businesses(criteria)

        assert len(result) == 2
        mock_get_shards.assert_called_once_with(criteria)

    @patch.object(ShardRouter, "get_shard")
    @patch.object(ShardedPostgresStorage, "execute_on_shard")
    def test_update_business(self, mock_execute, mock_get_shard):
        """Test updating business on correct shard."""
        mock_get_shard.return_value = self.shard1_config
        mock_execute.return_value = []

        result = self.storage.update_business(
            1, {"name": "Updated Business"}, {"source": "yelp"}
        )

        assert result is True
        mock_get_shard.assert_called_once_with({"source": "yelp"})

    @patch.object(ShardedPostgresStorage, "execute_on_multiple_shards")
    def test_get_statistics(self, mock_execute_multiple):
        """Test aggregating statistics across shards."""
        mock_execute_multiple.return_value = [
            {"total_businesses": 1000, "active_businesses": 800},
            {"total_businesses": 500, "active_businesses": 400}
        ]

        result = self.storage.get_statistics()

        assert result["total_businesses"] == 1500
        assert result["active_businesses"] == 1200
        assert result["shards_queried"] == 2

    @patch.object(ShardedPostgresStorage, "_create_pool_for_shard")
    @patch.object(ShardedPostgresStorage, "execute_on_shard")
    def test_health_check(self, mock_execute, mock_create_pool):
        """Test health check functionality."""
        # Set up existing pools
        mock_pool1 = MagicMock()
        mock_pool2 = MagicMock()
        self.storage._pools = {1: mock_pool1, 2: mock_pool2}

        # Mock successful health checks
        mock_execute.side_effect = [
            [{"result": 1}],  # Shard 1 healthy
            [{"result": 1}]   # Shard 2 healthy
        ]

        result = self.storage.health_check()

        assert result["healthy"] is True
        assert result["total_shards"] == 2
        assert result["healthy_shards"] == 2
        assert len(result["shard_status"]) == 2

    @patch.object(ShardedPostgresStorage, "execute_on_shard")
    def test_health_check_with_failures(self, mock_execute):
        """Test health check with shard failures."""
        # Set up existing pools
        self.storage._pools = {1: MagicMock(), 2: MagicMock()}

        # Mock one healthy, one failed shard
        mock_execute.side_effect = [
            [{"result": 1}],  # Shard 1 healthy
            Exception("Connection failed")  # Shard 2 failed
        ]

        result = self.storage.health_check()

        assert result["healthy"] is False
        assert result["total_shards"] == 2
        assert result["healthy_shards"] == 1
        assert result["shard_status"][1]["status"] == "healthy"
        assert result["shard_status"][2]["status"] == "unhealthy"

    @patch.object(ShardRouter, "get_read_shard")
    @patch.object(ShardedPostgresStorage, "_get_pool_for_shard")
    def test_read_replica_usage(self, mock_get_pool, mock_get_read_shard):
        """Test that read operations use read replicas."""
        # Mock read replica configuration
        read_config = {
            "host": "shard1-replica.example.com",
            "port": 5432,
            "database": "leadfactory_shard1"
        }
        mock_get_read_shard.return_value = read_config

        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_get_pool.return_value = mock_pool
        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [{"id": 1}]

        # Execute a read query
        result = self.storage.execute_on_shard(
            1, "SELECT * FROM businesses", (), use_read_replica=True
        )

        assert result == [{"id": 1}]
        mock_get_read_shard.assert_called_once()

    def test_connection_pool_exhaustion(self):
        """Test handling of connection pool exhaustion."""
        mock_pool = MagicMock()
        mock_pool.getconn.side_effect = psycopg2.pool.PoolError("Connection pool exhausted")
        self.storage._pools = {1: mock_pool}

        with pytest.raises(psycopg2.pool.PoolError):
            self.storage.execute_on_shard(1, "SELECT 1", ())

    @patch.object(ShardedPostgresStorage, "execute_on_shard")
    def test_distributed_transaction(self, mock_execute):
        """Test distributed transaction across shards."""
        # This is a simplified test - real distributed transactions are complex
        mock_execute.return_value = []

        queries = [
            (1, "UPDATE businesses SET status = 'active' WHERE id = 1"),
            (2, "UPDATE businesses SET status = 'active' WHERE id = 2")
        ]

        # Execute updates on different shards
        for shard_id, query in queries:
            self.storage.execute_on_shard(shard_id, query, ())

        assert mock_execute.call_count == 2

    def test_shard_key_extraction(self):
        """Test extracting shard key from business data."""
        test_cases = [
            ({"zip": "90210", "source": "yelp"}, {"zip": "90210", "source": "yelp"}),
            ({"id": 123, "name": "Test"}, {"id": 123}),
            ({"address": "123 Main St", "city": "LA"}, {})
        ]

        for business_data, expected_key in test_cases:
            key = self.storage._extract_shard_key(business_data)
            assert key == expected_key

    @patch("psycopg2.pool.SimpleConnectionPool")
    def test_connection_pool_configuration(self, mock_pool_class):
        """Test connection pool configuration options."""
        custom_config = ShardingConfig(
            strategy=ShardingStrategy.HASH_BASED,
            shards=[self.shard1_config],
            pool_config={
                "minconn": 5,
                "maxconn": 20,
                "connection_timeout": 30
            }
        )

        storage = ShardedPostgresStorage(custom_config)
        storage._initialize_pools()

        mock_pool_class.assert_called_once_with(
            5, 20,  # Custom min/max connections
            host="shard1.example.com",
            port=5432,
            database="leadfactory_shard1",
            user=None,
            password=None
        )
