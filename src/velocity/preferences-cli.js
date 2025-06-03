#!/usr/bin/env node

/**
 * Velocity Preferences CLI
 * Command-line interface for managing velocity preferences
 */

const VelocityPreferences = require('./preferences');
const chalk = require('chalk');

class VelocityPreferencesCLI {
  constructor() {
    this.preferences = new VelocityPreferences();
  }

  /**
   * Show all preferences
   * @param {Object} options - Command options
   */
  async showPreferences(options = {}) {
    try {
      const prefs = await this.preferences.load();

      console.log(chalk.blue.bold('\n🔧 Velocity Tracking Preferences\n'));

      if (options.section) {
        this.displaySection(prefs[options.section], options.section);
      } else {
        Object.keys(prefs).forEach(section => {
          this.displaySection(prefs[section], section);
        });
      }

      console.log(chalk.gray('\nUse "velocity config set <key> <value>" to change settings'));
      console.log(chalk.gray('Use "velocity config reset" to restore defaults\n'));

    } catch (error) {
      console.error(chalk.red('❌ Error loading preferences:'), error.message);
    }
  }

  /**
   * Display a preferences section
   * @param {Object} section - Section data
   * @param {string} sectionName - Section name
   */
  displaySection(section, sectionName) {
    console.log(chalk.yellow.bold(`📋 ${this.formatSectionName(sectionName)}`));
    console.log(chalk.gray('─'.repeat(50)));

    Object.entries(section).forEach(([key, value]) => {
      const formattedKey = chalk.cyan(key.padEnd(25));
      const formattedValue = this.formatValue(value);
      console.log(`  ${formattedKey} ${formattedValue}`);
    });

    console.log('');
  }

  /**
   * Set a preference value
   * @param {string} key - Preference key (dot notation)
   * @param {string} value - New value
   * @param {Object} options - Command options
   */
  async setPreference(key, value, options = {}) {
    try {
      // Parse value based on type
      const parsedValue = this.parseValue(value);

      // Validate the key exists in schema
      const currentValue = await this.preferences.get(key);
      if (currentValue === undefined && !options.force) {
        console.error(chalk.red(`❌ Unknown preference key: ${key}`));
        console.log(chalk.gray('Use --force to set anyway, or use "velocity config list" to see available keys'));
        return;
      }

      // Set the value
      await this.preferences.set(key, parsedValue);

      console.log(chalk.green('✅ Preference updated successfully!'));
      console.log(`${chalk.cyan(key)}: ${this.formatValue(currentValue)} → ${this.formatValue(parsedValue)}`);

    } catch (error) {
      console.error(chalk.red('❌ Error setting preference:'), error.message);
    }
  }

  /**
   * Update multiple preferences from a file
   * @param {string} filePath - Path to JSON file with preferences
   */
  async updateFromFile(filePath) {
    try {
      const fs = require('fs').promises;
      const data = await fs.readFile(filePath, 'utf8');
      const updates = JSON.parse(data);

      // Validate updates
      const errors = this.preferences.validate(updates);
      if (errors.length > 0) {
        console.error(chalk.red('❌ Validation errors:'));
        errors.forEach(error => console.error(`  • ${error}`));
        return;
      }

      await this.preferences.update(updates);

      console.log(chalk.green('✅ Preferences updated from file successfully!'));
      console.log(`Updated preferences from: ${chalk.cyan(filePath)}`);

    } catch (error) {
      console.error(chalk.red('❌ Error updating from file:'), error.message);
    }
  }

  /**
   * Reset preferences to defaults
   * @param {Array<string>} sections - Sections to reset (optional)
   */
  async resetPreferences(sections = null) {
    try {
      if (sections && sections.length > 0) {
        await this.preferences.reset(sections);
        console.log(chalk.green('✅ Preference sections reset to defaults:'));
        sections.forEach(section => console.log(`  • ${chalk.cyan(section)}`));
      } else {
        await this.preferences.reset();
        console.log(chalk.green('✅ All preferences reset to defaults!'));
      }

    } catch (error) {
      console.error(chalk.red('❌ Error resetting preferences:'), error.message);
    }
  }

  /**
   * Export preferences to a file
   * @param {string} filePath - Output file path
   * @param {Object} options - Export options
   */
  async exportPreferences(filePath, options = {}) {
    try {
      const fs = require('fs').promises;
      const prefs = await this.preferences.load();

      let output;
      if (options.format === 'yaml') {
        // Simple YAML-like output
        output = this.toYaml(prefs);
      } else {
        output = JSON.stringify(prefs, null, 2);
      }

      await fs.writeFile(filePath, output, 'utf8');

      console.log(chalk.green('✅ Preferences exported successfully!'));
      console.log(`Exported to: ${chalk.cyan(filePath)}`);

    } catch (error) {
      console.error(chalk.red('❌ Error exporting preferences:'), error.message);
    }
  }

  /**
   * Show preferences schema/documentation
   */
  async showSchema() {
    const schema = this.preferences.getSchema();

    console.log(chalk.blue.bold('\n📖 Velocity Preferences Schema\n'));

    Object.entries(schema).forEach(([section, info]) => {
      console.log(chalk.yellow.bold(`📋 ${this.formatSectionName(section)}`));
      console.log(chalk.gray(info.description));
      console.log(chalk.gray('─'.repeat(50)));

      Object.entries(info.properties).forEach(([key, prop]) => {
        const fullKey = `${section}.${key}`;
        console.log(`  ${chalk.cyan(fullKey.padEnd(35))} ${chalk.gray(prop.description)}`);

        const constraints = [];
        if (prop.type) constraints.push(`type: ${prop.type}`);
        if (prop.enum) constraints.push(`values: ${prop.enum.join(', ')}`);
        if (prop.min !== undefined) constraints.push(`min: ${prop.min}`);
        if (prop.max !== undefined) constraints.push(`max: ${prop.max}`);

        if (constraints.length > 0) {
          console.log(`  ${' '.repeat(37)} ${chalk.gray(`(${constraints.join(', ')})`)}`);
        }
      });

      console.log('');
    });
  }

  /**
   * Validate current preferences
   */
  async validatePreferences() {
    try {
      const prefs = await this.preferences.load();
      const errors = this.preferences.validate(prefs);

      if (errors.length === 0) {
        console.log(chalk.green('✅ All preferences are valid!'));
      } else {
        console.log(chalk.red('❌ Validation errors found:'));
        errors.forEach(error => console.error(`  • ${error}`));
      }

    } catch (error) {
      console.error(chalk.red('❌ Error validating preferences:'), error.message);
    }
  }

  /**
   * Format section name for display
   * @param {string} name - Section name
   * @returns {string} Formatted name
   */
  formatSectionName(name) {
    return name.charAt(0).toUpperCase() + name.slice(1).replace(/([A-Z])/g, ' $1');
  }

  /**
   * Format value for display
   * @param {any} value - Value to format
   * @returns {string} Formatted value
   */
  formatValue(value) {
    if (typeof value === 'boolean') {
      return value ? chalk.green('✓ true') : chalk.red('✗ false');
    } else if (typeof value === 'string') {
      return chalk.green(`"${value}"`);
    } else if (typeof value === 'number') {
      return chalk.blue(value.toString());
    } else if (Array.isArray(value)) {
      return chalk.magenta(`[${value.join(', ')}]`);
    } else {
      return chalk.gray(JSON.stringify(value));
    }
  }

  /**
   * Parse string value to appropriate type
   * @param {string} value - String value
   * @returns {any} Parsed value
   */
  parseValue(value) {
    // Boolean values
    if (value === 'true') return true;
    if (value === 'false') return false;

    // Number values
    if (/^\d+$/.test(value)) return parseInt(value, 10);
    if (/^\d+\.\d+$/.test(value)) return parseFloat(value);

    // Array values (comma-separated)
    if (value.includes(',')) {
      return value.split(',').map(v => v.trim());
    }

    // String values
    return value;
  }

  /**
   * Convert object to simple YAML format
   * @param {Object} obj - Object to convert
   * @param {number} indent - Indentation level
   * @returns {string} YAML string
   */
  toYaml(obj, indent = 0) {
    const spaces = '  '.repeat(indent);
    let yaml = '';

    Object.entries(obj).forEach(([key, value]) => {
      if (typeof value === 'object' && !Array.isArray(value)) {
        yaml += `${spaces}${key}:\n`;
        yaml += this.toYaml(value, indent + 1);
      } else {
        yaml += `${spaces}${key}: ${JSON.stringify(value)}\n`;
      }
    });

    return yaml;
  }

  /**
   * Show help information
   */
  showHelp() {
    console.log(chalk.blue.bold('\n🔧 Velocity Preferences CLI\n'));

    console.log(chalk.yellow.bold('Commands:'));
    console.log('  list [--section=<name>]           Show all preferences or specific section');
    console.log('  get <key>                         Get a specific preference value');
    console.log('  set <key> <value> [--force]       Set a preference value');
    console.log('  update --file=<path>              Update preferences from JSON file');
    console.log('  reset [section1] [section2]...    Reset preferences to defaults');
    console.log('  export --file=<path> [--format=yaml]  Export preferences to file');
    console.log('  schema                            Show preferences schema');
    console.log('  validate                          Validate current preferences');
    console.log('  help                              Show this help');
    console.log('');

    console.log(chalk.yellow.bold('Examples:'));
    console.log(chalk.gray('  velocity config list'));
    console.log(chalk.gray('  velocity config list --section=display'));
    console.log(chalk.gray('  velocity config set display.useColors false'));
    console.log(chalk.gray('  velocity config set calculation.workingHoursPerDay 7'));
    console.log(chalk.gray('  velocity config reset display calculation'));
    console.log(chalk.gray('  velocity config export --file=my-prefs.json'));
    console.log('');
  }
}

// CLI entry point
async function main() {
  const cli = new VelocityPreferencesCLI();
  const args = process.argv.slice(2);

  if (args.length === 0) {
    await cli.showPreferences();
    return;
  }

  const command = args[0];
  const options = {};

  // Parse options
  args.forEach(arg => {
    if (arg.startsWith('--')) {
      const [key, value] = arg.substring(2).split('=');
      options[key] = value || true;
    }
  });

  try {
    switch (command) {
      case 'list':
        await cli.showPreferences(options);
        break;
      case 'get':
        if (args[1]) {
          const value = await cli.preferences.get(args[1]);
          console.log(`${chalk.cyan(args[1])}: ${cli.formatValue(value)}`);
        } else {
          console.error(chalk.red('❌ Key required for get command'));
        }
        break;
      case 'set':
        if (args[1] && args[2]) {
          await cli.setPreference(args[1], args[2], options);
        } else {
          console.error(chalk.red('❌ Key and value required for set command'));
        }
        break;
      case 'update':
        if (options.file) {
          await cli.updateFromFile(options.file);
        } else {
          console.error(chalk.red('❌ --file option required for update command'));
        }
        break;
      case 'reset':
        const sections = args.slice(1).filter(arg => !arg.startsWith('--'));
        await cli.resetPreferences(sections.length > 0 ? sections : null);
        break;
      case 'export':
        if (options.file) {
          await cli.exportPreferences(options.file, options);
        } else {
          console.error(chalk.red('❌ --file option required for export command'));
        }
        break;
      case 'schema':
        await cli.showSchema();
        break;
      case 'validate':
        await cli.validatePreferences();
        break;
      case 'help':
      default:
        cli.showHelp();
        break;
    }
  } catch (error) {
    console.error(chalk.red('❌ Command failed:'), error.message);
    process.exit(1);
  }
}

// Export for testing
module.exports = VelocityPreferencesCLI;

// Run CLI if called directly
if (require.main === module) {
  main().catch(console.error);
}
