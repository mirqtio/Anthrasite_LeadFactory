# Velocity Tracking System

A comprehensive velocity tracking system for the task-master CLI that provides insights into team productivity, estimates completion times, and helps optimize workflow efficiency.

## Features

- 📊 **Real-time Velocity Metrics** - Track daily, weekly, and monthly velocity
- 📈 **Trend Analysis** - Visualize velocity trends over time
- ⏱️ **Cycle Time Tracking** - Monitor task completion times
- 🎯 **ETC Calculations** - Estimate time to completion for remaining work
- 📋 **Interactive Dashboard** - Comprehensive velocity overview
- 🎨 **ASCII Charts** - Beautiful terminal-based visualizations
- ⚙️ **Configurable Preferences** - Customize tracking and display settings
- 🔄 **Automatic Integration** - Seamless integration with task workflows

## Quick Start

```bash
# View velocity dashboard
task-master velocity dashboard

# Show velocity metrics
task-master velocity metrics

# Configure preferences
task-master velocity config list
```

## Documentation

- **[Complete Guide](../../docs/velocity-tracking-guide.md)** - Comprehensive documentation
- **[Quick Reference](../../docs/velocity-quick-reference.md)** - Essential commands and settings
- **[API Documentation](../../docs/velocity-api.md)** - Programmatic API reference

## Architecture

```
src/velocity/
├── calculator.js      # Core velocity calculations
├── service.js         # High-level velocity operations
├── visualizer.js      # Charts and dashboard generation
├── preferences.js     # User preferences management
├── preferences-cli.js # CLI for managing preferences
├── integration.js     # Task workflow integration
├── migrate.js         # Data migration utilities
├── test-suite.js      # Comprehensive test suite
└── README.md         # This file
```

## Core Components

### VelocityCalculator
Core calculation engine for velocity metrics including task duration, velocity rates, daily velocity, and ETC calculations.

### VelocityService
High-level service providing velocity metrics, trend analysis, and task management operations.

### VelocityVisualizer
Visualization engine for creating dashboards, charts, progress bars, and formatted tables.

### VelocityPreferences
User preferences management with validation, defaults, and configuration persistence.

### VelocityIntegration
Integration layer that connects velocity tracking with task management workflows.

## Key Concepts

- **Velocity Points**: Complexity/effort measure for tasks
- **Daily Velocity**: Average points completed per working day
- **Cycle Time**: Time from task start to completion
- **ETC**: Estimated time to complete remaining work

## Testing

```bash
# Run comprehensive test suite
node src/velocity/test-suite.js

# Run performance tests
node src/velocity/test-suite.js --performance

# Run preferences tests
node src/velocity/preferences-test.js --test
```

## Migration

For existing projects, run the migration script to add velocity metadata:

```bash
node src/velocity/migrate.js
```

## Configuration

Preferences are stored in `~/.task-master/velocity-preferences.json` and can be managed via:

```bash
task-master velocity config list
task-master velocity config set <key> <value>
task-master velocity config reset
```

## Integration

The velocity system automatically integrates with task status changes:

- Tasks moving to `in-progress` start time tracking
- Tasks moving to `done` calculate velocity metrics
- Velocity metadata is automatically maintained

## Performance

- Optimized for projects with 1000+ tasks
- Memory-efficient calculations
- Lazy loading of task data
- Configurable date ranges for large datasets

## Contributing

1. Run tests: `node src/velocity/test-suite.js`
2. Follow existing code patterns
3. Update documentation for new features
4. Ensure backward compatibility

## License

MIT License - see project LICENSE file for details.
