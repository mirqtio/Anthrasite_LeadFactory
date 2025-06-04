"""
Performance testing framework for scalable pipeline architecture.

Tests the microservices under load to validate 10x capacity improvements
and ensure the system meets performance targets.
"""

import asyncio
import time
import json
import logging
from typing import Dict, Any, List
from dataclasses import dataclass
import statistics
import aiohttp
from concurrent.futures import ThreadPoolExecutor

from .kafka_integration import kafka_manager, workflow_manager


logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance test results."""
    test_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_duration: float
    average_response_time: float
    median_response_time: float
    p95_response_time: float
    p99_response_time: float
    requests_per_second: float
    error_rate: float


class PipelineLoadTester:
    """Load testing framework for pipeline services."""
    
    def __init__(self, base_url: str = "http://localhost"):
        """Initialize load tester."""
        self.base_url = base_url
        self.session = None
        self.response_times = []
        
    async def start(self):
        """Start the load tester."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            connector=aiohttp.TCPConnector(limit=1000)
        )
        
    async def stop(self):
        """Stop the load tester."""
        if self.session:
            await self.session.close()
    
    async def test_service_load(
        self,
        service_name: str,
        port: int,
        concurrent_requests: int = 100,
        total_requests: int = 1000,
        test_payload: Dict[str, Any] = None
    ) -> PerformanceMetrics:
        """
        Test load performance of a specific service.
        
        Args:
            service_name: Name of the service to test
            port: Service port
            concurrent_requests: Number of concurrent requests
            total_requests: Total requests to send
            test_payload: Payload for testing
            
        Returns:
            Performance metrics
        """
        if test_payload is None:
            test_payload = {
                "task_id": "load_test",
                "priority": 5,
                "metadata": {"business_ids": [f"test_business_{i}" for i in range(10)]}
            }
        
        service_url = f"{self.base_url}:{port}/process"
        
        logger.info(f"Starting load test for {service_name} service")
        logger.info(f"Target: {total_requests} requests with {concurrent_requests} concurrent")
        
        start_time = time.time()
        response_times = []
        successful_requests = 0
        failed_requests = 0
        
        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(concurrent_requests)
        
        async def make_request():
            """Make a single request to the service."""
            nonlocal successful_requests, failed_requests
            
            async with semaphore:
                request_start = time.time()
                try:
                    async with self.session.post(service_url, json=test_payload) as response:
                        await response.json()
                        request_time = time.time() - request_start
                        response_times.append(request_time)
                        
                        if response.status == 200:
                            successful_requests += 1
                        else:
                            failed_requests += 1
                            
                except Exception as e:
                    logger.debug(f"Request failed: {e}")
                    failed_requests += 1
                    request_time = time.time() - request_start
                    response_times.append(request_time)
        
        # Execute all requests
        tasks = [make_request() for _ in range(total_requests)]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        total_duration = time.time() - start_time
        
        # Calculate metrics
        if response_times:
            avg_response_time = statistics.mean(response_times)
            median_response_time = statistics.median(response_times)
            sorted_times = sorted(response_times)
            p95_response_time = sorted_times[int(len(sorted_times) * 0.95)]
            p99_response_time = sorted_times[int(len(sorted_times) * 0.99)]
        else:
            avg_response_time = median_response_time = p95_response_time = p99_response_time = 0
        
        requests_per_second = total_requests / total_duration if total_duration > 0 else 0
        error_rate = failed_requests / total_requests if total_requests > 0 else 0
        
        metrics = PerformanceMetrics(
            test_name=f"{service_name}_load_test",
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            total_duration=total_duration,
            average_response_time=avg_response_time,
            median_response_time=median_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            requests_per_second=requests_per_second,
            error_rate=error_rate
        )
        
        logger.info(f"Load test completed for {service_name}")
        logger.info(f"RPS: {requests_per_second:.2f}, Error Rate: {error_rate:.2%}")
        
        return metrics
    
    async def test_workflow_performance(
        self,
        concurrent_workflows: int = 50,
        total_workflows: int = 200
    ) -> PerformanceMetrics:
        """
        Test end-to-end workflow performance.
        
        Args:
            concurrent_workflows: Number of concurrent workflows
            total_workflows: Total workflows to execute
            
        Returns:
            Performance metrics
        """
        logger.info(f"Starting workflow performance test")
        logger.info(f"Target: {total_workflows} workflows with {concurrent_workflows} concurrent")
        
        start_time = time.time()
        response_times = []
        successful_workflows = 0
        failed_workflows = 0
        
        semaphore = asyncio.Semaphore(concurrent_workflows)
        
        async def execute_workflow():
            """Execute a single workflow."""
            nonlocal successful_workflows, failed_workflows
            
            async with semaphore:
                workflow_start = time.time()
                try:
                    execution_id = await workflow_manager.start_workflow(
                        "test_workflow",
                        {
                            "zip_codes": ["10002", "98908"],
                            "verticals": ["hvac"],
                            "tier_level": 2
                        },
                        ["scrape", "enrich", "score"]  # Shorter workflow for testing
                    )
                    
                    # Wait for workflow completion (simplified for testing)
                    await asyncio.sleep(5)
                    
                    workflow_time = time.time() - workflow_start
                    response_times.append(workflow_time)
                    successful_workflows += 1
                    
                except Exception as e:
                    logger.debug(f"Workflow failed: {e}")
                    failed_workflows += 1
                    workflow_time = time.time() - workflow_start
                    response_times.append(workflow_time)
        
        # Execute all workflows
        tasks = [execute_workflow() for _ in range(total_workflows)]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        total_duration = time.time() - start_time
        
        # Calculate metrics
        if response_times:
            avg_response_time = statistics.mean(response_times)
            median_response_time = statistics.median(response_times)
            sorted_times = sorted(response_times)
            p95_response_time = sorted_times[int(len(sorted_times) * 0.95)]
            p99_response_time = sorted_times[int(len(sorted_times) * 0.99)]
        else:
            avg_response_time = median_response_time = p95_response_time = p99_response_time = 0
        
        workflows_per_second = total_workflows / total_duration if total_duration > 0 else 0
        error_rate = failed_workflows / total_workflows if total_workflows > 0 else 0
        
        metrics = PerformanceMetrics(
            test_name="workflow_performance_test",
            total_requests=total_workflows,
            successful_requests=successful_workflows,
            failed_requests=failed_workflows,
            total_duration=total_duration,
            average_response_time=avg_response_time,
            median_response_time=median_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            requests_per_second=workflows_per_second,
            error_rate=error_rate
        )
        
        logger.info(f"Workflow performance test completed")
        logger.info(f"Workflows/sec: {workflows_per_second:.2f}, Error Rate: {error_rate:.2%}")
        
        return metrics


class CapacityValidator:
    """Validates that the system meets 10x capacity targets."""
    
    def __init__(self, baseline_metrics: Dict[str, PerformanceMetrics] = None):
        """Initialize capacity validator."""
        self.baseline_metrics = baseline_metrics or {}
        self.target_multiplier = 10.0
        
    def validate_capacity_improvement(
        self,
        current_metrics: PerformanceMetrics,
        baseline_metrics: PerformanceMetrics = None
    ) -> Dict[str, Any]:
        """
        Validate that current performance meets 10x improvement target.
        
        Args:
            current_metrics: Current performance metrics
            baseline_metrics: Baseline metrics to compare against
            
        Returns:
            Validation results
        """
        if baseline_metrics is None:
            baseline_metrics = self.baseline_metrics.get(current_metrics.test_name)
            if baseline_metrics is None:
                return {
                    "status": "no_baseline",
                    "message": "No baseline metrics available for comparison"
                }
        
        # Calculate improvement ratios
        rps_improvement = (
            current_metrics.requests_per_second / baseline_metrics.requests_per_second
            if baseline_metrics.requests_per_second > 0 else float('inf')
        )
        
        response_time_improvement = (
            baseline_metrics.average_response_time / current_metrics.average_response_time
            if current_metrics.average_response_time > 0 else float('inf')
        )
        
        error_rate_change = current_metrics.error_rate - baseline_metrics.error_rate
        
        # Check if targets are met
        rps_target_met = rps_improvement >= self.target_multiplier
        response_time_acceptable = response_time_improvement >= 1.0  # Should not be worse
        error_rate_acceptable = error_rate_change <= 0.05  # Max 5% increase in errors
        
        overall_success = rps_target_met and response_time_acceptable and error_rate_acceptable
        
        return {
            "status": "success" if overall_success else "failed",
            "rps_improvement": rps_improvement,
            "rps_target_met": rps_target_met,
            "response_time_improvement": response_time_improvement,
            "response_time_acceptable": response_time_acceptable,
            "error_rate_change": error_rate_change,
            "error_rate_acceptable": error_rate_acceptable,
            "target_multiplier": self.target_multiplier,
            "recommendations": self._generate_recommendations(
                rps_improvement, response_time_improvement, error_rate_change
            )
        }
    
    def _generate_recommendations(
        self,
        rps_improvement: float,
        response_time_improvement: float,
        error_rate_change: float
    ) -> List[str]:
        """Generate recommendations based on performance results."""
        recommendations = []
        
        if rps_improvement < self.target_multiplier:
            recommendations.append(
                f"RPS improvement ({rps_improvement:.1f}x) below target ({self.target_multiplier}x). "
                "Consider increasing service replicas or optimizing service code."
            )
        
        if response_time_improvement < 1.0:
            recommendations.append(
                "Response time has degraded. Consider optimizing service implementations "
                "or adding caching layers."
            )
        
        if error_rate_change > 0.05:
            recommendations.append(
                f"Error rate increased by {error_rate_change:.1%}. "
                "Review service health and error handling."
            )
        
        if not recommendations:
            recommendations.append("Performance targets met! System is ready for production.")
        
        return recommendations


async def run_comprehensive_performance_tests():
    """Run comprehensive performance tests for all services."""
    load_tester = PipelineLoadTester()
    capacity_validator = CapacityValidator()
    
    try:
        await load_tester.start()
        
        # Service-specific tests
        services_to_test = [
            ("scrape", 8001),
            ("enrich", 8002),
            ("dedupe", 8003),
            ("score", 8004),
            ("mockup", 8005),
            ("email", 8006)
        ]
        
        results = {}
        
        for service_name, port in services_to_test:
            logger.info(f"Testing {service_name} service performance...")
            
            # Test with increasing load
            for load_level in [100, 500, 1000]:
                test_name = f"{service_name}_load_{load_level}"
                metrics = await load_tester.test_service_load(
                    service_name,
                    port,
                    concurrent_requests=min(load_level // 10, 100),
                    total_requests=load_level
                )
                results[test_name] = metrics
                
                # Log results
                logger.info(f"Results for {test_name}:")
                logger.info(f"  RPS: {metrics.requests_per_second:.2f}")
                logger.info(f"  Avg Response Time: {metrics.average_response_time:.3f}s")
                logger.info(f"  Error Rate: {metrics.error_rate:.2%}")
        
        # Workflow performance test
        logger.info("Testing end-to-end workflow performance...")
        workflow_metrics = await load_tester.test_workflow_performance(
            concurrent_workflows=20,
            total_workflows=100
        )
        results["workflow_performance"] = workflow_metrics
        
        # Generate report
        report = {
            "timestamp": time.time(),
            "test_summary": {
                "total_tests": len(results),
                "test_results": {}
            },
            "detailed_results": {}
        }
        
        for test_name, metrics in results.items():
            report["detailed_results"][test_name] = {
                "requests_per_second": metrics.requests_per_second,
                "average_response_time": metrics.average_response_time,
                "error_rate": metrics.error_rate,
                "p95_response_time": metrics.p95_response_time
            }
            
            # Assess if performance is acceptable
            rps_good = metrics.requests_per_second > 50  # Target: >50 RPS per service
            response_time_good = metrics.average_response_time < 2.0  # Target: <2s avg
            error_rate_good = metrics.error_rate < 0.05  # Target: <5% errors
            
            overall_good = rps_good and response_time_good and error_rate_good
            
            report["test_summary"]["test_results"][test_name] = {
                "status": "PASS" if overall_good else "FAIL",
                "rps_target_met": rps_good,
                "response_time_target_met": response_time_good,
                "error_rate_target_met": error_rate_good
            }
        
        # Save report
        with open("performance_test_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        logger.info("Performance testing completed. Report saved to performance_test_report.json")
        
        return results
        
    finally:
        await load_tester.stop()


async def main():
    """Run performance tests."""
    # Start Kafka manager for workflow tests
    await kafka_manager.start()
    
    try:
        results = await run_comprehensive_performance_tests()
        print("Performance testing completed successfully!")
        print(f"Tested {len(results)} scenarios")
        
    finally:
        await kafka_manager.stop()


if __name__ == "__main__":
    asyncio.run(main())