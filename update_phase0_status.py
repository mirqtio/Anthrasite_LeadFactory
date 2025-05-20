#!/usr/bin/env python3
"""
Script to update all task and subtask statuses in the Phase 0 plan to 'completed'.
"""

import json

def update_statuses(file_path):
    # Read the JSON file
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    # Update status for all main tasks
    for task in data.get('tasks', []):
        task['status'] = 'completed'
        
        # Update status for all subtasks
        for subtask in task.get('subtasks', []):
            subtask['status'] = 'completed'
    
    # Write the updated data back to the file
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Successfully updated all task statuses in {file_path}")

if __name__ == "__main__":
    file_path = "tasks/leadfactory_phase0_plan.json"
    update_statuses(file_path)
