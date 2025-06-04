# Enrichment Service Dockerfile
# Multi-stage build for production optimization

# Build stage
FROM python:3.10-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and constraints
COPY requirements/requirements.txt requirements/
COPY requirements/requirements-dev.txt requirements/
COPY constraints.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements/requirements.txt -c constraints.txt

# Production stage
FROM python:3.10-slim as production

# Create app user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    chromium \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder stage
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY leadfactory/ leadfactory/
COPY setup.py .
COPY pyproject.toml .

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PATH=/home/appuser/.local/bin:$PATH
ENV WORKER_TYPE=enrichment
ENV SERVICE_NAME=enrichment-service
ENV CHROMIUM_PATH=/usr/bin/chromium

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8081/health || exit 1

# Switch to non-root user
USER appuser

# Expose service port
EXPOSE 8081

# Default command
CMD ["python", "-m", "leadfactory.pipeline.enrich", "--service-mode"]
