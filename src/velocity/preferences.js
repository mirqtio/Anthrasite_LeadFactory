/**
 * Velocity Preferences Manager
 * Manages user preferences for velocity tracking settings
 */

const fs = require('fs').promises;
const path = require('path');
const os = require('os');

class VelocityPreferences {
  constructor(configPath = null) {
    this.configPath = configPath || this.getDefaultConfigPath();
    this._cache = null;
  }

  /**
   * Get default configuration file path
   * @returns {string} Configuration file path
   */
  getDefaultConfigPath() {
    const homeDir = os.homedir();
    const configDir = path.join(homeDir, '.task-master');
    return path.join(configDir, 'velocity-preferences.json');
  }

  /**
   * Get default preferences
   * @returns {Object} Default preferences
   */
  getDefaultPreferences() {
    return {
      // Display preferences
      display: {
        showVelocityInList: true,
        showTrendIndicators: true,
        showEstimatedCompletion: true,
        defaultChartType: 'velocity', // velocity, burndown, cycle-time
        chartHeight: 10,
        useColors: true,
        compactMode: false
      },

      // Calculation preferences
      calculation: {
        workingHoursPerDay: 8,
        workingDaysPerWeek: 5,
        excludeWeekends: true,
        excludeHolidays: false,
        velocityPeriod: 'week', // week, month, sprint
        trendAnalysisPeriod: 4, // number of periods
        complexityScale: 'fibonacci', // fibonacci, linear, exponential
        autoEstimateComplexity: true
      },

      // Tracking preferences
      tracking: {
        autoStartTracking: true,
        trackBlockedTime: true,
        trackWaitTime: true,
        requireTimeEstimates: false,
        autoCompleteSubtasks: false,
        notifyOnLongRunningTasks: true,
        longRunningThresholdHours: 24
      },

      // Reporting preferences
      reporting: {
        defaultReportPeriod: 'week',
        includeSubtasks: true,
        includeBlockedTime: true,
        groupByPriority: false,
        groupByComplexity: false,
        exportFormat: 'json', // json, csv, markdown
        includeCharts: true
      },

      // Notification preferences
      notifications: {
        enabled: true,
        velocityAlerts: true,
        completionMilestones: true,
        trendWarnings: true,
        dailySummary: false,
        weeklySummary: true
      },

      // Integration preferences
      integration: {
        enhanceListCommand: true,
        enhanceSetStatusCommand: true,
        autoMigration: true,
        backupBeforeMigration: true,
        validateDataIntegrity: true
      },

      // Advanced preferences
      advanced: {
        cacheMetrics: true,
        cacheExpiryMinutes: 30,
        enableDebugLogging: false,
        enablePerformanceMetrics: false,
        maxHistoryDays: 365,
        dataRetentionDays: 730
      }
    };
  }

  /**
   * Get default preferences (creates a new copy each time)
   * @returns {Object} Default preferences
   */
  get defaultPreferences() {
    return this.getDefaultPreferences();
  }

  /**
   * Load preferences from file
   * @returns {Promise<Object>} User preferences
   */
  async load() {
    if (this._cache) {
      return this._cache;
    }

    try {
      // Ensure config directory exists
      await this.ensureConfigDirectory();

      // Try to read existing preferences
      const data = await fs.readFile(this.configPath, 'utf8');
      const userPreferences = JSON.parse(data);

      // Merge with defaults to ensure all properties exist
      this._cache = this.mergeWithDefaults(userPreferences);
      return this._cache;

    } catch (error) {
      if (error.code === 'ENOENT') {
        // File doesn't exist, create with defaults
        this._cache = { ...this.defaultPreferences };
        await this.save(this._cache);
        return this._cache;
      }
      throw error;
    }
  }

  /**
   * Save preferences to file
   * @param {Object} preferences - Preferences to save
   */
  async save(preferences = null) {
    const prefs = preferences || this._cache || this.defaultPreferences;

    try {
      await this.ensureConfigDirectory();
      await fs.writeFile(this.configPath, JSON.stringify(prefs, null, 2), 'utf8');
      this._cache = prefs;
    } catch (error) {
      throw new Error(`Failed to save preferences: ${error.message}`);
    }
  }

  /**
   * Get a specific preference value
   * @param {string} path - Dot-separated path to preference (e.g., 'display.showVelocityInList')
   * @returns {Promise<any>} Preference value
   */
  async get(path) {
    const preferences = await this.load();
    return this.getNestedValue(preferences, path);
  }

  /**
   * Set a specific preference value
   * @param {string} path - Dot-separated path to preference
   * @param {any} value - Value to set
   */
  async set(path, value) {
    const preferences = await this.load();
    this.setNestedValue(preferences, path, value);
    await this.save(preferences);
  }

  /**
   * Update multiple preferences
   * @param {Object} updates - Object with preference updates
   */
  async update(updates) {
    const preferences = await this.load();
    const updated = this.deepMerge(preferences, updates);
    await this.save(updated);
  }

  /**
   * Reset preferences to defaults
   * @param {Array<string>} sections - Optional array of sections to reset
   */
  async reset(sections = null) {
    if (sections) {
      // Load current preferences
      const preferences = await this.load();

      // Reset specified sections to defaults
      sections.forEach(section => {
        if (this.defaultPreferences[section]) {
          preferences[section] = JSON.parse(JSON.stringify(this.defaultPreferences[section]));
        }
      });

      // Clear cache and save
      this._cache = null;
      await this.save(preferences);
    } else {
      // Reset all preferences
      this._cache = JSON.parse(JSON.stringify(this.defaultPreferences));
      await this.save(this._cache);
    }
  }

  /**
   * Validate preferences structure
   * @param {Object} preferences - Preferences to validate
   * @returns {Array} Array of validation errors
   */
  validate(preferences) {
    const errors = [];

    // Validate working hours
    if (preferences.calculation?.workingHoursPerDay < 1 || preferences.calculation?.workingHoursPerDay > 24) {
      errors.push('Working hours per day must be between 1 and 24');
    }

    // Validate working days
    if (preferences.calculation?.workingDaysPerWeek < 1 || preferences.calculation?.workingDaysPerWeek > 7) {
      errors.push('Working days per week must be between 1 and 7');
    }

    // Validate trend analysis period
    if (preferences.calculation?.trendAnalysisPeriod < 2 || preferences.calculation?.trendAnalysisPeriod > 52) {
      errors.push('Trend analysis period must be between 2 and 52');
    }

    // Validate chart height
    if (preferences.display?.chartHeight < 5 || preferences.display?.chartHeight > 50) {
      errors.push('Chart height must be between 5 and 50');
    }

    // Validate retention days
    if (preferences.advanced?.dataRetentionDays < 30) {
      errors.push('Data retention must be at least 30 days');
    }

    return errors;
  }

  /**
   * Get preferences schema for documentation
   * @returns {Object} Preferences schema
   */
  getSchema() {
    return {
      display: {
        description: 'Display and visualization preferences',
        properties: {
          showVelocityInList: { type: 'boolean', description: 'Show velocity metrics in task list' },
          showTrendIndicators: { type: 'boolean', description: 'Show trend arrows and indicators' },
          showEstimatedCompletion: { type: 'boolean', description: 'Show estimated completion dates' },
          defaultChartType: { type: 'string', enum: ['velocity', 'burndown', 'cycle-time'], description: 'Default chart type for dashboard' },
          chartHeight: { type: 'number', min: 5, max: 50, description: 'Height of ASCII charts in lines' },
          useColors: { type: 'boolean', description: 'Use colors in terminal output' },
          compactMode: { type: 'boolean', description: 'Use compact display mode' }
        }
      },
      calculation: {
        description: 'Velocity calculation settings',
        properties: {
          workingHoursPerDay: { type: 'number', min: 1, max: 24, description: 'Working hours per day' },
          workingDaysPerWeek: { type: 'number', min: 1, max: 7, description: 'Working days per week' },
          excludeWeekends: { type: 'boolean', description: 'Exclude weekends from calculations' },
          excludeHolidays: { type: 'boolean', description: 'Exclude holidays from calculations' },
          velocityPeriod: { type: 'string', enum: ['week', 'month', 'sprint'], description: 'Default velocity calculation period' },
          trendAnalysisPeriod: { type: 'number', min: 2, max: 52, description: 'Number of periods for trend analysis' },
          complexityScale: { type: 'string', enum: ['fibonacci', 'linear', 'exponential'], description: 'Complexity scoring scale' },
          autoEstimateComplexity: { type: 'boolean', description: 'Automatically estimate task complexity' }
        }
      },
      tracking: {
        description: 'Task tracking behavior',
        properties: {
          autoStartTracking: { type: 'boolean', description: 'Automatically start tracking when task status changes' },
          trackBlockedTime: { type: 'boolean', description: 'Track time spent in blocked state' },
          trackWaitTime: { type: 'boolean', description: 'Track time spent waiting for dependencies' },
          requireTimeEstimates: { type: 'boolean', description: 'Require time estimates for new tasks' },
          autoCompleteSubtasks: { type: 'boolean', description: 'Auto-complete parent task when all subtasks done' },
          notifyOnLongRunningTasks: { type: 'boolean', description: 'Notify when tasks run longer than threshold' },
          longRunningThresholdHours: { type: 'number', min: 1, description: 'Hours threshold for long-running task alerts' }
        }
      }
    };
  }

  /**
   * Ensure configuration directory exists
   */
  async ensureConfigDirectory() {
    const configDir = path.dirname(this.configPath);
    try {
      await fs.mkdir(configDir, { recursive: true });
    } catch (error) {
      if (error.code !== 'EEXIST') {
        throw error;
      }
    }
  }

  /**
   * Merge user preferences with defaults
   * @param {Object} userPreferences - User preferences
   * @returns {Object} Merged preferences
   */
  mergeWithDefaults(userPreferences) {
    return this.deepMerge(this.defaultPreferences, userPreferences);
  }

  /**
   * Deep merge two objects
   * @param {Object} target - Target object
   * @param {Object} source - Source object
   * @returns {Object} Merged object
   */
  deepMerge(target, source) {
    const result = { ...target };

    for (const key in source) {
      if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
        result[key] = this.deepMerge(result[key] || {}, source[key]);
      } else {
        result[key] = source[key];
      }
    }

    return result;
  }

  /**
   * Get nested value from object using dot notation
   * @param {Object} obj - Object to search
   * @param {string} path - Dot-separated path
   * @returns {any} Value at path
   */
  getNestedValue(obj, path) {
    return path.split('.').reduce((current, key) => current?.[key], obj);
  }

  /**
   * Set nested value in object using dot notation
   * @param {Object} obj - Object to modify
   * @param {string} path - Dot-separated path
   * @param {any} value - Value to set
   */
  setNestedValue(obj, path, value) {
    const keys = path.split('.');
    const lastKey = keys.pop();
    const target = keys.reduce((current, key) => {
      if (!current[key] || typeof current[key] !== 'object') {
        current[key] = {};
      }
      return current[key];
    }, obj);
    target[lastKey] = value;
  }

  /**
   * Clear cache (useful for testing)
   */
  clearCache() {
    this._cache = null;
  }
}

module.exports = VelocityPreferences;
