#!/usr/bin/env python3
"""
Script to import n8n workflows from JSON files directly into SQLite database.
"""

import sqlite3
import json
import os
from datetime import datetime
import uuid

# n8n database path
N8N_DB_PATH = "/root/.n8n/database.sqlite"

# Workflow files directory
WORKFLOWS_DIR = "/workspace/workflows/intake_v1"

def import_workflow(db_path, workflow_file):
    """Import a single workflow into n8n database."""
    
    # Read workflow JSON
    with open(workflow_file, 'r') as f:
        workflow_data = json.load(f)
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Get current timestamp
        now = datetime.utcnow().isoformat() + 'Z'
        
        # Generate IDs
        workflow_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())
        
        # Prepare workflow data
        workflow_name = workflow_data.get('name', 'Unknown')
        nodes_json = json.dumps(workflow_data.get('nodes', []))
        connections_json = json.dumps(workflow_data.get('connections', {}))
        settings_json = json.dumps(workflow_data.get('settings', {}))
        static_data_json = json.dumps(workflow_data.get('static_data', None))
        pin_data_json = json.dumps(workflow_data.get('pinData', {}))
        tags_json = json.dumps(workflow_data.get('tags', []))
        
        # Insert workflow
        cursor.execute('''
            INSERT INTO workflow_entity (
                id, 
                name, 
                active, 
                nodes, 
                connections, 
                settings, 
                staticData, 
                pinData, 
                versionId, 
                triggerCount, 
                createdAt, 
                updatedAt, 
                versionCounter
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            workflow_id,
            workflow_name,
            False,  # inactive by default
            nodes_json,
            connections_json,
            settings_json,
            static_data_json,
            pin_data_json,
            version_id,
            workflow_data.get('triggerCount', 0),
            now,
            now,
            1
        ))
        
        conn.commit()
        
        print(f"✓ Successfully imported: {workflow_name}")
        print(f"  Workflow ID: {workflow_id}")
        print(f"  Version ID: {version_id}")
        print()
        
        return True, workflow_id
        
    except Exception as e:
        conn.rollback()
        print(f"✗ Failed to import {workflow_file}: {str(e)}")
        return False, None
        
    finally:
        conn.close()

def main():
    """Main function to import all workflows."""
    
    print("Importing n8n workflows from JSON files...")
    print(f"Database: {N8N_DB_PATH}")
    print(f"Workflows directory: {WORKFLOWS_DIR}")
    print("=" * 60)
    print()
    
    # Check if database exists
    if not os.path.exists(N8N_DB_PATH):
        print(f"Error: n8n database not found at {N8N_DB_PATH}")
        return 1
    
    # Check if workflows directory exists
    if not os.path.exists(WORKFLOWS_DIR):
        print(f"Error: Workflows directory not found at {WORKFLOWS_DIR}")
        return 1
    
    # Get all workflow JSON files
    workflow_files = [
        os.path.join(WORKFLOWS_DIR, f) 
        for f in os.listdir(WORKFLOWS_DIR) 
        if f.endswith('.json')
    ]
    
    if not workflow_files:
        print("No workflow JSON files found")
        return 1
    
    # Import each workflow
    success_count = 0
    fail_count = 0
    
    for workflow_file in sorted(workflow_files):
        success, workflow_id = import_workflow(N8N_DB_PATH, workflow_file)
        if success:
            success_count += 1
        else:
            fail_count += 1
    
    # Summary
    print("=" * 60)
    print(f"Import complete: {success_count} successful, {fail_count} failed")
    
    return 0 if fail_count == 0 else 1

if __name__ == "__main__":
    exit(main())