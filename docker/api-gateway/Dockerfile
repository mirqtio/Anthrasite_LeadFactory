# API Gateway Dockerfile
# NGINX-based API gateway with rate limiting

FROM nginx:alpine

# Install curl for health checks
RUN apk add --no-cache curl

# Copy nginx configuration
COPY docker/api-gateway/nginx.conf /etc/nginx/nginx.conf
COPY docker/api-gateway/default.conf /etc/nginx/conf.d/default.conf

# Create nginx cache directory
RUN mkdir -p /var/cache/nginx/rate_limit

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:80/health || exit 1

# Expose port
EXPOSE 80

# Default command
CMD ["nginx", "-g", "daemon off;"]
