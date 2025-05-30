# Velocity Tracking API Documentation

## Overview

The Velocity Tracking API provides programmatic access to velocity calculations, metrics, and visualizations. This document covers all public APIs and integration points.

## Core Classes

### VelocityCalculator

Core calculation engine for velocity metrics.

#### Constructor
```javascript
const calculator = new VelocityCalculator();
```

#### Methods

##### `calculateTaskDuration(startTime, endTime)`
Calculate the duration of a task in hours.

**Parameters:**
- `startTime` (Date|string): Task start time
- `endTime` (Date|string): Task end time

**Returns:** `number` - Duration in hours

**Example:**
```javascript
const hours = calculator.calculateTaskDuration(
  '2024-01-01T09:00:00Z',
  '2024-01-01T17:00:00Z'
);
// Returns: 8
```

##### `calculateVelocityRate(velocityPoints, actualHours)`
Calculate velocity rate (points per hour).

**Parameters:**
- `velocityPoints` (number): Task complexity points
- `actualHours` (number): Actual time spent

**Returns:** `number` - Velocity rate (points/hour)

**Example:**
```javascript
const rate = calculator.calculateVelocityRate(8, 4);
// Returns: 2.0
```

##### `calculateDailyVelocity(tasks, workingDays)`
Calculate daily velocity from completed tasks.

**Parameters:**
- `tasks` (Array): Array of completed tasks
- `workingDays` (number): Number of working days

**Returns:** `number` - Daily velocity (points/day)

**Example:**
```javascript
const daily = calculator.calculateDailyVelocity(completedTasks, 5);
// Returns: 5.2
```

##### `calculateETC(remainingTasks, dailyVelocity)`
Calculate estimated time to completion.

**Parameters:**
- `remainingTasks` (Array): Array of remaining tasks
- `dailyVelocity` (number): Current daily velocity

**Returns:** `Object` - ETC details
```javascript
{
  totalComplexity: 45,
  estimatedDays: 8.7,
  estimatedHours: 69.6,
  completionDate: Date
}
```

##### `updateVelocityMetadata(task, oldStatus, newStatus)`
Update task velocity metadata on status change.

**Parameters:**
- `task` (Object): Task object
- `oldStatus` (string): Previous status
- `newStatus` (string): New status

**Returns:** `Object` - Updated task with velocity metadata

---

### VelocityService

High-level service for velocity operations.

#### Constructor
```javascript
const service = new VelocityService(tasksFilePath);
```

**Parameters:**
- `tasksFilePath` (string): Path to tasks.json file

#### Methods

##### `loadTasks()`
Load tasks from file.

**Returns:** `Promise<Array>` - Array of tasks

##### `getVelocityMetrics(options)`
Get comprehensive velocity metrics.

**Parameters:**
- `options` (Object): Calculation options
  - `days` (number): Number of days to analyze
  - `period` (string): Period type ('day', 'week', 'month')
  - `includeSubtasks` (boolean): Include subtasks in calculations

**Returns:** `Promise<Object>` - Velocity metrics
```javascript
{
  velocity: {
    daily: 5.2,
    weekly: 26.0,
    monthly: 104.0
  },
  completed: {
    count: 12,
    totalComplexity: 89
  },
  cycleTime: {
    average: 4.5,
    median: 3.8,
    min: 1.2,
    max: 12.0
  },
  workInProgress: {
    count: 3,
    totalComplexity: 21
  },
  estimates: {
    totalComplexity: 156,
    estimatedDays: 12.5,
    completionDate: Date
  }
}
```

##### `getVelocityTrend(weeks)`
Get velocity trend over time.

**Parameters:**
- `weeks` (number): Number of weeks to analyze

**Returns:** `Promise<Array>` - Trend data points
```javascript
[
  { period: 'Week 1', velocity: 4.8, date: Date },
  { period: 'Week 2', velocity: 5.2, date: Date },
  // ...
]
```

##### `updateTaskStatus(taskId, newStatus)`
Update task status and recalculate velocity.

**Parameters:**
- `taskId` (number): Task ID
- `newStatus` (string): New status

**Returns:** `Promise<Object>` - Updated task

---

### VelocityVisualizer

Visualization and chart generation.

#### Constructor
```javascript
const visualizer = new VelocityVisualizer(preferences);
```

**Parameters:**
- `preferences` (Object): Display preferences

#### Methods

##### `createVelocityDashboard(metrics, trend)`
Create comprehensive velocity dashboard.

**Parameters:**
- `metrics` (Object): Velocity metrics
- `trend` (Array): Trend data

**Returns:** `string` - Formatted dashboard

##### `createVelocityChart(data, options)`
Create velocity trend chart.

**Parameters:**
- `data` (Array): Chart data points
- `options` (Object): Chart options
  - `height` (number): Chart height
  - `width` (number): Chart width
  - `title` (string): Chart title

**Returns:** `string` - ASCII chart

##### `createProgressBar(current, total, options)`
Create progress bar visualization.

**Parameters:**
- `current` (number): Current value
- `total` (number): Total value
- `options` (Object): Progress bar options
  - `width` (number): Bar width
  - `showPercentage` (boolean): Show percentage

**Returns:** `string` - Progress bar

**Example:**
```javascript
const bar = visualizer.createProgressBar(75, 100, { width: 30 });
// Returns: "[██████████████████████░░░░░░] 75.0%"
```

##### `createTable(data, columns)`
Create formatted table.

**Parameters:**
- `data` (Array): Table data
- `columns` (Array): Column definitions

**Returns:** `string` - Formatted table

---

### VelocityPreferences

User preferences management.

#### Constructor
```javascript
const preferences = new VelocityPreferences(configPath);
```

**Parameters:**
- `configPath` (string): Path to config file (optional)

#### Methods

##### `load()`
Load preferences from file.

**Returns:** `Promise<Object>` - User preferences

##### `save(preferences)`
Save preferences to file.

**Parameters:**
- `preferences` (Object): Preferences to save

**Returns:** `Promise<void>`

##### `get(key)`
Get preference value.

**Parameters:**
- `key` (string): Preference key (dot notation supported)

**Returns:** `Promise<any>` - Preference value

**Example:**
```javascript
const useColors = await preferences.get('display.useColors');
const workingHours = await preferences.get('calculation.workingHoursPerDay');
```

##### `set(key, value)`
Set preference value.

**Parameters:**
- `key` (string): Preference key
- `value` (any): Preference value

**Returns:** `Promise<void>`

##### `reset(sections)`
Reset preferences to defaults.

**Parameters:**
- `sections` (Array): Sections to reset (optional, resets all if not provided)

**Returns:** `Promise<void>`

##### `validate(preferences)`
Validate preferences object.

**Parameters:**
- `preferences` (Object): Preferences to validate

**Returns:** `Object` - Validation result
```javascript
{
  valid: true,
  errors: []
}
```

---

### VelocityIntegration

Integration with task management workflow.

#### Constructor
```javascript
const integration = new VelocityIntegration(tasksFilePath);
```

#### Methods

##### `onTaskStatusChange(taskId, oldStatus, newStatus)`
Handle task status change event.

**Parameters:**
- `taskId` (number): Task ID
- `oldStatus` (string): Previous status
- `newStatus` (string): New status

**Returns:** `Promise<Object>` - Updated task

##### `estimateComplexity(task)`
Estimate task complexity automatically.

**Parameters:**
- `task` (Object): Task object

**Returns:** `number` - Estimated complexity score

##### `enhanceTasksWithVelocity(tasks)`
Add velocity metadata to tasks.

**Parameters:**
- `tasks` (Array): Array of tasks

**Returns:** `Promise<Array>` - Enhanced tasks

##### `generateVelocitySummary(options)`
Generate velocity summary report.

**Parameters:**
- `options` (Object): Summary options
  - `period` (string): Time period
  - `includeCharts` (boolean): Include charts

**Returns:** `Promise<string>` - Summary report

#### Events

The integration class extends EventEmitter and emits the following events:

##### `velocityUpdate`
Emitted when task velocity is updated.

**Payload:**
```javascript
{
  taskId: 1,
  metrics: {
    complexity: 8,
    actualHours: 6.5,
    velocityRate: 1.23
  }
}
```

##### `taskCompleted`
Emitted when task is completed.

**Payload:**
```javascript
{
  taskId: 1,
  stats: {
    complexity: 8,
    actualTime: 6.5,
    velocityRate: 1.23
  }
}
```

**Example:**
```javascript
integration.on('velocityUpdate', (data) => {
  console.log(`Task ${data.taskId} velocity updated:`, data.metrics);
});
```

---

## Data Structures

### Task with Velocity Metadata

```javascript
{
  "id": 1,
  "title": "Implement feature X",
  "status": "done",
  "velocity_metadata": {
    "complexity_score": 8,
    "estimated_hours": 6,
    "actual_hours": 7.5,
    "velocity_points": 8,
    "blocked_time": 0.5,
    "velocity_rate": 1.07,
    "status_history": [
      {
        "status": "pending",
        "timestamp": "2024-01-01T10:00:00Z",
        "duration_hours": null
      },
      {
        "status": "in-progress",
        "timestamp": "2024-01-01T11:00:00Z",
        "duration_hours": 1
      },
      {
        "status": "done",
        "timestamp": "2024-01-01T18:30:00Z",
        "duration_hours": 7.5
      }
    ]
  }
}
```

### Velocity Metrics

```javascript
{
  "velocity": {
    "daily": 5.2,
    "weekly": 26.0,
    "monthly": 104.0
  },
  "completed": {
    "count": 12,
    "totalComplexity": 89,
    "averageComplexity": 7.4
  },
  "cycleTime": {
    "average": 4.5,
    "median": 3.8,
    "min": 1.2,
    "max": 12.0,
    "standardDeviation": 2.1
  },
  "workInProgress": {
    "count": 3,
    "totalComplexity": 21
  },
  "progress": {
    "completion": 0.75,
    "complexity": 0.68
  },
  "estimates": {
    "totalComplexity": 156,
    "estimatedDays": 12.5,
    "estimatedHours": 100,
    "completionDate": "2024-02-15T17:00:00Z"
  },
  "trend": {
    "direction": "up",
    "change": 0.15,
    "confidence": "high"
  }
}
```

### Preferences Schema

```javascript
{
  "display": {
    "showVelocityInList": true,
    "showTrendIndicators": true,
    "showEstimatedCompletion": true,
    "defaultChartType": "velocity",
    "chartHeight": 10,
    "useColors": true,
    "compactMode": false
  },
  "calculation": {
    "workingHoursPerDay": 8,
    "workingDaysPerWeek": 5,
    "excludeWeekends": true,
    "excludeHolidays": false,
    "velocityPeriod": "week",
    "trendAnalysisPeriod": 4,
    "complexityScale": "fibonacci",
    "autoEstimateComplexity": true
  },
  "tracking": {
    "trackBlockedTime": true,
    "trackSubtasks": true,
    "minimumTaskDuration": 0.1,
    "autoUpdateMetrics": true
  }
}
```

## Error Handling

All API methods use standard JavaScript error handling patterns:

```javascript
try {
  const metrics = await service.getVelocityMetrics({ days: 7 });
  console.log(metrics);
} catch (error) {
  console.error('Failed to get velocity metrics:', error.message);
}
```

Common error types:
- `FileNotFoundError`: Tasks file not found
- `ValidationError`: Invalid preferences or data
- `CalculationError`: Error in velocity calculations
- `ConfigurationError`: Invalid configuration

## Integration Examples

### Basic Integration

```javascript
const VelocityIntegration = require('./src/velocity/integration');

const integration = new VelocityIntegration();

// Handle task completion
async function completeTask(taskId) {
  await integration.onTaskStatusChange(taskId, 'in-progress', 'done');

  const summary = await integration.generateVelocitySummary();
  console.log(summary);
}
```

### Custom Metrics Dashboard

```javascript
const VelocityService = require('./src/velocity/service');
const VelocityVisualizer = require('./src/velocity/visualizer');

async function createCustomDashboard() {
  const service = new VelocityService();
  const visualizer = new VelocityVisualizer();

  const metrics = await service.getVelocityMetrics({ days: 14 });
  const trend = await service.getVelocityTrend(6);

  const dashboard = visualizer.createVelocityDashboard(metrics, trend);

  // Add custom sections
  const customReport = `
${dashboard}

🎯 Custom Analysis
────────────────────────────────────────
Team Performance: ${metrics.velocity.daily > 5 ? 'Excellent' : 'Good'}
Cycle Time Trend: ${trend[trend.length-1].velocity > trend[0].velocity ? 'Improving' : 'Declining'}
Capacity Utilization: ${(metrics.workInProgress.count / 10 * 100).toFixed(1)}%
  `;

  return customReport;
}
```

### Automated Reporting

```javascript
const cron = require('node-cron');

// Generate weekly velocity report
cron.schedule('0 9 * * 1', async () => {
  const integration = new VelocityIntegration();
  const report = await integration.generateVelocitySummary({
    period: 'week',
    includeCharts: true
  });

  // Send report via email, Slack, etc.
  await sendReport(report);
});
```

## Testing

### Unit Tests

```javascript
const VelocityCalculator = require('./src/velocity/calculator');

describe('VelocityCalculator', () => {
  const calculator = new VelocityCalculator();

  test('calculates task duration correctly', () => {
    const duration = calculator.calculateTaskDuration(
      '2024-01-01T09:00:00Z',
      '2024-01-01T17:00:00Z'
    );
    expect(duration).toBe(8);
  });

  test('calculates velocity rate correctly', () => {
    const rate = calculator.calculateVelocityRate(8, 4);
    expect(rate).toBe(2.0);
  });
});
```

### Integration Tests

```javascript
const VelocityIntegration = require('./src/velocity/integration');

describe('VelocityIntegration', () => {
  test('handles task status change', async () => {
    const integration = new VelocityIntegration();

    const result = await integration.onTaskStatusChange(1, 'pending', 'in-progress');

    expect(result.velocity_metadata).toBeDefined();
    expect(result.velocity_metadata.status_history).toHaveLength(2);
  });
});
```

## Performance Considerations

### Large Datasets

For projects with many tasks (>1000), consider:

1. **Pagination**: Limit date ranges for metrics calculations
2. **Caching**: Cache frequently accessed metrics
3. **Indexing**: Use task status and date indexing
4. **Batch Operations**: Process multiple tasks together

### Memory Usage

The velocity system is designed to be memory-efficient:

- Lazy loading of task data
- Streaming calculations for large datasets
- Minimal memory footprint for visualizations

### Optimization Tips

```javascript
// Use specific date ranges
const metrics = await service.getVelocityMetrics({ days: 7 });

// Cache preferences
const preferences = await VelocityPreferences.load();
const visualizer = new VelocityVisualizer(preferences);

// Batch task updates
const tasks = await service.loadTasks();
const enhanced = await integration.enhanceTasksWithVelocity(tasks);
```

---

For more examples and advanced usage patterns, see the [velocity tracking guide](velocity-tracking-guide.md).
