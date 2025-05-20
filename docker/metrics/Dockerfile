FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements-metrics.txt .
RUN pip install --no-cache-dir -r requirements-metrics.txt

# Copy the application code
COPY . .

# Expose the metrics port
EXPOSE 8000

# Set environment variables
ENV PYTHONPATH=/app
ENV LOG_LEVEL=info
ENV ENVIRONMENT=production

# Run the metrics server
CMD ["uvicorn", "utils.metrics:app", "--host", "0.0.0.0", "--port", "8000"]
