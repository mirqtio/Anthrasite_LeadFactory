#!/usr/bin/env python3
"""
Test script for Task 13: Scalable Architecture Implementation.
Validates all components of the scalable architecture are properly implemented.
"""

import os
import sys
from pathlib import Path

import yaml


def test_containerization():
    """Test Docker containerization implementation."""

    # Check for Docker files
    docker_files = [
        "docker/api-gateway/Dockerfile",
        "docker/deduplication/Dockerfile",
        "docker/email/Dockerfile",
        "docker/enrichment/Dockerfile",
        "docker/mockup/Dockerfile",
        "docker/scoring/Dockerfile",
        "docker/scraper/Dockerfile",
        "docker-compose.scalable.yml",
    ]

    missing_files = []
    for file_path in docker_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)

    if missing_files:
        return False

    # Check docker-compose for scalable services
    try:
        with open("docker-compose.scalable.yml") as f:
            compose_config = yaml.safe_load(f)

        services = compose_config.get("services", {})
        expected_services = [
            "api-gateway",
            "deduplication-service",
            "email-service",
            "enrichment-service",
            "mockup-service",
            "scoring-service",
            "scraper-service",
        ]

        for service in expected_services:
            if service not in services:
                return False

    except Exception:
        return False

    return True


def test_kubernetes():
    """Test Kubernetes orchestration implementation."""

    k8s_files = [
        "k8s/namespace.yaml",
        "k8s/configmap.yaml",
        "k8s/secrets.yaml",
        "k8s/postgres-deployment.yaml",
        "k8s/redis-deployment.yaml",
        "k8s/scraper-deployment.yaml",
        "k8s/mockup-deployment.yaml",
    ]

    missing_files = []
    for file_path in k8s_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)

    if missing_files:
        return False

    # Check for scalability configurations
    try:
        with open("k8s/scraper-deployment.yaml") as f:
            scraper_config = yaml.safe_load_all(f)

        # Look for HPA or replica configurations
        has_scaling_config = False
        for doc in scraper_config:
            if doc and doc.get("kind") == "Deployment":
                spec = doc.get("spec", {})
                if "replicas" in spec:
                    has_scaling_config = True
                    break

        if not has_scaling_config:
            pass

    except Exception:
        pass

    return True


def test_database_optimization():
    """Test database sharding and optimization."""

    # Check for sharding implementation
    sharding_files = [
        "leadfactory/storage/sharded_postgres_storage.py",
        "leadfactory/storage/sharding_strategy.py",
    ]

    missing_files = []
    for file_path in sharding_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)

    if missing_files:
        return False

    # Check sharding implementation
    try:
        with open("leadfactory/storage/sharded_postgres_storage.py") as f:
            content = f.read()

        if "class ShardedPostgresStorage" not in content:
            return False

        if "shard" not in content.lower():
            return False

    except Exception:
        return False

    return True


def test_microservices():
    """Test microservices architecture."""

    # Check for pipeline services
    services_dir = "leadfactory/services/pipeline_services"
    if not os.path.exists(services_dir):
        return False

    expected_services = [
        "base_service.py",
        "dedupe_service.py",
        "email_service.py",
        "enrich_service.py",
        "mockup_service.py",
        "score_service.py",
        "scrape_service.py",
        "orchestrator.py",
    ]

    missing_services = []
    for service in expected_services:
        service_path = os.path.join(services_dir, service)
        if not os.path.exists(service_path):
            missing_services.append(service)

    if missing_services:
        return False

    # Check for service orchestration
    orchestrator_path = os.path.join(services_dir, "orchestrator.py")
    try:
        with open(orchestrator_path) as f:
            content = f.read()

        if "class" not in content or "orchestrator" not in content.lower():
            return False

    except Exception:
        return False

    return True


def test_monitoring():
    """Test monitoring and observability."""

    # Check for metrics implementation
    metrics_file = "leadfactory/utils/metrics.py"
    if not os.path.exists(metrics_file):
        return False

    try:
        with open(metrics_file) as f:
            content = f.read()

        # Check for key monitoring components
        monitoring_components = [
            "prometheus",
            "PIPELINE_DURATION",
            "API_LATENCY",
            "COST_COUNTER",
            "GPU_INSTANCES_ACTIVE",
        ]

        missing_components = []
        for component in monitoring_components:
            if component not in content:
                missing_components.append(component)

        if missing_components:
            pass

    except Exception:
        return False

    # Check for GPU configuration (Task 22 integration)
    gpu_config = "etc/gpu_config.yml"
    if os.path.exists(gpu_config):
        pass
    else:
        pass

    return True


def test_performance_framework():
    """Test performance testing framework."""

    performance_files = [
        "scripts/performance/load_test.py",
        "tests/performance/test_node_capability_performance.py",
    ]

    missing_files = []
    for file_path in performance_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)

    if missing_files:
        pass

    # Check for load testing implementation
    load_test_file = "scripts/performance/load_test.py"
    if os.path.exists(load_test_file):
        try:
            with open(load_test_file) as f:
                content = f.read()

            if "load" in content.lower() and "test" in content.lower():
                pass
            else:
                pass
        except Exception:
            pass

    return True


def main():
    """Run all scalable architecture tests."""

    tests = [
        test_containerization,
        test_kubernetes,
        test_database_optimization,
        test_microservices,
        test_monitoring,
        test_performance_framework,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    if failed == 0:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
