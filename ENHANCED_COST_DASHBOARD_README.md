# Enhanced Cost Dashboard for LeadFactory

## Overview

The Enhanced Cost Dashboard is a comprehensive cost monitoring and analytics system for LeadFactory that provides real-time cost tracking, advanced analytics, forecasting, and optimization recommendations. It integrates seamlessly with existing LeadFactory infrastructure including SQLite databases, Prometheus metrics, and monitoring systems.

## Features

### 🚀 **Core Features**
- **Real-time Cost Monitoring**: WebSocket-based streaming of cost data
- **Advanced Analytics**: Trend analysis, seasonality detection, and anomaly identification
- **Predictive Forecasting**: AI-powered cost forecasting with confidence intervals
- **Optimization Recommendations**: Actionable cost reduction strategies
- **Multi-service Breakdown**: Detailed cost analysis by service, operation, and time period
- **Interactive Dashboard**: Modern, responsive web interface with real-time updates

### 📊 **Analytics Capabilities**
- **Trend Decomposition**: Separate trend, seasonal, and residual components
- **Volatility Analysis**: Cost stability and predictability metrics
- **Change Point Detection**: Identify significant shifts in cost patterns
- **Anomaly Detection**: Multiple statistical methods for outlier identification
- **ROI Analysis**: Revenue attribution and profitability calculations

### 🔧 **Integration Features**
- **Database Integration**: Connects to all LeadFactory SQLite databases
- **Prometheus Metrics**: Seamless integration with existing monitoring
- **API-First Design**: RESTful APIs for all functionality
- **Export Capabilities**: JSON and CSV export for reports and analysis
- **Health Monitoring**: Comprehensive system health checks

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                Enhanced Cost Dashboard System                    │
├─────────────────────────────────────────────────────────────────┤
│  Frontend Dashboard (Port 5002)                                │
│  ├── Real-time WebSocket Updates                               │
│  ├── Interactive Charts & Visualizations                       │
│  ├── Cost Optimization Recommendations                         │
│  └── Multi-format Export (JSON, CSV)                          │
├─────────────────────────────────────────────────────────────────┤
│  Cost Breakdown API (Port 5001)                               │
│  ├── Detailed Cost Analysis                                   │
│  ├── Service/Time Period Filtering                            │
│  ├── Real-time Streaming                                      │
│  └── Advanced Breakdown Views                                 │
├─────────────────────────────────────────────────────────────────┤
│  Analytics Engine                                             │
│  ├── Trend Analysis & Forecasting                            │
│  ├── Anomaly Detection                                        │
│  ├── Optimization Recommendations                             │
│  └── Statistical Analysis                                     │
├─────────────────────────────────────────────────────────────────┤
│  Integration Layer                                            │
│  ├── SQLite Database Connections                             │
│  ├── Prometheus Metrics Integration                           │
│  ├── Cost Tracker Integration                                │
│  └── Real-time Metric Streaming                              │
├─────────────────────────────────────────────────────────────────┤
│  Data Sources                                                 │
│  ├── Cost Tracking Database                                  │
│  ├── Purchase Metrics Database                               │
│  ├── Budget Configuration                                    │
│  └── Other LeadFactory Databases                            │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Installation & Dependencies

The enhanced cost dashboard is built into LeadFactory and uses existing dependencies. Ensure you have:

- Python 3.8+
- Flask & Flask-SocketIO
- SQLite3
- Prometheus client (optional but recommended)
- NumPy/SciPy for analytics (will gracefully degrade if not available)

### 2. Starting the Dashboard

```bash
# Start with default settings (recommended)
python run_enhanced_cost_dashboard.py

# Start with custom host/port
python run_enhanced_cost_dashboard.py --host 0.0.0.0 --port 5003

# Start in debug mode
python run_enhanced_cost_dashboard.py --debug

# Start without integration system (limited features)
python run_enhanced_cost_dashboard.py --no-integration
```

### 3. Accessing the Dashboard

Once started, access the dashboard at:
- **Main Dashboard**: http://127.0.0.1:5002
- **API Documentation**: http://127.0.0.1:5002/api/enhanced/health

## API Reference

### Enhanced Dashboard Endpoints

#### `GET /api/enhanced/dashboard-data`
Get comprehensive dashboard data with filtering options.

**Parameters:**
- `time_period` (string): hourly, daily, weekly, monthly
- `service_filter` (string): Filter by specific service
- `start_date` (string): Start date (YYYY-MM-DD)
- `end_date` (string): End date (YYYY-MM-DD)

**Example:**
```bash
curl "http://localhost:5002/api/enhanced/dashboard-data?time_period=daily&service_filter=openai"
```

#### `GET /api/enhanced/cost-trends`
Get advanced cost trend analysis and forecasting.

**Parameters:**
- `service_type` (string): Filter by service type
- `days_back` (integer): Historical data period (default: 90)
- `forecast_days` (integer): Forecast period (default: 30)

**Example:**
```bash
curl "http://localhost:5002/api/enhanced/cost-trends?service_type=openai&days_back=60&forecast_days=14"
```

#### `GET /api/enhanced/optimization-recommendations`
Get AI-powered cost optimization recommendations.

**Example Response:**
```json
{
  "total_recommendations": 5,
  "total_estimated_savings": 245.67,
  "recommendations": [
    {
      "type": "volatility_management",
      "priority": "high",
      "title": "Implement Cost Smoothing Strategies",
      "description": "Cost volatility is high (CV: 0.45)",
      "actions": [
        "Implement request batching to reduce transaction frequency",
        "Use cost averaging strategies for API calls"
      ],
      "estimated_savings": 150.00,
      "impact": "Reduce cost unpredictability and enable better budgeting"
    }
  ]
}
```

#### `GET /api/enhanced/cost-efficiency`
Get cost efficiency metrics and optimization scores.

#### `GET /api/enhanced/detailed-breakdown`
Get detailed cost breakdown with advanced filtering.

**Parameters:**
- `service_type`, `time_period`, `operation_type`
- `start_date`, `end_date`, `group_by[]`
- `min_cost`, `max_cost` (float): Cost range filters
- `sort_by`, `sort_order`: Sorting options

#### `GET /api/enhanced/export/{format}`
Export comprehensive cost data.

**Formats:** `json`, `csv`

**Parameters:**
- `export_type`: dashboard, trends, recommendations
- `time_period`: daily, weekly, monthly
- `include_trends` (boolean): Include trend analysis
- `include_recommendations` (boolean): Include optimization recommendations

### Cost Breakdown API Endpoints

#### `GET /api/cost/breakdown`
Detailed cost breakdown with comprehensive filtering.

#### `GET /api/cost/trends`
Cost trend analysis and predictions.

#### `GET /api/cost/optimization`
Cost optimization recommendations.

#### `GET /api/cost/budget-utilization`
Budget utilization analysis and forecasting.

#### `GET /api/cost/roi-analysis`
ROI calculations and analysis.

### WebSocket Events

#### Real-time Updates
Connect to the WebSocket at the dashboard URL to receive real-time updates:

```javascript
const socket = io('http://localhost:5002');

socket.on('enhanced_initial_data', (data) => {
    console.log('Initial dashboard data:', data);
});

socket.on('integrated_cost_update', (data) => {
    console.log('Real-time cost update:', data);
});

// Subscribe to specific update types
socket.emit('subscribe_enhanced_updates', {
    types: ['dashboard', 'efficiency', 'alerts'],
    filters: { service_type: 'openai' }
});
```

## Configuration

### Environment Variables

```bash
# Database paths (auto-discovered if not set)
COST_TRACKING_DB_PATH=/path/to/cost_tracking.db
PURCHASE_METRICS_DB_PATH=/path/to/purchase_metrics.db

# Dashboard settings
FLASK_SECRET_KEY=your-secret-key-here
ENHANCED_DASHBOARD_HOST=127.0.0.1
ENHANCED_DASHBOARD_PORT=5002

# Integration settings
ENABLE_PROMETHEUS_METRICS=true
COST_SYNC_INTERVAL=60
ANALYTICS_CACHE_DURATION=300

# Cost tracking thresholds
BUDGET_GATE_THRESHOLD=1000.0
HIGH_COST_THRESHOLD=10.0
VOLATILITY_WARNING_THRESHOLD=0.3
```

### Database Configuration

The system automatically discovers and connects to LeadFactory databases:

- `cost_tracking.db` - Main cost tracking data
- `purchase_metrics.db` - Revenue and transaction data
- `budget_config.db` - Budget configuration
- `ab_tests.db` - A/B testing cost data
- Additional databases as discovered

## Analytics Deep Dive

### Trend Analysis

The analytics engine performs comprehensive trend analysis including:

1. **Trend Decomposition**: Separates time series into trend, seasonal, and residual components
2. **Seasonality Detection**: Identifies weekly and monthly patterns
3. **Volatility Analysis**: Measures cost stability and predictability
4. **Change Point Detection**: Finds significant shifts in cost patterns

### Forecasting

Advanced forecasting uses multiple methods:

1. **Linear Trend**: Simple linear regression forecasting
2. **Exponential Smoothing**: Weighted recent observations
3. **Moving Average**: Simple average-based forecasting
4. **Seasonal Naive**: Pattern-based forecasting for seasonal data
5. **Ensemble**: Weighted combination of all methods

### Anomaly Detection

Multiple statistical methods identify cost anomalies:

1. **Z-Score Method**: Statistical deviation from mean
2. **IQR Method**: Interquartile range outlier detection
3. **Moving Average**: Deviation from rolling averages
4. **Seasonal**: Anomalies in seasonal patterns

### Optimization Recommendations

AI-powered recommendations based on:

1. **Cost Volatility**: Smoothing strategies for unstable costs
2. **Growth Patterns**: Controls for rapid cost increases
3. **Anomaly Patterns**: Prevention strategies for outliers
4. **Service Efficiency**: Optimization for specific services
5. **Budget Utilization**: Planning and allocation improvements

## Monitoring & Health Checks

### System Health

Access comprehensive health checks at:
```
GET /api/enhanced/health
```

**Response includes:**
- Overall system status
- Database connectivity
- Integration system status
- Analytics engine health
- Prometheus metrics availability

### Logging

The system provides comprehensive logging:

```bash
# Log file location
enhanced_cost_dashboard.log

# Log levels
DEBUG: Detailed operation logs
INFO: General operation status
WARNING: Non-critical issues
ERROR: Critical errors requiring attention
```

### Alerts & Notifications

The dashboard generates intelligent alerts for:

- **Budget Overruns**: Approaching or exceeding budget limits
- **Cost Anomalies**: Unusual cost spikes or patterns
- **System Issues**: Integration or database problems
- **Optimization Opportunities**: Cost reduction recommendations

## Performance & Scalability

### Caching Strategy

- **Analytics Cache**: 10-minute TTL for trend analysis
- **Metrics Cache**: 5-minute TTL for dashboard data
- **Database Query Optimization**: Intelligent query caching

### Real-time Performance

- **WebSocket Updates**: 30-second intervals for real-time data
- **Background Processing**: Non-blocking analytics calculations
- **Progressive Loading**: Dashboard loads incrementally

### Resource Usage

- **Memory**: ~50-100MB typical usage
- **CPU**: Low impact background processing
- **Disk**: Minimal additional storage requirements
- **Network**: Efficient WebSocket communication

## Troubleshooting

### Common Issues

#### Dashboard Won't Start
```bash
# Check dependencies
pip install flask flask-socketio

# Check port availability
netstat -an | grep 5002

# Start with debug mode
python run_enhanced_cost_dashboard.py --debug
```

#### No Real-time Updates
```bash
# Check WebSocket connection in browser console
# Verify integration system is running
# Check firewall settings for WebSocket traffic
```

#### Missing Cost Data
```bash
# Verify cost tracker is active
python -c "from leadfactory.cost.cost_tracking import cost_tracker; print(cost_tracker.get_daily_cost())"

# Check database permissions
ls -la *.db

# Verify database schema
sqlite3 cost_tracking.db ".schema"
```

#### Analytics Not Working
```bash
# Check required dependencies
pip install numpy scipy

# Verify data availability
# Check analytics engine logs
```

### Debug Mode

Start in debug mode for detailed troubleshooting:

```bash
python run_enhanced_cost_dashboard.py --debug
```

Debug mode provides:
- Detailed request/response logging
- WebSocket connection debugging
- Analytics calculation tracing
- Database query logging

## Development & Customization

### Extending the Dashboard

#### Adding Custom Metrics

```python
# In leadfactory/api/cost_metrics_integration.py
def get_custom_metrics(self) -> Dict[str, Any]:
    return {
        "custom_metric": self._calculate_custom_metric(),
        "timestamp": datetime.now().isoformat()
    }
```

#### Creating Custom Analytics

```python
# In leadfactory/analytics/cost_analytics.py
def custom_analysis(self, data: List[float]) -> Dict[str, Any]:
    return {
        "custom_result": your_custom_calculation(data),
        "confidence": 0.95
    }
```

#### Adding New API Endpoints

```python
# In leadfactory/monitoring/enhanced_cost_dashboard.py
@self.app.route("/api/enhanced/custom-endpoint")
def api_custom_endpoint():
    return jsonify({"custom": "data"})
```

### Testing

```bash
# Run integration tests
python -m pytest tests/integration/test_enhanced_cost_dashboard.py

# Test API endpoints
curl -X GET "http://localhost:5002/api/enhanced/health"

# Test WebSocket connectivity
# Use browser dev tools or WebSocket testing tools
```

## Production Deployment

### WSGI Deployment

```python
# wsgi.py
from leadfactory.monitoring.enhanced_cost_dashboard import enhanced_dashboard

application = enhanced_dashboard.create_wsgi_app()

if __name__ == "__main__":
    application.run()
```

### Docker Deployment

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 5002

CMD ["python", "run_enhanced_cost_dashboard.py", "--host", "0.0.0.0"]
```

### Reverse Proxy Configuration

#### Nginx
```nginx
location /cost-dashboard/ {
    proxy_pass http://localhost:5002/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
}
```

### Security Considerations

- **Authentication**: Implement authentication middleware
- **HTTPS**: Use SSL/TLS in production
- **CORS**: Configure appropriate CORS policies
- **Rate Limiting**: Implement API rate limiting
- **Input Validation**: Validate all API inputs

## Support & Maintenance

### Regular Maintenance

1. **Database Optimization**: Periodic VACUUM operations
2. **Log Rotation**: Manage log file sizes
3. **Cache Cleanup**: Clear expired cache entries
4. **Health Monitoring**: Regular health check reviews

### Backup & Recovery

```bash
# Backup databases
cp *.db backup/

# Backup configuration
cp enhanced_cost_dashboard.log backup/
```

### Updates & Upgrades

The enhanced cost dashboard is designed to be backwards compatible with existing LeadFactory installations. Updates should be tested in a development environment before production deployment.

---

## License

This enhanced cost dashboard is part of the LeadFactory system and follows the same licensing terms.

## Contributing

For contributions, improvements, or bug reports, please follow the standard LeadFactory contribution guidelines.
