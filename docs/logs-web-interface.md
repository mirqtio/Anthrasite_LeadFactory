# Logs Web Interface Documentation

## Overview

The Logs Web Interface provides a comprehensive solution for browsing, searching, filtering, and exporting HTML and LLM logs stored in the LeadFactory database. The implementation consists of a RESTful API backend and modern web frontend with advanced analytics capabilities.

## Features

### Core Functionality
- **Log Browsing**: View and navigate through HTML and LLM logs with pagination
- **Advanced Filtering**: Filter by business ID, log type, date range, and content search
- **Real-time Search**: Full-text search across log content with highlighting
- **Export Capabilities**: Export logs in CSV, JSON, and Excel formats
- **Performance Optimization**: In-memory caching and streaming exports for large datasets

### Analytics Dashboard
- **Interactive Charts**: Log distribution by type and activity timeline
- **Statistics Overview**: Total logs, business metrics, and storage insights
- **Business Activity**: Top active businesses with log counts and trends
- **Real-time Metrics**: Cache performance and system statistics

## Architecture

### Backend API (`leadfactory/api/logs_api.py`)
- RESTful API endpoints built with Flask
- Comprehensive filtering and pagination support
- Multiple export formats with streaming capabilities
- In-memory caching layer for performance optimization
- Integration with existing storage interface

### Frontend Interface
- **Main Browser** (`leadfactory/static/logs.html`): Primary log browsing interface
- **Analytics Dashboard** (`leadfactory/static/dashboard.html`): Advanced analytics and visualizations
- Modern responsive design with mobile support
- Real-time updates and interactive charts

### Caching Layer (`leadfactory/api/cache.py`)
- In-memory cache with TTL and LRU eviction
- Query result caching with intelligent cache keys
- Cache hit/miss tracking and performance metrics
- Cache management endpoints for monitoring and clearing

## API Endpoints

### Log Retrieval
- `GET /api/logs` - Get logs with filtering and pagination
- `GET /api/logs/{id}` - Get detailed log entry
- `POST /api/logs/search` - Advanced search with filters
- `GET /api/logs/stats` - Get log statistics
- `GET /api/logs/types` - Get available log types

### Export Functionality
- `POST /api/logs/export` - Export logs in various formats
- `POST /api/logs/export/stream` - Stream large exports

### Management
- `GET /api/businesses` - Get businesses with logs
- `GET /api/cache/stats` - Get cache performance metrics
- `POST /api/cache/clear` - Clear application cache
- `GET /api/health` - Health check endpoint

## Installation and Setup

### Prerequisites
- Python 3.8+
- Flask and required dependencies
- PostgreSQL database with log tables
- Optional: pandas and openpyxl for Excel export

### Database Schema
The interface expects the following tables:
- `llm_logs`: LLM interaction logs
- `raw_html_storage`: HTML storage records
- `businesses`: Business information

### Running the Application

1. **Install Dependencies**:
   ```bash
   pip install flask flask-cors psycopg2
   # Optional for Excel export:
   pip install pandas openpyxl
   ```

2. **Configure Environment**:
   ```bash
   export LOGS_HOST=0.0.0.0
   export LOGS_PORT=5000
   export LOGS_DEBUG=False
   ```

3. **Start the Application**:
   ```bash
   python run_logs_app.py
   ```

4. **Access the Interface**:
   - Web Interface: `http://localhost:5000/logs`
   - Analytics Dashboard: `http://localhost:5000/dashboard`
   - API Health: `http://localhost:5000/api/health`

## Usage Guide

### Basic Log Browsing
1. Navigate to `/logs` to access the main interface
2. Use the sidebar to filter by log type (All, HTML, LLM, etc.)
3. Apply additional filters using the filter panel
4. View log details by clicking the "View" button

### Advanced Search
1. Enter search terms in the search box
2. Combine with filters for precise results
3. Use the advanced search modal for complex queries
4. Results are highlighted for easy identification

### Data Export
1. Configure your filters and search criteria
2. Click the "Export" button in the toolbar
3. Choose format (CSV, JSON, Excel)
4. Select whether to include full content
5. For large datasets, use streaming export

### Analytics Dashboard
1. Navigate to `/dashboard` for comprehensive analytics
2. Adjust time range and business filters
3. View interactive charts and metrics
4. Monitor top active businesses and trends

## Performance Optimization

### Caching Strategy
- Query results cached for 5 minutes (configurable)
- Statistics cached for 10 minutes
- Business lists cached for 15 minutes
- Search results cached for 1 minute
- Automatic cache cleanup and LRU eviction

### Large Dataset Handling
- Pagination for efficient data loading
- Streaming exports for large datasets
- Virtualized lists for frontend performance
- Optimized database queries with proper indexing

### Monitoring
- Cache hit/miss ratios available via API
- Performance metrics in dashboard
- Real-time statistics updates
- Error logging and debugging

## Configuration

### Cache Settings
```python
# In leadfactory/api/cache.py
cache = LogsAPICache(
    max_entries=1000,      # Maximum cache entries
    default_ttl=300        # Default TTL in seconds
)
```

### API Limits
- Maximum export limit: 10,000 records
- Streaming chunk size: 1,000-5,000 records
- Search query timeout: 30 seconds
- Pagination limit: 1,000 records per page

## Security Considerations

### Data Protection
- No sensitive data logged in application logs
- Secure export file generation
- Proper SQL injection prevention
- Input validation and sanitization

### Access Control
- Ready for authentication integration
- CORS configured for cross-origin requests
- Rate limiting considerations for production
- Secure file download mechanisms

## Troubleshooting

### Common Issues
1. **Cache Performance**: Monitor cache hit rates via `/api/cache/stats`
2. **Large Exports**: Use streaming endpoints for datasets > 1000 records
3. **Database Performance**: Ensure proper indexing on timestamp and business_id
4. **Memory Usage**: Configure appropriate cache limits

### Error Handling
- Comprehensive error logging
- User-friendly error messages
- Graceful degradation for missing features
- Automatic retry mechanisms for transient failures

## Future Enhancements

### Planned Features
- Real-time log streaming with WebSockets
- Advanced analytics with machine learning insights
- User authentication and role-based access
- Automated report generation and scheduling
- Integration with external monitoring systems

### Performance Improvements
- Database query optimization
- Client-side virtualization for large datasets
- Progressive data loading
- Enhanced caching strategies

## Support and Maintenance

### Monitoring
- Monitor cache performance regularly
- Track export usage patterns
- Review database query performance
- Monitor system resource usage

### Updates
- Regular dependency updates
- Security patch management
- Feature enhancement deployments
- Database schema migrations

For additional support or feature requests, please refer to the project documentation or contact the development team.
