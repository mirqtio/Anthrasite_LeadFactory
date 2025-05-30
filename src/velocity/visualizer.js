/**
 * Velocity Visualization Module
 * Creates charts, graphs, and visual representations of velocity data
 */

const chalk = require('chalk');

class VelocityVisualizer {
  constructor() {
    this.chartWidth = 60;
    this.chartHeight = 15;
  }

  /**
   * Create a velocity trend chart
   * @param {Array} velocityHistory - Array of velocity data points
   * @param {Object} options - Chart options
   * @returns {string} ASCII chart
   */
  createVelocityChart(velocityHistory, options = {}) {
    const {
      title = 'Velocity Trend',
      width = this.chartWidth,
      height = this.chartHeight,
      showValues = true
    } = options;

    if (!velocityHistory || velocityHistory.length === 0) {
      return chalk.gray('No velocity data available for chart');
    }

    const values = velocityHistory.map(h => h.velocity);
    const labels = velocityHistory.map(h => h.period);
    const maxValue = Math.max(...values, 1);
    const minValue = Math.min(...values, 0);
    const range = maxValue - minValue || 1;

    let chart = chalk.blue.bold(`\n📈 ${title}\n`);
    chart += chalk.gray('─'.repeat(width + 10)) + '\n';

    // Create chart rows from top to bottom
    for (let row = height - 1; row >= 0; row--) {
      const threshold = minValue + (range * row / (height - 1));
      let line = chalk.gray(`${threshold.toFixed(1).padStart(5)} │ `);

      for (let col = 0; col < values.length; col++) {
        const value = values[col];
        const barHeight = ((value - minValue) / range) * (height - 1);

        if (barHeight >= row) {
          // Determine color based on value relative to average
          const avg = values.reduce((sum, v) => sum + v, 0) / values.length;
          const color = value > avg ? chalk.green : value < avg ? chalk.red : chalk.yellow;
          line += color('█');
        } else {
          line += ' ';
        }

        // Add spacing between bars
        if (col < values.length - 1) {
          line += ' ';
        }
      }

      chart += line + '\n';
    }

    // Add x-axis
    chart += chalk.gray('      └' + '─'.repeat(values.length * 2 - 1) + '\n');

    // Add labels
    let labelLine = '       ';
    labels.forEach((label, index) => {
      labelLine += chalk.gray(label.substring(0, 1));
      if (index < labels.length - 1) {
        labelLine += ' ';
      }
    });
    chart += labelLine + '\n';

    // Add values if requested
    if (showValues) {
      chart += chalk.gray('\nValues: ');
      values.forEach((value, index) => {
        const color = value > 0 ? chalk.green : chalk.gray;
        chart += color(`${value.toFixed(1)}`);
        if (index < values.length - 1) {
          chart += chalk.gray(', ');
        }
      });
      chart += '\n';
    }

    return chart;
  }

  /**
   * Create a cycle time distribution chart
   * @param {Array} cycleTimes - Array of cycle times
   * @param {Object} options - Chart options
   * @returns {string} ASCII histogram
   */
  createCycleTimeHistogram(cycleTimes, options = {}) {
    const {
      title = 'Cycle Time Distribution',
      bins = 10,
      width = this.chartWidth
    } = options;

    if (!cycleTimes || cycleTimes.length === 0) {
      return chalk.gray('No cycle time data available for histogram');
    }

    const minTime = Math.min(...cycleTimes);
    const maxTime = Math.max(...cycleTimes);
    const binSize = (maxTime - minTime) / bins || 1;

    // Create bins
    const histogram = new Array(bins).fill(0);
    cycleTimes.forEach(time => {
      const binIndex = Math.min(Math.floor((time - minTime) / binSize), bins - 1);
      histogram[binIndex]++;
    });

    const maxCount = Math.max(...histogram);
    const barWidth = Math.floor(width / bins);

    let chart = chalk.blue.bold(`\n📊 ${title}\n`);
    chart += chalk.gray('─'.repeat(width + 10)) + '\n';

    // Create horizontal bars
    for (let i = 0; i < bins; i++) {
      const count = histogram[i];
      const barLength = maxCount > 0 ? Math.round((count / maxCount) * barWidth) : 0;
      const binStart = minTime + (i * binSize);
      const binEnd = binStart + binSize;

      const label = `${binStart.toFixed(1)}-${binEnd.toFixed(1)}h`;
      const bar = chalk.cyan('█'.repeat(barLength)) + chalk.gray('░'.repeat(barWidth - barLength));
      const countLabel = count > 0 ? chalk.white.bold(` (${count})`) : '';

      chart += `${label.padStart(12)} │ ${bar}${countLabel}\n`;
    }

    chart += chalk.gray(`\nTotal tasks: ${cycleTimes.length}, Range: ${minTime.toFixed(1)}-${maxTime.toFixed(1)}h\n`);

    return chart;
  }

  /**
   * Create a burndown chart
   * @param {Array} burndownData - Array of {date, remaining} objects
   * @param {Object} options - Chart options
   * @returns {string} ASCII burndown chart
   */
  createBurndownChart(burndownData, options = {}) {
    const {
      title = 'Burndown Chart',
      width = this.chartWidth,
      height = this.chartHeight,
      showIdealLine = true
    } = options;

    if (!burndownData || burndownData.length === 0) {
      return chalk.gray('No burndown data available for chart');
    }

    const values = burndownData.map(d => d.remaining);
    const maxValue = Math.max(...values);
    const minValue = 0;
    const range = maxValue || 1;

    let chart = chalk.blue.bold(`\n📉 ${title}\n`);
    chart += chalk.gray('─'.repeat(width + 10)) + '\n';

    // Create chart
    for (let row = height - 1; row >= 0; row--) {
      const threshold = minValue + (range * row / (height - 1));
      let line = chalk.gray(`${threshold.toFixed(0).padStart(5)} │ `);

      for (let col = 0; col < values.length; col++) {
        const value = values[col];
        const normalizedValue = ((value - minValue) / range) * (height - 1);

        // Show ideal line if requested
        if (showIdealLine && col > 0) {
          const idealValue = maxValue * (1 - col / (values.length - 1));
          const normalizedIdeal = ((idealValue - minValue) / range) * (height - 1);

          if (Math.abs(normalizedIdeal - row) < 0.5) {
            line += chalk.gray('·');
          } else if (normalizedValue >= row) {
            line += chalk.red('█'); // Actual progress
          } else {
            line += ' ';
          }
        } else if (normalizedValue >= row) {
          line += chalk.red('█');
        } else {
          line += ' ';
        }

        if (col < values.length - 1) {
          line += ' ';
        }
      }

      chart += line + '\n';
    }

    // Add legend
    chart += chalk.gray('\nLegend: ') + chalk.red('█ Actual') +
             (showIdealLine ? chalk.gray(' · Ideal') : '') + '\n';

    return chart;
  }

  /**
   * Create a velocity vs complexity scatter plot
   * @param {Array} tasks - Array of completed tasks
   * @param {Object} options - Chart options
   * @returns {string} ASCII scatter plot
   */
  createVelocityScatterPlot(tasks, options = {}) {
    const {
      title = 'Velocity vs Complexity',
      width = this.chartWidth,
      height = this.chartHeight
    } = options;

    if (!tasks || tasks.length === 0) {
      return chalk.gray('No task data available for scatter plot');
    }

    const complexities = tasks.map(t => t.velocity_metadata?.complexity_score || 5);
    const cycleTimes = tasks.map(t => t.velocity_metadata?.actual_hours || 0).filter(t => t > 0);

    if (cycleTimes.length === 0) {
      return chalk.gray('No cycle time data available for scatter plot');
    }

    const maxComplexity = Math.max(...complexities);
    const maxCycleTime = Math.max(...cycleTimes);

    let chart = chalk.blue.bold(`\n📈 ${title}\n`);
    chart += chalk.gray('─'.repeat(width + 10)) + '\n';

    // Create grid
    const grid = Array(height).fill().map(() => Array(width).fill(' '));

    // Plot points
    tasks.forEach(task => {
      const complexity = task.velocity_metadata?.complexity_score || 5;
      const cycleTime = task.velocity_metadata?.actual_hours;

      if (cycleTime && cycleTime > 0) {
        const x = Math.floor((complexity / maxComplexity) * (width - 1));
        const y = Math.floor(((maxCycleTime - cycleTime) / maxCycleTime) * (height - 1));

        if (x >= 0 && x < width && y >= 0 && y < height) {
          grid[y][x] = '●';
        }
      }
    });

    // Render grid
    for (let row = 0; row < height; row++) {
      const yValue = maxCycleTime * (1 - row / (height - 1));
      let line = chalk.gray(`${yValue.toFixed(1).padStart(5)} │ `);

      for (let col = 0; col < width; col++) {
        if (grid[row][col] === '●') {
          line += chalk.green('●');
        } else {
          line += chalk.gray('·');
        }
      }

      chart += line + '\n';
    }

    // Add x-axis labels
    chart += chalk.gray('      └' + '─'.repeat(width) + '\n');
    chart += chalk.gray('       0') + chalk.gray(' '.repeat(width - 10)) + chalk.gray(`${maxComplexity}\n`);
    chart += chalk.gray('       Complexity →\n');

    return chart;
  }

  /**
   * Create a simple progress bar
   * @param {number} current - Current value
   * @param {number} total - Total value
   * @param {Object} options - Progress bar options
   * @returns {string} Progress bar
   */
  createProgressBar(current, total, options = {}) {
    const {
      width = 40,
      showPercentage = true,
      showNumbers = true,
      style = 'blocks'
    } = options;

    const percentage = total > 0 ? (current / total) * 100 : 0;
    const filled = Math.round((percentage / 100) * width);
    const empty = width - filled;

    let bar = '';

    if (style === 'blocks') {
      bar = chalk.green('█'.repeat(filled)) + chalk.gray('░'.repeat(empty));
    } else if (style === 'dots') {
      bar = chalk.green('●'.repeat(filled)) + chalk.gray('○'.repeat(empty));
    } else {
      bar = chalk.green('='.repeat(filled)) + chalk.gray('-'.repeat(empty));
    }

    let result = `[${bar}]`;

    if (showPercentage) {
      result += ` ${percentage.toFixed(1)}%`;
    }

    if (showNumbers) {
      result += ` (${current}/${total})`;
    }

    return result;
  }

  /**
   * Create a velocity dashboard
   * @param {Object} metrics - Velocity metrics
   * @param {Object} trend - Velocity trend data
   * @returns {string} Complete dashboard
   */
  createVelocityDashboard(metrics, trend) {
    let dashboard = chalk.blue.bold('\n🚀 Velocity Dashboard\n');
    dashboard += chalk.gray('═'.repeat(80)) + '\n\n';

    // Key metrics section
    dashboard += chalk.yellow.bold('📊 Key Metrics\n');
    dashboard += chalk.gray('─'.repeat(40)) + '\n';

    const velocityColor = metrics.velocity.daily > 0 ? chalk.green : chalk.gray;
    dashboard += `Daily Velocity:    ${velocityColor.bold(metrics.velocity.daily.toFixed(1))} points/day\n`;
    dashboard += `Tasks Completed:   ${chalk.cyan.bold(metrics.completed.count)}\n`;
    dashboard += `Avg Cycle Time:    ${chalk.green.bold(metrics.cycleTime.average.toFixed(1))} hours\n`;
    dashboard += `Work in Progress:  ${chalk.yellow.bold(metrics.workInProgress.count)} tasks\n\n`;

    // Progress bars
    dashboard += chalk.yellow.bold('📈 Progress Overview\n');
    dashboard += chalk.gray('─'.repeat(40)) + '\n';

    const totalTasks = metrics.completed.count + metrics.workInProgress.count;
    if (totalTasks > 0) {
      dashboard += `Completion: ${this.createProgressBar(metrics.completed.count, totalTasks, { width: 30 })}\n`;
    }

    if (metrics.estimates?.totalComplexity > 0) {
      const completedComplexity = metrics.completed.totalComplexity || 0;
      const totalComplexity = completedComplexity + metrics.estimates.totalComplexity;
      dashboard += `Complexity: ${this.createProgressBar(completedComplexity, totalComplexity, { width: 30 })}\n`;
    } else if (metrics.completed?.totalComplexity > 0) {
      // Fallback for when estimates are not available
      dashboard += `Completed Complexity: ${chalk.green.bold(metrics.completed.totalComplexity)} points\n`;
    }

    dashboard += '\n';

    // Trend visualization
    if (trend && trend.length > 0) {
      dashboard += this.createVelocityChart(trend, {
        title: 'Velocity Trend (Last 4 Weeks)',
        width: 50,
        height: 10
      });
    }

    // Cycle time distribution
    if (metrics.tasks && metrics.tasks.length > 0) {
      const cycleTimes = metrics.tasks
        .map(t => t.cycleTime)
        .filter(ct => ct !== null && ct > 0);

      if (cycleTimes.length > 0) {
        dashboard += this.createCycleTimeHistogram(cycleTimes, {
          title: 'Cycle Time Distribution',
          bins: 8,
          width: 50
        });
      }
    }

    dashboard += chalk.gray('═'.repeat(80)) + '\n';

    return dashboard;
  }

  /**
   * Create a simple table
   * @param {Array} data - Array of row objects
   * @param {Array} columns - Column definitions
   * @returns {string} ASCII table
   */
  createTable(data, columns) {
    if (!data || data.length === 0) {
      return chalk.gray('No data available');
    }

    // Calculate column widths
    const widths = columns.map(col => {
      const headerWidth = col.header.length;
      const dataWidth = Math.max(...data.map(row =>
        String(row[col.key] || '').length
      ));
      return Math.max(headerWidth, dataWidth, col.minWidth || 0);
    });

    let table = '';

    // Header
    let headerRow = '│';
    columns.forEach((col, i) => {
      const padding = ' '.repeat(widths[i] - col.header.length);
      headerRow += ` ${chalk.bold(col.header)}${padding} │`;
    });
    table += headerRow + '\n';

    // Separator
    let separator = '├';
    columns.forEach((col, i) => {
      separator += '─'.repeat(widths[i] + 2) + '┼';
    });
    separator = separator.slice(0, -1) + '┤';
    table += separator + '\n';

    // Data rows
    data.forEach(row => {
      let dataRow = '│';
      columns.forEach((col, i) => {
        const value = String(row[col.key] || '');
        const padding = ' '.repeat(widths[i] - value.length);
        const coloredValue = col.color ? col.color(value) : value;
        dataRow += ` ${coloredValue}${padding} │`;
      });
      table += dataRow + '\n';
    });

    return table;
  }
}

module.exports = VelocityVisualizer;
