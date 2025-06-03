#!/usr/bin/env node

/**
 * Enhanced List Command with Velocity Integration
 * Combines task-master list with velocity dashboard
 */

const { spawn } = require('child_process');
const { resolve } = require('path');

async function runCommand(command, args = [], options = {}) {
    return new Promise((resolve, reject) => {
        const child = spawn(command, args, {
            stdio: 'inherit',
            cwd: process.cwd(),
            ...options
        });

        child.on('close', (code) => {
            if (code === 0) {
                resolve();
            } else {
                reject(new Error(`Command failed with code ${code}`));
            }
        });
    });
}

async function enhancedList() {
    const args = process.argv.slice(2);

    try {
        console.log('📊 Task Master with Velocity Tracking\n');

        // First show velocity summary
        console.log('🚀 Velocity Summary:');
        await runCommand('node', [resolve(__dirname, '../src/velocity/cli.js'), 'summary']);

        console.log('\n📋 Task List:');
        // Then show regular task list
        await runCommand('task-master', ['list', ...args]);

        console.log('\n📈 Velocity Dashboard:');
        // Finally show velocity dashboard
        await runCommand('node', [resolve(__dirname, '../src/velocity/cli.js'), 'dashboard']);

    } catch (error) {
        console.error('Error running enhanced list:', error.message);
        process.exit(1);
    }
}

if (require.main === module) {
    enhancedList();
}

module.exports = enhancedList;
