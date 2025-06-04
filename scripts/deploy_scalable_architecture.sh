#!/bin/bash
set -e

# Deployment script for LeadFactory Scalable Architecture
# Usage: ./scripts/deploy_scalable_architecture.sh [environment]

ENVIRONMENT=${1:-development}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🚀 Deploying LeadFactory Scalable Architecture for $ENVIRONMENT environment"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is required but not installed"
        exit 1
    fi

    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is required but not installed"
        exit 1
    fi

    # Check Kubernetes (for production)
    if [[ "$ENVIRONMENT" == "production" ]]; then
        if ! command -v kubectl &> /dev/null; then
            log_error "kubectl is required for production deployment"
            exit 1
        fi

        if ! command -v helm &> /dev/null; then
            log_warning "Helm is recommended for production deployment"
        fi
    fi

    log_success "Prerequisites check passed"
}

# Build Docker images
build_images() {
    log_info "Building Docker images..."

    cd "$PROJECT_ROOT"

    # Build base image first
    docker build -t leadfactory/base:latest -f Dockerfile .

    # Build service-specific images
    services=("scraper" "enrichment" "deduplication" "scoring" "mockup" "email" "api-gateway")

    for service in "${services[@]}"; do
        log_info "Building $service image..."
        docker build -t "leadfactory/$service:latest" -f "docker/$service/Dockerfile" .
        log_success "$service image built"
    done
}

# Deploy with Docker Compose (development/staging)
deploy_docker_compose() {
    log_info "Deploying with Docker Compose..."

    cd "$PROJECT_ROOT"

    # Copy environment-specific configuration
    if [[ "$ENVIRONMENT" == "staging" ]]; then
        cp .env.staging .env
    else
        cp .env.example .env
    fi

    # Stop existing services
    docker-compose -f docker-compose.scalable.yml down -v || true

    # Start infrastructure services first
    log_info "Starting infrastructure services..."
    docker-compose -f docker-compose.scalable.yml up -d postgres redis zookeeper kafka

    # Wait for infrastructure to be ready
    sleep 30

    # Start application services
    log_info "Starting application services..."
    docker-compose -f docker-compose.scalable.yml up -d \
        scraper-service enrichment-service deduplication-service \
        scoring-service mockup-service email-service

    # Start API gateway and monitoring
    log_info "Starting API gateway and monitoring..."
    docker-compose -f docker-compose.scalable.yml up -d \
        api-gateway prometheus grafana jaeger

    log_success "Docker Compose deployment completed"
}

# Deploy to Kubernetes (production)
deploy_kubernetes() {
    log_info "Deploying to Kubernetes..."

    cd "$PROJECT_ROOT"

    # Create namespace
    kubectl apply -f k8s/namespace.yaml

    # Apply configuration and secrets
    kubectl apply -f k8s/configmap.yaml
    kubectl apply -f k8s/secrets.yaml

    # Deploy infrastructure
    log_info "Deploying infrastructure components..."
    kubectl apply -f k8s/postgres-deployment.yaml
    kubectl apply -f k8s/redis-deployment.yaml

    # Wait for infrastructure to be ready
    kubectl wait --for=condition=ready pod -l app=postgres -n leadfactory --timeout=300s
    kubectl wait --for=condition=ready pod -l app=redis -n leadfactory --timeout=300s

    # Deploy application services
    log_info "Deploying application services..."
    kubectl apply -f k8s/scraper-deployment.yaml
    kubectl apply -f k8s/mockup-deployment.yaml

    # Wait for services to be ready
    kubectl wait --for=condition=ready pod -l app=scraper-service -n leadfactory --timeout=300s
    kubectl wait --for=condition=ready pod -l app=mockup-service -n leadfactory --timeout=300s

    log_success "Kubernetes deployment completed"
}

# Run health checks
run_health_checks() {
    log_info "Running health checks..."

    if [[ "$ENVIRONMENT" == "production" ]]; then
        # Kubernetes health checks
        kubectl get pods -n leadfactory
        kubectl get services -n leadfactory
    else
        # Docker Compose health checks
        docker-compose -f docker-compose.scalable.yml ps

        # Check service endpoints
        sleep 10

        endpoints=(
            "http://localhost:80/health"
            "http://localhost:80/api/scrape/health"
            "http://localhost:80/api/score/health"
        )

        for endpoint in "${endpoints[@]}"; do
            if curl -f "$endpoint" > /dev/null 2>&1; then
                log_success "Health check passed: $endpoint"
            else
                log_warning "Health check failed: $endpoint"
            fi
        done
    fi
}

# Run performance tests
run_performance_tests() {
    log_info "Running basic performance tests..."

    if [[ "$ENVIRONMENT" != "production" ]]; then
        # Wait for services to stabilize
        sleep 30

        # Run basic load test
        python3 scripts/performance/load_test.py \
            --rps 10 \
            --duration 2 \
            --users 5 \
            --output "performance_test_results.json"

        log_success "Performance tests completed"
    else
        log_info "Skipping performance tests in production environment"
    fi
}

# Setup monitoring
setup_monitoring() {
    log_info "Setting up monitoring..."

    if [[ "$ENVIRONMENT" == "production" ]]; then
        # Kubernetes monitoring setup
        log_info "Prometheus and Grafana should be configured via Helm charts"
    else
        # Docker Compose monitoring
        log_info "Monitoring services are available at:"
        log_info "- Prometheus: http://localhost:9090"
        log_info "- Grafana: http://localhost:3000 (admin/admin)"
        log_info "- Jaeger: http://localhost:16686"
    fi
}

# Cleanup function
cleanup() {
    if [[ "$ENVIRONMENT" != "production" ]]; then
        log_info "To stop all services, run:"
        log_info "docker-compose -f docker-compose.scalable.yml down -v"
    fi
}

# Main deployment flow
main() {
    log_info "Starting deployment for $ENVIRONMENT environment"

    check_prerequisites
    build_images

    if [[ "$ENVIRONMENT" == "production" ]]; then
        deploy_kubernetes
    else
        deploy_docker_compose
    fi

    run_health_checks
    setup_monitoring

    if [[ "$ENVIRONMENT" == "development" ]]; then
        run_performance_tests
    fi

    log_success "🎉 Deployment completed successfully!"

    if [[ "$ENVIRONMENT" != "production" ]]; then
        log_info "API Gateway available at: http://localhost:80"
        log_info "Monitoring dashboard at: http://localhost:3000"
    fi

    cleanup
}

# Trap Ctrl+C
trap 'log_error "Deployment interrupted"; exit 1' INT

# Run main function
main "$@"
