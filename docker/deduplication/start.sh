#!/bin/bash
set -e

# Start Ollama in the background
ollama serve &
OLLAMA_PID=$!

# Wait for Ollama to be ready
echo "Waiting for Ollama to start..."
sleep 10

# Pull the required model
echo "Pulling Llama3 8B model..."
ollama pull llama3:8b

# Start the deduplication service
echo "Starting deduplication service..."
exec python -m leadfactory.pipeline.dedupe --service-mode
