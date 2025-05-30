/**
 * Velocity Visualization Demo
 * Demonstrates visualization capabilities with sample data
 */

const VelocityVisualizer = require('./visualizer');
const chalk = require('chalk');

async function runVisualizationDemo() {
  console.log(chalk.blue.bold('\n🎨 Velocity Visualization Demo\n'));
  console.log(chalk.gray('=' .repeat(60)));

  const visualizer = new VelocityVisualizer();

  // Sample velocity trend data
  const velocityHistory = [
    { period: 'Week 1', velocity: 8.5 },
    { period: 'Week 2', velocity: 12.3 },
    { period: 'Week 3', velocity: 9.7 },
    { period: 'Week 4', velocity: 15.2 },
    { period: 'Week 5', velocity: 11.8 },
    { period: 'Week 6', velocity: 14.6 }
  ];

  // Demo 1: Velocity Trend Chart
  console.log(chalk.yellow.bold('\n📈 Demo 1: Velocity Trend Chart'));
  const velocityChart = visualizer.createVelocityChart(velocityHistory, {
    title: 'Team Velocity Over Time',
    showValues: true
  });
  console.log(velocityChart);

  // Sample cycle time data
  const cycleTimes = [
    2.5, 4.2, 1.8, 6.7, 3.1, 5.4, 2.9, 8.2, 4.6, 3.8,
    7.1, 2.3, 5.9, 4.4, 6.2, 3.7, 9.1, 2.8, 4.9, 5.6
  ];

  // Demo 2: Cycle Time Histogram
  console.log(chalk.yellow.bold('\n📊 Demo 2: Cycle Time Distribution'));
  const histogram = visualizer.createCycleTimeHistogram(cycleTimes, {
    title: 'Task Cycle Time Distribution',
    bins: 8
  });
  console.log(histogram);

  // Sample burndown data
  const burndownData = [
    { date: 'Week 1', remaining: 100 },
    { date: 'Week 2', remaining: 85 },
    { date: 'Week 3', remaining: 72 },
    { date: 'Week 4', remaining: 58 },
    { date: 'Week 5', remaining: 41 },
    { date: 'Week 6', remaining: 28 },
    { date: 'Week 7', remaining: 15 },
    { date: 'Week 8', remaining: 5 }
  ];

  // Demo 3: Burndown Chart
  console.log(chalk.yellow.bold('\n📉 Demo 3: Project Burndown Chart'));
  const burndownChart = visualizer.createBurndownChart(burndownData, {
    title: 'Sprint Burndown Chart',
    showIdealLine: true
  });
  console.log(burndownChart);

  // Demo 4: Progress Bars
  console.log(chalk.yellow.bold('\n📊 Demo 4: Progress Indicators'));
  console.log('Sprint Progress:');
  console.log('  ' + visualizer.createProgressBar(7, 10, { style: 'blocks', showPercentage: true }));
  console.log('  ' + visualizer.createProgressBar(15, 20, { style: 'dots', showPercentage: true }));
  console.log('  ' + visualizer.createProgressBar(8, 12, { style: 'lines', showPercentage: true }));

  // Demo 5: Data Table
  console.log(chalk.yellow.bold('\n📋 Demo 5: Task Summary Table'));
  const taskData = [
    { id: '15.1', title: 'Design Data Model', status: 'Done', complexity: 7, hours: 6.5 },
    { id: '15.2', title: 'Core Logic', status: 'Done', complexity: 8, hours: 8.2 },
    { id: '15.3', title: 'CLI Interface', status: 'Done', complexity: 6, hours: 5.8 },
    { id: '15.4', title: 'Visualizations', status: 'In Progress', complexity: 7, hours: 4.2 }
  ];

  const columns = [
    { key: 'id', header: 'ID', minWidth: 6 },
    { key: 'title', header: 'Task', minWidth: 15 },
    {
      key: 'status',
      header: 'Status',
      minWidth: 10,
      color: (value) => value === 'Done' ? chalk.green(value) : chalk.yellow(value)
    },
    { key: 'complexity', header: 'Complexity', minWidth: 10 },
    { key: 'hours', header: 'Hours', minWidth: 8 }
  ];

  const table = visualizer.createTable(taskData, columns);
  console.log(table);

  // Demo 6: Sample Dashboard
  console.log(chalk.yellow.bold('\n🚀 Demo 6: Sample Velocity Dashboard'));

  const sampleMetrics = {
    velocity: { daily: 12.4, weekly: 86.8, monthly: 372 },
    completed: { count: 8, totalComplexity: 56 },
    cycleTime: { average: 4.8, median: 4.2, min: 1.8, max: 9.1 },
    workInProgress: { count: 3 },
    estimates: { totalComplexity: 45, estimatedDays: 3.6 },
    tasks: taskData.map(t => ({ ...t, cycleTime: t.hours }))
  };

  const sampleTrend = { history: velocityHistory };

  const dashboard = visualizer.createVelocityDashboard(sampleMetrics, sampleTrend);
  console.log(dashboard);

  console.log(chalk.gray('=' .repeat(60)));
  console.log(chalk.green.bold('✅ Visualization Demo Complete!'));
  console.log(chalk.gray('All visualization components are working correctly.\n'));
}

// Export for use in other modules or run directly
if (require.main === module) {
  runVisualizationDemo().catch(console.error);
}

module.exports = { runVisualizationDemo };
