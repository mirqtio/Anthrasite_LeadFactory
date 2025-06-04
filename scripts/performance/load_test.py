#!/usr/bin/env python3
"""
Load testing script for scalable LeadFactory architecture.
Tests throughput, latency, and error rates at various load levels.
"""

import asyncio
import aiohttp
import argparse
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import statistics
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from leadfactory.utils.logging import get_logger
from leadfactory.utils.metrics import record_metric

logger = get_logger(__name__)


@dataclass
class LoadTestConfig:
    """Configuration for load testing."""

    base_url: str = "http://localhost:80"
    target_rps: int = 100  # Requests per second
    duration_minutes: int = 10
    ramp_up_minutes: int = 2
    concurrent_users: int = 50
    test_endpoints: List[str] = None


@dataclass
class TestResult:
    """Individual request result."""

    endpoint: str
    status_code: int
    response_time: float
    timestamp: datetime
    error: Optional[str] = None


@dataclass
class LoadTestResults:
    """Aggregated load test results."""

    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    p95_response_time: float
    p99_response_time: float
    error_rate: float
    throughput_rps: float
    results_by_endpoint: Dict[str, List[TestResult]]


class LoadTester:
    """Load testing orchestrator."""

    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.results: List[TestResult] = []
        self.session: Optional[aiohttp.ClientSession] = None

        # Default test endpoints if not provided
        if not config.test_endpoints:
            self.config.test_endpoints = [
                "/api/scrape",
                "/api/enrich",
                "/api/score",
                "/api/mockup",
                "/api/email",
            ]

    async def create_session(self):
        """Create HTTP session with appropriate settings."""
        timeout = aiohttp.ClientTimeout(total=300)  # 5 minutes
        connector = aiohttp.TCPConnector(
            limit=self.config.concurrent_users * 2,
            limit_per_host=self.config.concurrent_users,
        )
        self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)

    async def close_session(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()

    async def make_request(self, endpoint: str) -> TestResult:
        """Make a single HTTP request and record metrics."""
        url = f"{self.config.base_url}{endpoint}"
        start_time = time.time()

        try:
            # Generate test payload based on endpoint
            payload = self._generate_test_payload(endpoint)

            async with self.session.post(
                url, json=payload, headers={"Content-Type": "application/json"}
            ) as response:
                await response.text()  # Read response body
                response_time = time.time() - start_time

                return TestResult(
                    endpoint=endpoint,
                    status_code=response.status,
                    response_time=response_time,
                    timestamp=datetime.now(),
                )

        except Exception as e:
            response_time = time.time() - start_time
            return TestResult(
                endpoint=endpoint,
                status_code=0,
                response_time=response_time,
                timestamp=datetime.now(),
                error=str(e),
            )

    def _generate_test_payload(self, endpoint: str) -> Dict:
        """Generate appropriate test payload for each endpoint."""
        if endpoint == "/api/scrape":
            return {"zip_code": "10001", "vertical": "restaurant", "limit": 10}
        elif endpoint == "/api/enrich":
            return {
                "business_id": "test-123",
                "website": "https://example.com",
                "tier": 1,
            }
        elif endpoint == "/api/score":
            return {
                "business": {
                    "id": "test-123",
                    "name": "Test Business",
                    "industry": "restaurant",
                    "website": "https://example.com",
                }
            }
        elif endpoint == "/api/mockup":
            return {
                "business_id": "test-123",
                "website": "https://example.com",
                "improvements": ["speed", "mobile"],
            }
        elif endpoint == "/api/email":
            return {
                "business_id": "test-123",
                "template": "initial_outreach",
                "to_email": "test@example.com",
            }
        else:
            return {"test": True}

    async def worker(self, worker_id: int) -> List[TestResult]:
        """Individual worker that makes requests continuously."""
        worker_results = []
        start_time = time.time()
        duration_seconds = self.config.duration_minutes * 60
        ramp_up_seconds = self.config.ramp_up_minutes * 60

        # Calculate delay between requests for this worker
        requests_per_worker = self.config.target_rps / self.config.concurrent_users
        delay_between_requests = (
            1.0 / requests_per_worker if requests_per_worker > 0 else 1.0
        )

        logger.info(
            f"Worker {worker_id} starting - {requests_per_worker:.2f} RPS, "
            f"{delay_between_requests:.3f}s delay"
        )

        while time.time() - start_time < duration_seconds:
            # Ramp up gradually
            elapsed = time.time() - start_time
            if elapsed < ramp_up_seconds:
                current_delay = (
                    delay_between_requests
                    * (ramp_up_seconds - elapsed)
                    / ramp_up_seconds
                )
                await asyncio.sleep(current_delay)

            # Select endpoint (round-robin)
            endpoint = self.config.test_endpoints[
                len(worker_results) % len(self.config.test_endpoints)
            ]

            # Make request
            result = await self.make_request(endpoint)
            worker_results.append(result)

            # Respect rate limiting
            await asyncio.sleep(delay_between_requests)

        logger.info(f"Worker {worker_id} completed {len(worker_results)} requests")
        return worker_results

    async def run_load_test(self) -> LoadTestResults:
        """Execute the load test with multiple concurrent workers."""
        logger.info(
            f"Starting load test: {self.config.target_rps} RPS for "
            f"{self.config.duration_minutes} minutes with "
            f"{self.config.concurrent_users} concurrent users"
        )

        await self.create_session()

        try:
            # Start all workers
            tasks = [self.worker(i) for i in range(self.config.concurrent_users)]

            # Wait for all workers to complete
            start_time = time.time()
            worker_results = await asyncio.gather(*tasks)
            total_time = time.time() - start_time

            # Aggregate results
            all_results = []
            for worker_result in worker_results:
                all_results.extend(worker_result)

            return self._analyze_results(all_results, total_time)

        finally:
            await self.close_session()

    def _analyze_results(
        self, results: List[TestResult], total_time: float
    ) -> LoadTestResults:
        """Analyze and aggregate test results."""
        if not results:
            raise ValueError("No test results to analyze")

        # Basic statistics
        total_requests = len(results)
        successful_requests = len([r for r in results if 200 <= r.status_code < 300])
        failed_requests = total_requests - successful_requests
        error_rate = failed_requests / total_requests * 100
        throughput_rps = total_requests / total_time

        # Response time statistics
        response_times = [r.response_time for r in results]
        avg_response_time = statistics.mean(response_times)
        p95_response_time = statistics.quantiles(response_times, n=20)[
            18
        ]  # 95th percentile
        p99_response_time = statistics.quantiles(response_times, n=100)[
            98
        ]  # 99th percentile

        # Group by endpoint
        results_by_endpoint = {}
        for result in results:
            if result.endpoint not in results_by_endpoint:
                results_by_endpoint[result.endpoint] = []
            results_by_endpoint[result.endpoint].append(result)

        return LoadTestResults(
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_response_time=avg_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            error_rate=error_rate,
            throughput_rps=throughput_rps,
            results_by_endpoint=results_by_endpoint,
        )

    def print_results(self, results: LoadTestResults):
        """Print formatted test results."""
        print("\n" + "=" * 80)
        print("LOAD TEST RESULTS")
        print("=" * 80)
        print(f"Total Requests:      {results.total_requests:,}")
        print(f"Successful:          {results.successful_requests:,}")
        print(f"Failed:              {results.failed_requests:,}")
        print(f"Error Rate:          {results.error_rate:.2f}%")
        print(f"Throughput:          {results.throughput_rps:.2f} RPS")
        print(f"Avg Response Time:   {results.avg_response_time*1000:.2f}ms")
        print(f"95th Percentile:     {results.p95_response_time*1000:.2f}ms")
        print(f"99th Percentile:     {results.p99_response_time*1000:.2f}ms")

        print("\nResults by Endpoint:")
        print("-" * 80)
        for endpoint, endpoint_results in results.results_by_endpoint.items():
            successful = len(
                [r for r in endpoint_results if 200 <= r.status_code < 300]
            )
            total = len(endpoint_results)
            error_rate = (total - successful) / total * 100 if total > 0 else 0
            avg_time = statistics.mean([r.response_time for r in endpoint_results])

            print(
                f"{endpoint:<20} {total:>6} requests, {successful:>6} successful, "
                f"{error_rate:>5.1f}% errors, {avg_time*1000:>7.2f}ms avg"
            )


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Load test LeadFactory scalable architecture"
    )
    parser.add_argument(
        "--base-url", default="http://localhost:80", help="Base URL for API gateway"
    )
    parser.add_argument(
        "--rps", type=int, default=100, help="Target requests per second"
    )
    parser.add_argument(
        "--duration", type=int, default=10, help="Test duration in minutes"
    )
    parser.add_argument(
        "--ramp-up", type=int, default=2, help="Ramp up duration in minutes"
    )
    parser.add_argument(
        "--users", type=int, default=50, help="Number of concurrent users"
    )
    parser.add_argument("--endpoints", nargs="+", help="Specific endpoints to test")
    parser.add_argument("--output", help="Output file for results (JSON)")

    args = parser.parse_args()

    # Configure load test
    config = LoadTestConfig(
        base_url=args.base_url,
        target_rps=args.rps,
        duration_minutes=args.duration,
        ramp_up_minutes=args.ramp_up,
        concurrent_users=args.users,
        test_endpoints=args.endpoints,
    )

    # Run load test
    tester = LoadTester(config)
    try:
        results = await tester.run_load_test()
        tester.print_results(results)

        # Save results if output file specified
        if args.output:
            output_data = {
                "config": config.__dict__,
                "results": {
                    "total_requests": results.total_requests,
                    "successful_requests": results.successful_requests,
                    "failed_requests": results.failed_requests,
                    "error_rate": results.error_rate,
                    "throughput_rps": results.throughput_rps,
                    "avg_response_time": results.avg_response_time,
                    "p95_response_time": results.p95_response_time,
                    "p99_response_time": results.p99_response_time,
                },
                "timestamp": datetime.now().isoformat(),
            }

            with open(args.output, "w") as f:
                json.dump(output_data, f, indent=2)

            print(f"\nResults saved to {args.output}")

        # Check if performance targets are met
        if results.throughput_rps >= config.target_rps * 0.95:  # Within 5% of target
            print(
                f"\n✅ PASS: Throughput target met ({results.throughput_rps:.2f} >= {config.target_rps * 0.95:.2f} RPS)"
            )
        else:
            print(
                f"\n❌ FAIL: Throughput target not met ({results.throughput_rps:.2f} < {config.target_rps * 0.95:.2f} RPS)"
            )

        if results.error_rate <= 1.0:  # Less than 1% error rate
            print(f"✅ PASS: Error rate acceptable ({results.error_rate:.2f}% <= 1.0%)")
        else:
            print(f"❌ FAIL: Error rate too high ({results.error_rate:.2f}% > 1.0%)")

        if results.p95_response_time <= 5.0:  # Less than 5 seconds
            print(
                f"✅ PASS: Response time acceptable ({results.p95_response_time*1000:.2f}ms <= 5000ms)"
            )
        else:
            print(
                f"❌ FAIL: Response time too high ({results.p95_response_time*1000:.2f}ms > 5000ms)"
            )

    except Exception as e:
        logger.error(f"Load test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
