# Velocity Tracking System Guide

## Overview

The Velocity Tracking System is a comprehensive solution for monitoring and analyzing task completion velocity in the task-master CLI. It provides insights into team productivity, estimates completion times, and helps optimize workflow efficiency.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Core Concepts](#core-concepts)
3. [CLI Commands](#cli-commands)
4. [Configuration](#configuration)
5. [Data Model](#data-model)
6. [Integration](#integration)
7. [Visualization](#visualization)
8. [Troubleshooting](#troubleshooting)
9. [API Reference](#api-reference)

## Quick Start

### Installation

The velocity tracking system is built into task-master CLI. No additional installation is required.

### Basic Usage

```bash
# View velocity dashboard
task-master velocity dashboard

# Show velocity metrics
task-master velocity metrics

# Configure preferences
task-master velocity config list
```

### First Time Setup

1. **Migrate existing tasks** (if you have existing tasks):
   ```bash
   node src/velocity/migrate.js
   ```

2. **Set your preferences**:
   ```bash
   task-master velocity config set calculation.workingHoursPerDay 8
   task-master velocity config set display.useColors true
   ```

3. **View your dashboard**:
   ```bash
   task-master velocity dashboard
   ```

## Core Concepts

### Velocity Points

Velocity points represent the complexity or effort required for a task. They are automatically assigned based on:
- Task title complexity
- Description length and content
- Estimated hours (if provided)
- Historical data

### Cycle Time

The time from when a task starts (`in-progress`) to when it's completed (`done`). This includes:
- Active work time
- Blocked time (if any)
- Review time

### Daily Velocity

The average number of velocity points completed per working day. Calculated as:
```
Daily Velocity = Total Velocity Points / Working Days
```

### Estimated Time to Completion (ETC)

Projected completion time for remaining tasks based on current velocity:
```
ETC = Remaining Complexity / Daily Velocity
```

## CLI Commands

### Dashboard Commands

```bash
# Show comprehensive velocity dashboard
task-master velocity dashboard

# Show dashboard for specific period
task-master velocity dashboard --period=month
```

### Metrics Commands

```bash
# Show velocity metrics
task-master velocity metrics

# Show metrics for specific period
task-master velocity metrics --period=week --days=14

# Show trend analysis
task-master velocity trend --weeks=6
```

### Chart Commands

```bash
# Show velocity trend chart
task-master velocity chart --type=velocity

# Show burndown chart
task-master velocity chart --type=burndown

# Show cycle time distribution
task-master velocity chart --type=cycle-time
```

### Configuration Commands

```bash
# List all preferences
task-master velocity config list

# List specific section
task-master velocity config list --section=display

# Set a preference
task-master velocity config set display.chartHeight 15

# Get a preference value
task-master velocity config get calculation.velocityPeriod

# Reset preferences
task-master velocity config reset
task-master velocity config reset --sections=display,calculation
```

### Report Commands

```bash
# Generate velocity report
task-master velocity report

# Generate report for specific period
task-master velocity report --period=month

# Save report to file
task-master velocity report --output=velocity-report.txt
```

## Configuration

### Display Preferences

| Setting | Default | Description |
|---------|---------|-------------|
| `showVelocityInList` | `true` | Show velocity info in task lists |
| `showTrendIndicators` | `true` | Show trend arrows and indicators |
| `showEstimatedCompletion` | `true` | Show ETC in dashboard |
| `defaultChartType` | `"velocity"` | Default chart type for visualizations |
| `chartHeight` | `10` | Height of ASCII charts (5-50) |
| `useColors` | `true` | Use colors in output |
| `compactMode` | `false` | Use compact display format |

### Calculation Preferences

| Setting | Default | Description |
|---------|---------|-------------|
| `workingHoursPerDay` | `8` | Working hours per day (1-24) |
| `workingDaysPerWeek` | `5` | Working days per week (1-7) |
| `excludeWeekends` | `true` | Exclude weekends from calculations |
| `excludeHolidays` | `false` | Exclude holidays from calculations |
| `velocityPeriod` | `"week"` | Default period for velocity calculations |
| `trendAnalysisPeriod` | `4` | Number of periods for trend analysis |
| `complexityScale` | `"fibonacci"` | Complexity scale (fibonacci, linear, exponential) |
| `autoEstimateComplexity` | `true` | Auto-estimate task complexity |

### Tracking Preferences

| Setting | Default | Description |
|---------|---------|-------------|
| `trackBlockedTime` | `true` | Track time when tasks are blocked |
| `trackSubtasks` | `true` | Include subtasks in velocity calculations |
| `minimumTaskDuration` | `0.1` | Minimum task duration in hours |
| `autoUpdateMetrics` | `true` | Auto-update metrics on task changes |

### Example Configuration

```bash
# Set up for a team working 6-hour days, 4 days a week
task-master velocity config set calculation.workingHoursPerDay 6
task-master velocity config set calculation.workingDaysPerWeek 4

# Use monthly velocity tracking
task-master velocity config set calculation.velocityPeriod month

# Disable colors for CI/CD environments
task-master velocity config set display.useColors false

# Use compact mode for smaller terminals
task-master velocity config set display.compactMode true
```

## Data Model

### Task Velocity Metadata

Each task automatically gets velocity metadata:

```json
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

### Velocity Metrics Structure

```json
{
  "velocity": {
    "daily": 5.2,
    "weekly": 26.0,
    "monthly": 104.0
  },
  "completed": {
    "count": 12,
    "totalComplexity": 89
  },
  "cycleTime": {
    "average": 4.5,
    "median": 3.8,
    "min": 1.2,
    "max": 12.0
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
    "completionDate": "2024-02-15T17:00:00Z"
  }
}
```

## Integration

### Automatic Integration

The velocity system automatically integrates with existing task-master workflows:

1. **Task Status Changes**: Velocity metadata is updated when task status changes
2. **Task Creation**: New tasks get estimated complexity scores
3. **Task Completion**: Actual times and velocity rates are calculated
4. **List Commands**: Velocity info is shown in task lists (if enabled)

### Manual Integration

You can also integrate velocity tracking programmatically:

```javascript
const VelocityIntegration = require('./src/velocity/integration');

const integration = new VelocityIntegration();

// Handle task status change
await integration.onTaskStatusChange(taskId, 'in-progress', 'done');

// Get velocity summary
const summary = await integration.generateVelocitySummary();

// Enhance tasks with velocity data
const enhancedTasks = await integration.enhanceTasksWithVelocity(tasks);
```

### Hooks and Events

The system provides hooks for custom integrations:

```javascript
// Listen for velocity updates
integration.on('velocityUpdate', (taskId, metrics) => {
  console.log(`Task ${taskId} velocity updated:`, metrics);
});

// Listen for completion events
integration.on('taskCompleted', (taskId, stats) => {
  console.log(`Task ${taskId} completed:`, stats);
});
```

## Visualization

### Dashboard

The velocity dashboard provides a comprehensive overview:

```
🚀 Velocity Dashboard
════════════════════════════════════════════════════════════════════════════════

📊 Key Metrics
────────────────────────────────────────
Daily Velocity:    5.2 points/day
Tasks Completed:   12
Avg Cycle Time:    4.5 hours
Work in Progress:  3 tasks

📈 Progress Overview
────────────────────────────────────────
Completion: [████████████████████████░░░░░░] 75.0% (12/16)
Complexity: [██████████████████████░░░░░░░░░] 68.0% (89/131)

📈 Velocity Trend (Last 4 Weeks)
────────────────────────────────────────────────────────────
  8.0 │     █
  7.0 │   █ █
  6.0 │ █ █ █
  5.0 │ █ █ █ █
  4.0 │ █ █ █ █
  3.0 │ █ █ █ █
  2.0 │ █ █ █ █
  1.0 │ █ █ █ █
  0.0 │ █ █ █ █
      └─────────
       W W W W
```

### Charts

#### Velocity Trend Chart
Shows velocity over time with trend indicators.

#### Burndown Chart
Shows remaining work over time compared to ideal burndown.

#### Cycle Time Histogram
Shows distribution of task completion times.

### Customization

Charts can be customized through preferences:

```bash
# Adjust chart height
task-master velocity config set display.chartHeight 15

# Change default chart type
task-master velocity config set display.defaultChartType burndown

# Disable colors
task-master velocity config set display.useColors false
```

## Troubleshooting

### Common Issues

#### 1. No Velocity Data Showing

**Problem**: Dashboard shows "No velocity data available"

**Solutions**:
- Ensure tasks have been completed (status: 'done')
- Check if velocity metadata exists: `node src/velocity/migrate.js`
- Verify date range: `task-master velocity metrics --days=30`

#### 2. Incorrect Velocity Calculations

**Problem**: Velocity numbers seem wrong

**Solutions**:
- Check working hours setting: `task-master velocity config get calculation.workingHoursPerDay`
- Verify weekend exclusion: `task-master velocity config get calculation.excludeWeekends`
- Review task timestamps in velocity_metadata

#### 3. Charts Not Displaying Properly

**Problem**: ASCII charts are malformed

**Solutions**:
- Adjust terminal width
- Reduce chart height: `task-master velocity config set display.chartHeight 8`
- Enable compact mode: `task-master velocity config set display.compactMode true`

#### 4. Performance Issues

**Problem**: Velocity commands are slow

**Solutions**:
- Limit date range: `task-master velocity metrics --days=7`
- Use compact mode for large datasets
- Check for corrupted velocity metadata

### Debug Commands

```bash
# Test velocity calculations
node src/velocity/test.js

# Run comprehensive tests
node src/velocity/test-suite.js

# Check preferences
task-master velocity config list

# Validate task data
node src/velocity/service.js --validate
```

### Log Files

Velocity tracking logs are written to:
- `~/.task-master/logs/velocity.log` (if logging enabled)
- Console output with `[Velocity]` prefix

## API Reference

### VelocityCalculator

Core calculation engine for velocity metrics.

```javascript
const calculator = new VelocityCalculator();

// Calculate task duration
const hours = calculator.calculateTaskDuration(startTime, endTime);

// Calculate velocity rate
const rate = calculator.calculateVelocityRate(points, hours);

// Calculate daily velocity
const daily = calculator.calculateDailyVelocity(tasks, days);

// Calculate ETC
const etc = calculator.calculateETC(remainingTasks, dailyVelocity);
```

### VelocityService

High-level service for velocity operations.

```javascript
const service = new VelocityService();

// Get velocity metrics
const metrics = await service.getVelocityMetrics({ days: 7 });

// Get velocity trend
const trend = await service.getVelocityTrend(weeks);

// Update task status
await service.updateTaskStatus(taskId, newStatus);
```

### VelocityVisualizer

Visualization and chart generation.

```javascript
const visualizer = new VelocityVisualizer();

// Create dashboard
const dashboard = visualizer.createVelocityDashboard(metrics, trend);

// Create velocity chart
const chart = visualizer.createVelocityChart(data);

// Create progress bar
const bar = visualizer.createProgressBar(current, total);
```

### VelocityPreferences

User preferences management.

```javascript
const preferences = new VelocityPreferences();

// Load preferences
const prefs = await preferences.load();

// Set preference
await preferences.set('display.useColors', false);

// Get preference
const value = await preferences.get('calculation.velocityPeriod');

// Reset preferences
await preferences.reset(['display']);
```

### VelocityIntegration

Integration with task management workflow.

```javascript
const integration = new VelocityIntegration();

// Handle status change
await integration.onTaskStatusChange(id, oldStatus, newStatus);

// Estimate complexity
const complexity = integration.estimateComplexity(task);

// Generate summary
const summary = await integration.generateVelocitySummary();
```

## Advanced Usage

### Custom Complexity Estimation

Override automatic complexity estimation:

```javascript
// In your task creation workflow
task.velocity_metadata = {
  complexity_score: 13, // Custom complexity
  estimated_hours: 8,
  velocity_points: 13
};
```

### Bulk Operations

Process multiple tasks efficiently:

```javascript
const integration = new VelocityIntegration();

// Bulk update tasks
const tasks = await integration.loadTasks();
const enhanced = await integration.enhanceTasksWithVelocity(tasks);
await integration.saveTasks(enhanced);
```

### Custom Reporting

Create custom velocity reports:

```javascript
const service = new VelocityService();
const visualizer = new VelocityVisualizer();

// Get data
const metrics = await service.getVelocityMetrics({ days: 30 });
const trend = await service.getVelocityTrend(8);

// Create custom visualization
const report = `
${visualizer.createVelocityDashboard(metrics, trend)}

Custom Analysis:
- Team velocity increased 15% this month
- Average cycle time decreased from 6.2 to 4.5 hours
- Blocked time reduced by 40%
`;

console.log(report);
```

## Best Practices

### 1. Consistent Task Management

- Use consistent status values (`pending`, `in-progress`, `done`)
- Update task status promptly
- Include meaningful task descriptions
- Break down large tasks into smaller ones

### 2. Accurate Time Tracking

- Start tasks when work begins
- Mark tasks as done when complete
- Track blocked time separately
- Review and adjust estimates regularly

### 3. Team Adoption

- Train team on velocity concepts
- Establish velocity tracking guidelines
- Review velocity metrics in team meetings
- Use velocity data for sprint planning

### 4. Continuous Improvement

- Monitor velocity trends over time
- Identify bottlenecks in cycle time
- Adjust working hours and capacity settings
- Experiment with different complexity scales

## Migration Guide

### From Manual Tracking

If you're migrating from manual velocity tracking:

1. **Export existing data** to task-master format
2. **Run migration script**: `node src/velocity/migrate.js`
3. **Verify data integrity**: `node src/velocity/test-suite.js`
4. **Configure preferences** to match your current process
5. **Train team** on new workflow

### From Other Tools

Integration helpers for common tools:

```bash
# From Jira (example)
node scripts/import-jira-velocity.js --file=export.json

# From Trello (example)
node scripts/import-trello-velocity.js --board=board-id

# From CSV
node scripts/import-csv-velocity.js --file=data.csv
```

## Support

### Getting Help

1. **Documentation**: Check this guide and API reference
2. **Issues**: Report bugs on GitHub issues
3. **Discussions**: Join community discussions
4. **Support**: Contact maintainers for enterprise support

### Contributing

Contributions welcome! See `CONTRIBUTING.md` for guidelines.

### License

MIT License - see `LICENSE` file for details.

---

*This guide covers the comprehensive velocity tracking system for task-master CLI. For the latest updates and features, check the project repository.*
