#!/usr/bin/env node

/**
 * Velocity-Enhanced List Command
 * Extends the standard task-master list command with velocity tracking information
 */

const url = require('url');
const path = require('path');
const fs = require('fs');
const Table = require('cli-table3');
const chalk = require('chalk');
const boxen = require('boxen');

// Import velocity tracking components
const velocityService = require('../src/velocity/service.js');
const velocityCalculator = require('../src/velocity/calculator.js');
const velocityVisualizer = require('../src/velocity/visualizer.js');

const __filename = url.fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Enhanced list command with velocity tracking
 */
async function velocityEnhancedList(options = {}) {
    const { status, withSubtasks, showVelocity = true } = options;

    try {
        // Initialize velocity components
        const velocityServiceInstance = new velocityService.VelocityService();
        const calculator = new velocityCalculator.VelocityCalculator();
        const visualizer = new velocityVisualizer.VelocityVisualizer();

        // Load tasks
        const tasks = await velocityServiceInstance.loadTasks();

        // Display banner
        console.log(boxen('📊 Task Master with Velocity Tracking', {
            padding: 1,
            margin: 1,
            borderStyle: 'round',
            borderColor: 'blue'
        }));

        // Filter tasks by status if specified
        const filteredTasks = status && status.toLowerCase() !== 'all'
            ? tasks.filter(task => task.status && task.status.toLowerCase() === status.toLowerCase())
            : tasks;

        // Calculate velocity metrics
        const velocityMetrics = calculator.calculateVelocityMetrics(tasks);
        const trends = calculator.calculateTrends(tasks);

        // Display velocity summary if enabled
        if (showVelocity) {
            displayVelocitySummary(velocityMetrics, trends);
        }

        // Display tasks table
        displayTasksTable(filteredTasks, withSubtasks);

        // Display velocity insights
        if (showVelocity) {
            displayVelocityInsights(velocityMetrics, trends, visualizer);
        }

        // Display next task recommendation
        displayNextTaskRecommendation(tasks, velocityMetrics);

    } catch (error) {
        console.error(chalk.red('Error loading velocity-enhanced task list:'), error.message);
        process.exit(1);
    }
}

/**
 * Display velocity summary at the top
 */
function displayVelocitySummary(metrics, trends) {
    const summary = [
        `📈 Daily Velocity: ${chalk.cyan(metrics.dailyVelocity.toFixed(1))} points/day`,
        `⏱️  Avg Cycle Time: ${chalk.yellow(metrics.averageCycleTime.toFixed(1))} hours`,
        `🔄 Tasks in Progress: ${chalk.blue(metrics.tasksInProgress)}`,
        `✅ Completion Rate: ${chalk.green(metrics.completionRate.toFixed(1))}%`
    ].join('  |  ');

    console.log(boxen(summary, {
        padding: { top: 0, bottom: 0, left: 1, right: 1 },
        borderStyle: 'single',
        borderColor: 'gray'
    }));
    console.log();
}

/**
 * Display tasks in a table format with velocity information
 */
function displayTasksTable(tasks, withSubtasks) {
    const table = new Table({
        head: ['ID', 'Title', 'Status', 'Priority', 'Velocity', 'Cycle Time', 'Dependencies'],
        colWidths: [4, 25, 12, 10, 10, 12, 15],
        style: {
            head: ['cyan'],
            border: ['gray']
        }
    });

    tasks.forEach(task => {
        const velocityInfo = getTaskVelocityInfo(task);

        table.push([
            task.id,
            truncateText(task.title, 23),
            getStatusWithColor(task.status),
            task.priority || 'medium',
            velocityInfo.velocity,
            velocityInfo.cycleTime,
            formatDependencies(task.dependencies)
        ]);

        // Add subtasks if requested
        if (withSubtasks && task.subtasks && task.subtasks.length > 0) {
            task.subtasks.forEach(subtask => {
                const subtaskVelocity = getTaskVelocityInfo(subtask);
                table.push([
                    `  ${task.id}.${subtask.id}`,
                    `  ${truncateText(subtask.title, 21)}`,
                    getStatusWithColor(subtask.status),
                    subtask.priority || 'medium',
                    subtaskVelocity.velocity,
                    subtaskVelocity.cycleTime,
                    formatDependencies(subtask.dependencies)
                ]);
            });
        }
    });

    console.log(table.toString());
    console.log();
}

/**
 * Get velocity information for a task
 */
function getTaskVelocityInfo(task) {
    const velocity = task.velocityMetadata?.velocity || 0;
    const cycleTime = task.velocityMetadata?.cycleTime || 0;

    return {
        velocity: velocity > 0 ? `${velocity.toFixed(1)}pts` : '-',
        cycleTime: cycleTime > 0 ? `${cycleTime.toFixed(1)}h` : '-'
    };
}

/**
 * Display velocity insights and trends
 */
function displayVelocityInsights(metrics, trends, visualizer) {
    console.log(chalk.bold('📊 Velocity Insights:'));
    console.log();

    // Show trend information
    if (trends.length > 0) {
        const latestTrend = trends[trends.length - 1];
        const trendDirection = latestTrend.velocity > (trends[trends.length - 2]?.velocity || 0) ? '📈' : '📉';
        console.log(`${trendDirection} Recent Trend: ${latestTrend.velocity.toFixed(1)} points/day (${latestTrend.date})`);
    }

    // Show productivity insights
    const productivityLevel = getProductivityLevel(metrics.dailyVelocity);
    console.log(`🎯 Productivity Level: ${productivityLevel}`);

    // Show cycle time insights
    const cycleTimeInsight = getCycleTimeInsight(metrics.averageCycleTime);
    console.log(`⏰ Cycle Time: ${cycleTimeInsight}`);

    console.log();
}

/**
 * Display next task recommendation with velocity considerations
 */
function displayNextTaskRecommendation(tasks, metrics) {
    const pendingTasks = tasks.filter(task => task.status === 'pending');
    const availableTasks = pendingTasks.filter(task => {
        if (!task.dependencies || task.dependencies.length === 0) return true;
        return task.dependencies.every(depId => {
            const depTask = tasks.find(t => t.id === depId);
            return depTask && (depTask.status === 'done' || depTask.status === 'completed');
        });
    });

    if (availableTasks.length > 0) {
        // Sort by priority and complexity for velocity optimization
        const recommendedTask = availableTasks.sort((a, b) => {
            const priorityScore = getPriorityScore(a.priority) - getPriorityScore(b.priority);
            const complexityScore = (a.complexity || 5) - (b.complexity || 5);
            return priorityScore + (complexityScore * 0.3); // Weight priority higher
        })[0];

        console.log(boxen(
            `🎯 Recommended Next Task: #${recommendedTask.id} - ${recommendedTask.title}\n` +
            `Priority: ${recommendedTask.priority || 'medium'} | Estimated Complexity: ${recommendedTask.complexity || 'unknown'}`,
            {
                padding: 1,
                borderStyle: 'round',
                borderColor: 'green',
                title: '⚡ VELOCITY OPTIMIZED'
            }
        ));
    } else {
        console.log(boxen(
            'No tasks available to work on. All pending tasks have unmet dependencies.',
            {
                padding: 1,
                borderStyle: 'round',
                borderColor: 'yellow',
                title: '⚠️  NO AVAILABLE TASKS'
            }
        ));
    }
}

/**
 * Helper functions
 */
function truncateText(text, maxLength) {
    return text.length > maxLength ? text.substring(0, maxLength - 3) + '...' : text;
}

function getStatusWithColor(status) {
    const statusColors = {
        'done': chalk.green('✓ done'),
        'completed': chalk.green('✓ done'),
        'in-progress': chalk.yellow('⚡ progress'),
        'pending': chalk.blue('○ pending'),
        'blocked': chalk.red('⚠ blocked'),
        'deferred': chalk.gray('x deferred'),
        'cancelled': chalk.red('✗ cancelled')
    };
    return statusColors[status] || status;
}

function formatDependencies(dependencies) {
    if (!dependencies || dependencies.length === 0) return 'None';
    return dependencies.join(', ');
}

function getProductivityLevel(dailyVelocity) {
    if (dailyVelocity >= 3) return chalk.green('🔥 High');
    if (dailyVelocity >= 1.5) return chalk.yellow('📈 Good');
    if (dailyVelocity >= 0.5) return chalk.blue('📊 Moderate');
    return chalk.gray('🐌 Low');
}

function getCycleTimeInsight(avgCycleTime) {
    if (avgCycleTime <= 4) return chalk.green('🚀 Fast');
    if (avgCycleTime <= 8) return chalk.yellow('⚡ Normal');
    if (avgCycleTime <= 16) return chalk.orange('🐢 Slow');
    return chalk.red('🚨 Very Slow');
}

function getPriorityScore(priority) {
    const scores = { 'high': 1, 'medium': 2, 'low': 3 };
    return scores[priority] || 2;
}

// CLI handling
if (require.main === module) {
    const args = process.argv.slice(2);
    const options = {};

    // Parse command line arguments
    for (let i = 0; i < args.length; i++) {
        if (args[i] === '--status' && args[i + 1]) {
            options.status = args[i + 1];
            i++;
        } else if (args[i] === '--with-subtasks') {
            options.withSubtasks = true;
        } else if (args[i] === '--no-velocity') {
            options.showVelocity = false;
        }
    }

    velocityEnhancedList(options);
}

module.exports = velocityEnhancedList;
