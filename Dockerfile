FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files
COPY requirements.txt .
COPY requirements-dev.txt .
COPY constraints.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt
RUN pip install --no-cache-dir -r requirements-dev.txt -c constraints.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/data /app/logs

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose ports for API and metrics
EXPOSE 8000
EXPOSE 9090

# Default command
CMD ["python", "-m", "bin.scrape"]
