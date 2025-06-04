# Email Service Dockerfile
# Lightweight service for email queue processing

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
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder stage
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY leadfactory/ leadfactory/
COPY templates/ templates/
COPY setup.py .
COPY pyproject.toml .

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PATH=/home/appuser/.local/bin:$PATH
ENV WORKER_TYPE=email
ENV SERVICE_NAME=email-service

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8085/health || exit 1

# Switch to non-root user
USER appuser

# Expose service port
EXPOSE 8085

# Default command
CMD ["python", "-m", "leadfactory.pipeline.email_queue", "--service-mode"]
