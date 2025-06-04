# Deduplication Service Dockerfile
# Multi-stage build with Ollama integration

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

# Production stage with Ollama
FROM python:3.10-slim as production

# Create app user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Install runtime dependencies including Ollama
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.ai/install.sh | sh

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
ENV WORKER_TYPE=deduplication
ENV SERVICE_NAME=deduplication-service
ENV OLLAMA_HOST=0.0.0.0:11434

# Health check
HEALTHCHECK --interval=30s --timeout=15s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8082/health || exit 1

# Create ollama data directory
RUN mkdir -p /home/appuser/.ollama && chown -R appuser:appuser /home/appuser/.ollama

# Switch to non-root user
USER appuser

# Expose service ports
EXPOSE 8082 11434

# Start script to initialize Ollama and run service
COPY docker/deduplication/start.sh /start.sh
USER root
RUN chmod +x /start.sh
USER appuser

# Default command
CMD ["/start.sh"]
