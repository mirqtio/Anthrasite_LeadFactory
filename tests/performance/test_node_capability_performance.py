"""
Performance benchmark tests for NodeCapability configurations.

Tests the performance impact of environment-aware capability selection
and ensures the new system doesn't introduce significant overhead.
"""

import os
import time
import statistics
from unittest.mock import patch
import pytest

from leadfactory.config.node_config import (
    DeploymentEnvironment,
    NodeType,
    get_deployment_environment,
    get_enabled_capabilities,
    estimate_node_cost,
    get_environment_info,
    validate_environment_configuration,
)
from leadfactory.pipeline.dag_traversal import PipelineDAG


class TestCapabilitySelectionPerformance:
    """Test performance of capability selection operations."""

    def test_environment_detection_performance(self):
        """Test environment detection performance."""
        iterations = 1000
        times = []

        # Test with various environment configurations
        env_configs = [
            {"DEPLOYMENT_ENVIRONMENT": "development"},
            {"DEPLOYMENT_ENVIRONMENT": "production_audit"},
            {"DEPLOYMENT_ENVIRONMENT": "production_general"},
            {"NODE_ENV": "development"},
            {"BUSINESS_MODEL": "audit"},
            {},  # Default case
        ]

        for env_config in env_configs:
            with patch.dict(os.environ, env_config, clear=True):
                start_time = time.perf_counter()
                for _ in range(iterations):
                    get_deployment_environment()
                end_time = time.perf_counter()

                avg_time = (end_time - start_time) / iterations
                times.append(avg_time)

        # Environment detection should be very fast (< 1ms per call)
        max_time = max(times)
        avg_time = statistics.mean(times)

        assert max_time < 0.001, f"Environment detection too slow: {max_time:.6f}s"
        assert avg_time < 0.0005, f"Average environment detection too slow: {avg_time:.6f}s"

        print(f"Environment detection performance:")
        print(f"  Average: {avg_time*1000:.3f}ms")
        print(f"  Maximum: {max_time*1000:.3f}ms")

    @patch('leadfactory.config.node_config.is_api_available')
    def test_capability_selection_performance(self, mock_api_available):
        """Test capability selection performance."""
        # Mock all APIs as available for consistent testing
        mock_api_available.return_value = True

        iterations = 100
        node_types = [NodeType.ENRICH, NodeType.FINAL_OUTPUT]
        environments = [
            DeploymentEnvironment.DEVELOPMENT,
            DeploymentEnvironment.PRODUCTION_AUDIT,
            DeploymentEnvironment.PRODUCTION_GENERAL,
        ]

        performance_data = {}

        for env in environments:
            env_times = []
            with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": env.value}):
                for node_type in node_types:
                    start_time = time.perf_counter()
                    for _ in range(iterations):
                        get_enabled_capabilities(node_type)
                    end_time = time.perf_counter()

                    avg_time = (end_time - start_time) / iterations
                    env_times.append(avg_time)

            performance_data[env] = {
                "avg_time": statistics.mean(env_times),
                "max_time": max(env_times),
            }

        # Capability selection should be fast (< 10ms per call)
        for env, data in performance_data.items():
            assert data["max_time"] < 0.01, \
                f"Capability selection too slow in {env.value}: {data['max_time']:.6f}s"
            assert data["avg_time"] < 0.005, \
                f"Average capability selection too slow in {env.value}: {data['avg_time']:.6f}s"

        print(f"Capability selection performance:")
        for env, data in performance_data.items():
            print(f"  {env.value}: avg={data['avg_time']*1000:.3f}ms, max={data['max_time']*1000:.3f}ms")

    @patch('leadfactory.config.node_config.is_api_available')
    def test_cost_estimation_performance(self, mock_api_available):
        """Test cost estimation performance."""
        # Mock all APIs as available
        mock_api_available.return_value = True

        iterations = 100
        node_types = [NodeType.ENRICH, NodeType.FINAL_OUTPUT]
        budget_scenarios = [None, 0.0, 1.0, 5.0, 10.0, 20.0]

        times = []

        with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": "production_general"}):
            for node_type in node_types:
                for budget in budget_scenarios:
                    start_time = time.perf_counter()
                    for _ in range(iterations):
                        estimate_node_cost(node_type, budget_cents=budget)
                    end_time = time.perf_counter()

                    avg_time = (end_time - start_time) / iterations
                    times.append(avg_time)

        max_time = max(times)
        avg_time = statistics.mean(times)

        # Cost estimation should be very fast (< 5ms per call)
        assert max_time < 0.005, f"Cost estimation too slow: {max_time:.6f}s"
        assert avg_time < 0.002, f"Average cost estimation too slow: {avg_time:.6f}s"

        print(f"Cost estimation performance:")
        print(f"  Average: {avg_time*1000:.3f}ms")
        print(f"  Maximum: {max_time*1000:.3f}ms")


class TestDAGTraversalPerformance:
    """Test performance impact on DAG traversal."""

    @patch('leadfactory.config.node_config.is_api_available')
    def test_dag_execution_plan_performance(self, mock_api_available):
        """Test DAG execution plan generation performance."""
        # Mock all APIs as available
        mock_api_available.return_value = True

        iterations = 50
        node_types = [NodeType.ENRICH, NodeType.FINAL_OUTPUT]

        dag = PipelineDAG()
        times = []

        for node_type in node_types:
            with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": "production_general"}):
                start_time = time.perf_counter()
                for _ in range(iterations):
                    dag.get_execution_plan(node_type=node_type, budget_cents=10.0)
                end_time = time.perf_counter()

                avg_time = (end_time - start_time) / iterations
                times.append(avg_time)

        max_time = max(times)
        avg_time = statistics.mean(times)

        # DAG traversal should remain fast (< 20ms per call)
        assert max_time < 0.02, f"DAG execution plan too slow: {max_time:.6f}s"
        assert avg_time < 0.01, f"Average DAG execution plan too slow: {avg_time:.6f}s"

        print(f"DAG execution plan performance:")
        print(f"  Average: {avg_time*1000:.3f}ms")
        print(f"  Maximum: {max_time*1000:.3f}ms")

    @patch('leadfactory.config.node_config.is_api_available')
    def test_dag_topological_sort_performance(self, mock_api_available):
        """Test DAG topological sort performance with capability filtering."""
        # Mock all APIs as available
        mock_api_available.return_value = True

        iterations = 100

        dag = PipelineDAG()
        times = []

        for env in ["development", "production_audit", "production_general"]:
            with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": env}):
                start_time = time.perf_counter()
                for _ in range(iterations):
                    dag.topological_sort(
                        node_type=NodeType.ENRICH,
                        budget_cents=10.0
                    )
                end_time = time.perf_counter()

                avg_time = (end_time - start_time) / iterations
                times.append(avg_time)

        max_time = max(times)
        avg_time = statistics.mean(times)

        # Topological sort should remain fast
        assert max_time < 0.01, f"DAG topological sort too slow: {max_time:.6f}s"
        assert avg_time < 0.005, f"Average DAG topological sort too slow: {avg_time:.6f}s"

        print(f"DAG topological sort performance:")
        print(f"  Average: {avg_time*1000:.3f}ms")
        print(f"  Maximum: {max_time*1000:.3f}ms")


class TestMemoryUsage:
    """Test memory usage of capability configurations."""

    def test_capability_configuration_memory(self):
        """Test memory usage of capability configurations."""
        import sys

        # Measure baseline memory
        initial_objects = len(gc.get_objects()) if 'gc' in globals() else 0

        # Import gc for memory testing
        import gc
        gc.collect()
        initial_objects = len(gc.get_objects())

        # Create multiple environment configurations
        environments = [
            DeploymentEnvironment.DEVELOPMENT,
            DeploymentEnvironment.PRODUCTION_AUDIT,
            DeploymentEnvironment.PRODUCTION_GENERAL,
        ]

        node_types = [NodeType.ENRICH, NodeType.FINAL_OUTPUT]

        # Generate capabilities for all combinations
        capabilities_cache = {}
        for env in environments:
            with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": env.value}):
                for node_type in node_types:
                    with patch('leadfactory.config.node_config.is_api_available') as mock_api:
                        mock_api.return_value = True
                        caps = get_enabled_capabilities(node_type)
                        capabilities_cache[(env, node_type)] = caps

        gc.collect()
        final_objects = len(gc.get_objects())

        # Memory usage should be reasonable
        object_increase = final_objects - initial_objects

        # Should not create excessive objects (< 1000 new objects for all configurations)
        assert object_increase < 1000, \
            f"Excessive memory usage: {object_increase} new objects created"

        print(f"Memory usage test:")
        print(f"  Objects created: {object_increase}")
        print(f"  Configurations cached: {len(capabilities_cache)}")


class TestScalabilityBenchmarks:
    """Test scalability with large numbers of capabilities and environments."""

    @patch('leadfactory.config.node_config.is_api_available')
    def test_large_scale_capability_evaluation(self, mock_api_available):
        """Test performance with many capability evaluations."""
        # Mock all APIs as available
        mock_api_available.return_value = True

        # Simulate a large batch processing scenario
        batch_size = 1000
        node_types = [NodeType.ENRICH, NodeType.FINAL_OUTPUT]

        start_time = time.perf_counter()

        with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": "production_general"}):
            for _ in range(batch_size):
                for node_type in node_types:
                    get_enabled_capabilities(node_type)
                    estimate_node_cost(node_type)

        end_time = time.perf_counter()
        total_time = end_time - start_time

        # Should handle large batches efficiently
        time_per_evaluation = total_time / (batch_size * len(node_types) * 2)  # 2 operations per iteration

        assert time_per_evaluation < 0.001, \
            f"Large scale evaluation too slow: {time_per_evaluation:.6f}s per evaluation"

        print(f"Large scale capability evaluation:")
        print(f"  Total operations: {batch_size * len(node_types) * 2}")
        print(f"  Total time: {total_time:.3f}s")
        print(f"  Time per evaluation: {time_per_evaluation*1000:.3f}ms")

    @patch('leadfactory.config.node_config.is_api_available')
    def test_concurrent_environment_access(self, mock_api_available):
        """Test performance with concurrent environment access simulation."""
        import threading
        import queue

        # Mock all APIs as available
        mock_api_available.return_value = True

        results_queue = queue.Queue()
        thread_count = 10
        operations_per_thread = 50

        def worker():
            """Worker function for concurrent testing."""
            times = []
            for _ in range(operations_per_thread):
                start_time = time.perf_counter()

                # Simulate different environments accessing capabilities
                env = ["development", "production_audit", "production_general"][
                    threading.current_thread().ident % 3
                ]

                with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": env}):
                    get_enabled_capabilities(NodeType.ENRICH)
                    estimate_node_cost(NodeType.FINAL_OUTPUT)

                end_time = time.perf_counter()
                times.append(end_time - start_time)

            results_queue.put(times)

        # Start threads
        threads = []
        start_time = time.perf_counter()

        for _ in range(thread_count):
            thread = threading.Thread(target=worker)
            thread.start()
            threads.append(thread)

        # Wait for completion
        for thread in threads:
            thread.join()

        end_time = time.perf_counter()
        total_time = end_time - start_time

        # Collect results
        all_times = []
        while not results_queue.empty():
            thread_times = results_queue.get()
            all_times.extend(thread_times)

        avg_operation_time = statistics.mean(all_times)
        max_operation_time = max(all_times)

        # Concurrent access should not significantly degrade performance
        assert avg_operation_time < 0.01, \
            f"Concurrent access too slow: {avg_operation_time:.6f}s average"
        assert max_operation_time < 0.05, \
            f"Concurrent access maximum too slow: {max_operation_time:.6f}s"

        print(f"Concurrent environment access:")
        print(f"  Threads: {thread_count}")
        print(f"  Operations per thread: {operations_per_thread}")
        print(f"  Total time: {total_time:.3f}s")
        print(f"  Average operation time: {avg_operation_time*1000:.3f}ms")
        print(f"  Maximum operation time: {max_operation_time*1000:.3f}ms")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])  # -s to see print output
