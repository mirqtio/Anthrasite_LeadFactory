/**
 * Velocity Preferences Test Suite
 * Tests for the velocity preferences system
 */

const VelocityPreferences = require('./preferences');
const VelocityPreferencesCLI = require('./preferences-cli');
const fs = require('fs').promises;
const path = require('path');
const os = require('os');

class VelocityPreferencesTest {
  constructor() {
    this.testConfigPath = path.join(os.tmpdir(), 'test-velocity-preferences.json');
    this.preferences = new VelocityPreferences(this.testConfigPath);
    this.cli = new VelocityPreferencesCLI();
    this.cli.preferences = this.preferences; // Use test instance
  }

  /**
   * Run all tests
   */
  async runAllTests() {
    console.log('🧪 Running Velocity Preferences Tests\n');

    const tests = [
      this.testDefaultPreferences,
      this.testLoadAndSave,
      this.testGetAndSet,
      this.testNestedValues,
      this.testValidation,
      this.testReset,
      this.testMerging,
      this.testCLICommands
    ];

    let passed = 0;
    let failed = 0;

    for (const test of tests) {
      try {
        await this.cleanup();
        await test.call(this);
        console.log(`✅ ${test.name} - PASSED`);
        passed++;
      } catch (error) {
        console.error(`❌ ${test.name} - FAILED: ${error.message}`);
        failed++;
      }
    }

    await this.cleanup();

    console.log(`\n📊 Test Results: ${passed} passed, ${failed} failed`);
    return failed === 0;
  }

  /**
   * Test default preferences loading
   */
  async testDefaultPreferences() {
    const prefs = await this.preferences.load();

    // Check that all required sections exist
    const requiredSections = ['display', 'calculation', 'tracking', 'reporting', 'notifications', 'integration', 'advanced'];
    requiredSections.forEach(section => {
      if (!prefs[section]) {
        throw new Error(`Missing required section: ${section}`);
      }
    });

    // Check some specific default values
    if (prefs.display.showVelocityInList !== true) {
      throw new Error('Default showVelocityInList should be true');
    }

    if (prefs.calculation.workingHoursPerDay !== 8) {
      throw new Error('Default workingHoursPerDay should be 8');
    }

    if (prefs.calculation.velocityPeriod !== 'week') {
      throw new Error('Default velocityPeriod should be week');
    }
  }

  /**
   * Test loading and saving preferences
   */
  async testLoadAndSave() {
    // Load defaults
    const prefs1 = await this.preferences.load();

    // Modify a value
    prefs1.display.chartHeight = 20;

    // Save
    await this.preferences.save(prefs1);

    // Clear cache and reload
    this.preferences.clearCache();
    const prefs2 = await this.preferences.load();

    if (prefs2.display.chartHeight !== 20) {
      throw new Error('Saved preference not persisted correctly');
    }
  }

  /**
   * Test get and set methods
   */
  async testGetAndSet() {
    // Test getting a nested value
    const chartHeight = await this.preferences.get('display.chartHeight');
    if (typeof chartHeight !== 'number') {
      throw new Error('Failed to get nested preference value');
    }

    // Test setting a nested value
    await this.preferences.set('display.useColors', false);
    const useColors = await this.preferences.get('display.useColors');
    if (useColors !== false) {
      throw new Error('Failed to set nested preference value');
    }

    // Test setting a deep nested value
    await this.preferences.set('calculation.workingHoursPerDay', 6);
    const workingHours = await this.preferences.get('calculation.workingHoursPerDay');
    if (workingHours !== 6) {
      throw new Error('Failed to set deep nested preference value');
    }
  }

  /**
   * Test nested value operations
   */
  async testNestedValues() {
    const prefs = await this.preferences.load();

    // Test getNestedValue
    const value1 = this.preferences.getNestedValue(prefs, 'display.chartHeight');
    if (typeof value1 !== 'number') {
      throw new Error('getNestedValue failed');
    }

    // Test setNestedValue
    this.preferences.setNestedValue(prefs, 'display.newProperty', 'test');
    if (prefs.display.newProperty !== 'test') {
      throw new Error('setNestedValue failed');
    }

    // Test deep nesting
    this.preferences.setNestedValue(prefs, 'new.deep.property', 'value');
    if (prefs.new?.deep?.property !== 'value') {
      throw new Error('Deep setNestedValue failed');
    }
  }

  /**
   * Test preference validation
   */
  async testValidation() {
    const prefs = await this.preferences.load();

    // Test valid preferences
    let errors = this.preferences.validate(prefs);
    if (errors.length > 0) {
      throw new Error(`Default preferences should be valid, but got errors: ${errors.join(', ')}`);
    }

    // Test invalid working hours
    prefs.calculation.workingHoursPerDay = 25;
    errors = this.preferences.validate(prefs);
    if (errors.length === 0) {
      throw new Error('Should have validation error for invalid working hours');
    }

    // Test invalid chart height
    prefs.calculation.workingHoursPerDay = 8; // Fix previous error
    prefs.display.chartHeight = 100;
    errors = this.preferences.validate(prefs);
    if (errors.length === 0) {
      throw new Error('Should have validation error for invalid chart height');
    }
  }

  /**
   * Test reset functionality
   */
  async testReset() {
    // Modify some preferences
    await this.preferences.set('display.useColors', false);
    await this.preferences.set('calculation.workingHoursPerDay', 6);

    // Verify changes were made
    let useColors = await this.preferences.get('display.useColors');
    let workingHours = await this.preferences.get('calculation.workingHoursPerDay');

    if (useColors !== false || workingHours !== 6) {
      throw new Error('Initial preference changes not applied correctly');
    }

    // Reset display section only
    await this.preferences.reset(['display']);

    useColors = await this.preferences.get('display.useColors');
    workingHours = await this.preferences.get('calculation.workingHoursPerDay');

    if (useColors !== true) {
      throw new Error(`Display section not reset correctly: expected true, got ${useColors}`);
    }

    if (workingHours !== 6) {
      throw new Error('Calculation section should not have been reset');
    }

    // Reset all preferences
    await this.preferences.reset();

    const resetWorkingHours = await this.preferences.get('calculation.workingHoursPerDay');
    if (resetWorkingHours !== 8) {
      throw new Error('All preferences not reset correctly');
    }
  }

  /**
   * Test deep merging
   */
  async testMerging() {
    const target = {
      a: { b: 1, c: 2 },
      d: 3
    };

    const source = {
      a: { b: 10, e: 4 },
      f: 5
    };

    const merged = this.preferences.deepMerge(target, source);

    if (merged.a.b !== 10) {
      throw new Error('Deep merge failed: overwrite not working');
    }

    if (merged.a.c !== 2) {
      throw new Error('Deep merge failed: existing value lost');
    }

    if (merged.a.e !== 4) {
      throw new Error('Deep merge failed: new value not added');
    }

    if (merged.d !== 3) {
      throw new Error('Deep merge failed: root value lost');
    }

    if (merged.f !== 5) {
      throw new Error('Deep merge failed: new root value not added');
    }
  }

  /**
   * Test CLI commands
   */
  async testCLICommands() {
    // Test value parsing
    if (this.cli.parseValue('true') !== true) {
      throw new Error('CLI parseValue failed for boolean true');
    }

    if (this.cli.parseValue('false') !== false) {
      throw new Error('CLI parseValue failed for boolean false');
    }

    if (this.cli.parseValue('123') !== 123) {
      throw new Error('CLI parseValue failed for integer');
    }

    if (this.cli.parseValue('12.5') !== 12.5) {
      throw new Error('CLI parseValue failed for float');
    }

    if (this.cli.parseValue('hello') !== 'hello') {
      throw new Error('CLI parseValue failed for string');
    }

    const arrayResult = this.cli.parseValue('a,b,c');
    if (!Array.isArray(arrayResult) || arrayResult.length !== 3) {
      throw new Error('CLI parseValue failed for array');
    }

    // Test value formatting
    const formattedTrue = this.cli.formatValue(true);
    if (!formattedTrue.includes('true')) {
      throw new Error('CLI formatValue failed for boolean');
    }

    const formattedNumber = this.cli.formatValue(42);
    if (!formattedNumber.includes('42')) {
      throw new Error('CLI formatValue failed for number');
    }
  }

  /**
   * Clean up test files
   */
  async cleanup() {
    try {
      await fs.unlink(this.testConfigPath);
    } catch (error) {
      // File might not exist, ignore
    }
    this.preferences.clearCache();
  }
}

// Demo function to show preferences in action
async function demonstratePreferences() {
  console.log('🎨 Velocity Preferences Demo\n');

  const prefs = new VelocityPreferences();

  // Show current chart height
  const chartHeight = await prefs.get('display.chartHeight');
  console.log(`Current chart height: ${chartHeight}`);

  // Change chart height
  await prefs.set('display.chartHeight', 20);
  console.log('Changed chart height to 20');

  // Show working hours
  const workingHours = await prefs.get('calculation.workingHoursPerDay');
  console.log(`Working hours per day: ${workingHours}`);

  // Update multiple preferences
  await prefs.update({
    display: { useColors: false, compactMode: true },
    calculation: { velocityPeriod: 'month' }
  });
  console.log('Updated multiple preferences');

  // Show final state
  const finalPrefs = await prefs.load();
  console.log('\nFinal preferences:');
  console.log(`- Chart height: ${finalPrefs.display.chartHeight}`);
  console.log(`- Use colors: ${finalPrefs.display.useColors}`);
  console.log(`- Compact mode: ${finalPrefs.display.compactMode}`);
  console.log(`- Velocity period: ${finalPrefs.calculation.velocityPeriod}`);
}

// Export for use in other modules or run directly
module.exports = { VelocityPreferencesTest, demonstratePreferences };

// Run tests if called directly
if (require.main === module) {
  const runTests = process.argv.includes('--test');
  const runDemo = process.argv.includes('--demo');

  if (runTests) {
    const test = new VelocityPreferencesTest();
    test.runAllTests().then(success => {
      process.exit(success ? 0 : 1);
    }).catch(console.error);
  } else if (runDemo) {
    demonstratePreferences().catch(console.error);
  } else {
    console.log('Usage:');
    console.log('  node preferences-test.js --test   # Run tests');
    console.log('  node preferences-test.js --demo   # Run demo');
  }
}
