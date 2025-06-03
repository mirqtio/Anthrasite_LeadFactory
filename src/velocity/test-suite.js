#!/usr/bin/env node

/**
 * Comprehensive Velocity Tracking Test Suite
 * Tests all components of the velocity tracking system
 */

const fs = require('fs').promises;
const path = require('path');
const os = require('os');
const chalk = require('chalk');

// Import all modules to test
const VelocityCalculator = require('./calculator');
const VelocityService = require('./service');
const VelocityVisualizer = require('./visualizer');
const VelocityPreferences = require('./preferences');
const VelocityIntegration = require('./integration');

class VelocityTestSuite {
  constructor() {
    this.testDir = path.join(os.tmpdir(), 'velocity-test-' + Date.now());
    this.testTasksFile = path.join(this.testDir, 'tasks.json');
    this.testConfigFile = path.join(this.testDir, 'velocity-preferences.json');

    this.results = {
      passed: 0,
      failed: 0,
      errors: []
    };
  }

  /**
   * Run all tests
   */
  async runAllTests() {
    console.log(chalk.blue.bold('🧪 Comprehensive Velocity Tracking Test Suite\n'));

    try {
      await this.setup();

      const testSuites = [
        { name: 'Calculator Tests', tests: this.runCalculatorTests },
        { name: 'Service Tests', tests: this.runServiceTests },
        { name: 'Visualizer Tests', tests: this.runVisualizerTests },
        { name: 'Preferences Tests', tests: this.runPreferencesTests },
        { name: 'Integration Tests', tests: this.runIntegrationTests },
        { name: 'End-to-End Tests', tests: this.runEndToEndTests }
      ];

      for (const suite of testSuites) {
        console.log(chalk.yellow.bold(`\n📋 ${suite.name}`));
        console.log(chalk.gray('─'.repeat(50)));
        await suite.tests.call(this);
      }

      await this.cleanup();

      console.log(chalk.blue.bold('\n📊 Test Results Summary'));
      console.log(chalk.gray('═'.repeat(50)));
      console.log(`${chalk.green('✅ Passed:')} ${this.results.passed}`);
      console.log(`${chalk.red('❌ Failed:')} ${this.results.failed}`);

      if (this.results.errors.length > 0) {
        console.log(chalk.red.bold('\n🚨 Failed Tests:'));
        this.results.errors.forEach(error => {
          console.log(chalk.red(`  • ${error}`));
        });
      }

      const success = this.results.failed === 0;
      console.log(chalk[success ? 'green' : 'red'].bold(`\n${success ? '🎉 All tests passed!' : '💥 Some tests failed!'}`));

      return success;

    } catch (error) {
      console.error(chalk.red('❌ Test suite failed:'), error.message);
      return false;
    }
  }

  /**
   * Setup test environment
   */
  async setup() {
    await fs.mkdir(this.testDir, { recursive: true });

    // Create sample tasks file
    const sampleTasks = [
      {
        id: 1,
        title: 'Test Task 1',
        status: 'done',
        priority: 'high',
        dependencies: [],
        created_at: '2024-01-01T10:00:00Z',
        started_at: '2024-01-01T11:00:00Z',
        completed_at: '2024-01-01T15:00:00Z',
        velocity_metadata: {
          complexity_score: 5,
          estimated_hours: 4,
          actual_hours: 4,
          velocity_points: 5,
          blocked_time: 0,
          status_history: [
            { status: 'pending', timestamp: '2024-01-01T10:00:00Z', duration_hours: null },
            { status: 'in-progress', timestamp: '2024-01-01T11:00:00Z', duration_hours: 1 },
            { status: 'done', timestamp: '2024-01-01T15:00:00Z', duration_hours: 4 }
          ]
        }
      },
      {
        id: 2,
        title: 'Test Task 2',
        status: 'in-progress',
        priority: 'medium',
        dependencies: [],
        created_at: '2024-01-02T09:00:00Z',
        started_at: '2024-01-02T10:00:00Z',
        velocity_metadata: {
          complexity_score: 8,
          estimated_hours: 6,
          actual_hours: null,
          velocity_points: 8,
          blocked_time: 0,
          status_history: [
            { status: 'pending', timestamp: '2024-01-02T09:00:00Z', duration_hours: null },
            { status: 'in-progress', timestamp: '2024-01-02T10:00:00Z', duration_hours: 1 }
          ]
        }
      }
    ];

    await fs.writeFile(this.testTasksFile, JSON.stringify(sampleTasks, null, 2));
  }

  /**
   * Cleanup test environment
   */
  async cleanup() {
    try {
      await fs.rm(this.testDir, { recursive: true, force: true });
    } catch (error) {
      // Ignore cleanup errors
    }
  }

  /**
   * Test helper
   */
  async test(name, testFn) {
    try {
      await testFn();
      console.log(chalk.green(`  ✅ ${name}`));
      this.results.passed++;
    } catch (error) {
      console.log(chalk.red(`  ❌ ${name}: ${error.message}`));
      this.results.failed++;
      this.results.errors.push(`${name}: ${error.message}`);
    }
  }

  /**
   * Calculator Tests
   */
  async runCalculatorTests() {
    const calculator = new VelocityCalculator();

    await this.test('Task Duration Calculation', async () => {
      const duration = calculator.calculateTaskDuration(
        '2024-01-01T10:00:00Z',
        '2024-01-01T14:00:00Z'
      );
      if (duration !== 4) {
        throw new Error(`Expected 4 hours, got ${duration}`);
      }
    });

    await this.test('Velocity Rate Calculation', async () => {
      const rate = calculator.calculateVelocityRate(5, 4);
      if (rate !== 1.25) {
        throw new Error(`Expected 1.25, got ${rate}`);
      }
    });

    await this.test('Daily Velocity Calculation', async () => {
      const tasks = [
        { velocity_metadata: { velocity_points: 5 }, completed_at: '2024-01-01T15:00:00Z' },
        { velocity_metadata: { velocity_points: 3 }, completed_at: '2024-01-01T16:00:00Z' }
      ];
      const velocity = calculator.calculateDailyVelocity(tasks, 1);
      if (velocity !== 8) {
        throw new Error(`Expected 8, got ${velocity}`);
      }
    });

    await this.test('ETC Calculation', async () => {
      const remainingTasks = [
        { velocity_metadata: { complexity_score: 5 } },
        { velocity_metadata: { complexity_score: 8 } },
        { velocity_metadata: { complexity_score: 3 } }
      ];
      const etc = calculator.calculateETC(remainingTasks, 4); // 4 points per day
      if (etc.totalComplexity !== 16) {
        throw new Error(`Expected total complexity 16, got ${etc.totalComplexity}`);
      }
      if (etc.estimatedDays !== 4) {
        throw new Error(`Expected 4 days, got ${etc.estimatedDays}`);
      }
    });

    await this.test('Velocity Metadata Update', async () => {
      const task = {
        velocity_metadata: {
          status_history: []
        }
      };
      calculator.updateTaskVelocityMetadata(task, 'in-progress', '2024-01-01T10:00:00Z');
      if (task.velocity_metadata.status_history.length !== 1) {
        throw new Error('Status history not updated');
      }
    });
  }

  /**
   * Service Tests
   */
  async runServiceTests() {
    const service = new VelocityService(this.testTasksFile);

    await this.test('Load Tasks', async () => {
      const tasks = await service.loadTasks();
      if (tasks.length !== 2) {
        throw new Error(`Expected 2 tasks, got ${tasks.length}`);
      }
    });

    await this.test('Find Task by ID', async () => {
      const tasks = await service.loadTasks();
      const task = service.findTaskById(tasks, 1);
      if (!task || task.title !== 'Test Task 1') {
        throw new Error('Task not found or incorrect');
      }
    });

    await this.test('Get Velocity Metrics', async () => {
      const metrics = await service.getVelocityMetrics({ days: 7 });
      if (typeof metrics.velocity.daily !== 'number') {
        throw new Error('Daily velocity not calculated');
      }
      if (typeof metrics.completed.count !== 'number') {
        throw new Error('Completed count not calculated');
      }
    });

    await this.test('Get Velocity Trend', async () => {
      const trend = await service.getVelocityTrend(4);
      if (!trend.history || !Array.isArray(trend.history)) {
        throw new Error('Trend history not generated');
      }
    });

    await this.test('Update Task Status', async () => {
      await service.updateTaskStatus(2, 'done');
      const tasks = await service.loadTasks();
      const task = service.findTaskById(tasks, 2);
      if (task.status !== 'done') {
        throw new Error('Task status not updated');
      }
    });
  }

  /**
   * Visualizer Tests
   */
  async runVisualizerTests() {
    const visualizer = new VelocityVisualizer();

    await this.test('Create Progress Bar', async () => {
      const bar = visualizer.createProgressBar(7, 10);
      if (typeof bar !== 'string' || bar.length === 0) {
        throw new Error('Progress bar not created');
      }
    });

    await this.test('Create Velocity Chart', async () => {
      const data = [
        { period: 'Week 1', velocity: 5 },
        { period: 'Week 2', velocity: 8 }
      ];
      const chart = visualizer.createVelocityChart(data);
      if (typeof chart !== 'string' || !chart.includes('Velocity Trend')) {
        throw new Error('Velocity chart not created');
      }
    });

    await this.test('Create Table', async () => {
      const data = [
        { id: 1, name: 'Test', value: 100 }
      ];
      const columns = [
        { key: 'id', header: 'ID' },
        { key: 'name', header: 'Name' },
        { key: 'value', header: 'Value' }
      ];
      const table = visualizer.createTable(data, columns);
      if (typeof table !== 'string' || !table.includes('Test')) {
        throw new Error('Table not created');
      }
    });

    await this.test('Create Dashboard', async () => {
      const metrics = {
        velocity: { daily: 5, weekly: 35, monthly: 150 },
        completed: { count: 10, totalComplexity: 50 },
        cycleTime: { average: 4.5, median: 4.0 },
        workInProgress: { count: 3 },
        progress: { completion: 0.5, complexity: 0.6 }
      };
      const trend = { history: [] };
      const dashboard = visualizer.createVelocityDashboard(metrics, trend);
      if (typeof dashboard !== 'string' || !dashboard.includes('Velocity Dashboard')) {
        throw new Error('Dashboard not created');
      }
    });
  }

  /**
   * Preferences Tests
   */
  async runPreferencesTests() {
    const preferences = new VelocityPreferences(this.testConfigFile);

    await this.test('Load Default Preferences', async () => {
      const prefs = await preferences.load();
      if (!prefs.display || !prefs.calculation) {
        throw new Error('Default preferences not loaded');
      }
    });

    await this.test('Set and Get Preference', async () => {
      await preferences.set('display.chartHeight', 15);
      const value = await preferences.get('display.chartHeight');
      if (value !== 15) {
        throw new Error(`Expected 15, got ${value}`);
      }
    });

    await this.test('Validate Preferences', async () => {
      const prefs = await preferences.load();
      const errors = preferences.validate(prefs);
      if (errors.length > 0) {
        throw new Error(`Validation errors: ${errors.join(', ')}`);
      }
    });

    await this.test('Reset Preferences', async () => {
      await preferences.set('display.useColors', false);
      await preferences.reset(['display']);
      const value = await preferences.get('display.useColors');
      if (value !== true) {
        throw new Error('Preferences not reset correctly');
      }
    });
  }

  /**
   * Integration Tests
   */
  async runIntegrationTests() {
    const integration = new VelocityIntegration(this.testTasksFile);

    await this.test('Estimate Complexity', async () => {
      const task = {
        title: 'Implement comprehensive system',
        details: 'Create advanced integration with complex architecture'
      };
      const complexity = integration.estimateComplexity(task);
      if (complexity < 5 || complexity > 10) {
        throw new Error(`Complexity should be 5-10, got ${complexity}`);
      }
    });

    await this.test('Task Status Change Hook', async () => {
      await integration.onTaskStatusChange(1, 'in-progress', 'done');
      // Should not throw error
    });

    await this.test('Enhance Tasks with Velocity', async () => {
      const tasks = await integration.velocityService.loadTasks();
      const enhanced = await integration.enhanceTasksWithVelocity(tasks);
      if (enhanced.length !== tasks.length) {
        throw new Error('Enhanced tasks count mismatch');
      }
    });

    await this.test('Generate Velocity Summary', async () => {
      const summary = await integration.generateVelocitySummary();
      if (!summary || typeof summary.dailyVelocity !== 'number') {
        throw new Error('Velocity summary not generated');
      }
    });
  }

  /**
   * End-to-End Tests
   */
  async runEndToEndTests() {
    await this.test('Complete Workflow', async () => {
      // Create integration
      const integration = new VelocityIntegration(this.testTasksFile);

      // Migrate tasks
      await integration.migrateTasksToVelocity();

      // Update task status
      await integration.onTaskStatusChange(2, 'in-progress', 'done');

      // Get metrics
      const metrics = await integration.velocityService.getVelocityMetrics({ days: 7 });

      // Create visualization
      const visualizer = new VelocityVisualizer();
      const dashboard = visualizer.createVelocityDashboard(metrics, { history: [] });

      if (typeof dashboard !== 'string') {
        throw new Error('End-to-end workflow failed');
      }
    });

    await this.test('CLI Integration', async () => {
      // Test that CLI commands can be constructed
      const { spawn } = require('child_process');

      // This is a basic test to ensure CLI structure is correct
      const cliPath = path.join(__dirname, 'cli.js');
      const exists = await fs.access(cliPath).then(() => true).catch(() => false);

      if (!exists) {
        throw new Error('CLI file not found');
      }
    });

    await this.test('Configuration Management', async () => {
      const preferences = new VelocityPreferences(this.testConfigFile);

      // Set preferences
      await preferences.set('display.chartHeight', 20);
      await preferences.set('calculation.velocityPeriod', 'month');

      // Load and verify
      const prefs = await preferences.load();
      if (prefs.display.chartHeight !== 20 || prefs.calculation.velocityPeriod !== 'month') {
        throw new Error('Configuration not persisted correctly');
      }
    });
  }
}

// Performance test function
async function runPerformanceTests() {
  console.log(chalk.blue.bold('\n⚡ Performance Tests\n'));

  const calculator = new VelocityCalculator();
  const visualizer = new VelocityVisualizer();

  // Test calculation performance
  const start1 = Date.now();
  for (let i = 0; i < 1000; i++) {
    calculator.calculateVelocityRate(Math.random() * 10, Math.random() * 10 + 1);
  }
  const calcTime = Date.now() - start1;
  console.log(`Calculator performance: ${calcTime}ms for 1000 calculations`);

  // Test visualization performance
  const data = Array.from({ length: 100 }, (_, i) => ({
    period: `Week ${i + 1}`,
    velocity: Math.random() * 20
  }));

  const start2 = Date.now();
  visualizer.createVelocityChart(data);
  const vizTime = Date.now() - start2;
  console.log(`Visualizer performance: ${vizTime}ms for 100-point chart`);

  if (calcTime > 100 || vizTime > 500) {
    console.log(chalk.yellow('⚠️  Performance may need optimization'));
  } else {
    console.log(chalk.green('✅ Performance tests passed'));
  }
}

// Main execution
async function main() {
  const args = process.argv.slice(2);

  if (args.includes('--performance')) {
    await runPerformanceTests();
    return;
  }

  const testSuite = new VelocityTestSuite();
  const success = await testSuite.runAllTests();

  if (args.includes('--performance')) {
    await runPerformanceTests();
  }

  process.exit(success ? 0 : 1);
}

// Export for use in other modules
module.exports = { VelocityTestSuite, runPerformanceTests };

// Run if called directly
if (require.main === module) {
  main().catch(console.error);
}
