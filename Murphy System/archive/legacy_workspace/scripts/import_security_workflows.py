#!/usr/bin/env python3
"""
Import SECURITY_v1 workflows into n8n SQLite database
"""

import json
import sqlite3
from datetime import datetime
import uuid

def import_workflow(conn, workflow_file_path):
    """Import a single workflow into n8n database"""
    
    # Read workflow file
    with open(workflow_file_path, 'r') as f:
        workflow_data = json.load(f)
    
    # Generate workflow ID if not present
    workflow_id = workflow_data.get('id')
    if not workflow_id:
        workflow_id = str(uuid.uuid4())
    
    # Prepare workflow data for database
    workflow_name = workflow_data.get('name')
    workflow_nodes = json.dumps(workflow_data.get('nodes', []))
    workflow_connections = json.dumps(workflow_data.get('connections', {}))
    workflow_settings = json.dumps(workflow_data.get('settings', {}))
    active = False  # Start inactive
    version_id = workflow_data.get('versionId', str(uuid.uuid4()))
    trigger_count = workflow_data.get('triggerCount', 1)
    static_data = json.dumps(workflow_data.get('staticData', None))
    pin_data = json.dumps(workflow_data.get('pinData', {}))
    meta = json.dumps(workflow_data.get('meta', None))
    description = workflow_data.get('description', None)
    
    try:
        cursor = conn.cursor()
        
        # Check if workflow already exists
        cursor.execute(
            "SELECT id, versionCounter FROM workflow_entity WHERE name = ?",
            (workflow_name,)
        )
        existing = cursor.fetchone()
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        
        if existing:
            # Update existing workflow
            existing_id, version_counter = existing
            cursor.execute(
                """UPDATE workflow_entity 
                   SET nodes = ?, connections = ?, settings = ?, active = ?, 
                       versionId = ?, updatedAt = ?, staticData = ?, pinData = ?, 
                       meta = ?, triggerCount = ?, versionCounter = versionCounter + 1
                   WHERE name = ?""",
                (
                    workflow_nodes,
                    workflow_connections,
                    workflow_settings,
                    active,
                    version_id,
                    now,
                    static_data,
                    pin_data,
                    meta,
                    trigger_count,
                    workflow_name
                )
            )
            print(f"✓ Updated workflow: {workflow_name}")
        else:
            # Insert new workflow
            cursor.execute(
                """INSERT INTO workflow_entity 
                   (id, name, active, nodes, connections, settings, staticData, pinData, 
                    versionId, triggerCount, meta, createdAt, updatedAt, isArchived, versionCounter, description)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    workflow_id,
                    workflow_name,
                    active,
                    workflow_nodes,
                    workflow_connections,
                    workflow_settings,
                    static_data,
                    pin_data,
                    version_id,
                    trigger_count,
                    meta,
                    now,
                    now,
                    False,
                    1,
                    description
                )
            )
            print(f"✓ Imported workflow: {workflow_name}")
        
        conn.commit()
        cursor.close()
        return True
        
    except Exception as e:
        print(f"✗ Error importing {workflow_name}: {str(e)}")
        conn.rollback()
        return False

def main():
    """Main import function"""
    
    print("=" * 60)
    print("SECURITY_v1 Workflows Import")
    print("=" * 60)
    
    # Database connection
    try:
        conn = sqlite3.connect('/root/.n8n/database.sqlite')
        print("✓ Connected to n8n SQLite database")
    except Exception as e:
        print(f"✗ Database connection error: {str(e)}")
        return
    
    # List of SECURITY_v1 workflows to import
    workflows = [
        "workflows/security_v1/SECURITY_v1_Manage_Credentials.json",
        "workflows/security_v1/SECURITY_v1_Validate_Configuration.json"
    ]
    
    # Import each workflow
    success_count = 0
    for workflow_file in workflows:
        if import_workflow(conn, workflow_file):
            success_count += 1
    
    conn.close()
    
    print("\n" + "=" * 60)
    print(f"Import Complete: {success_count}/{len(workflows)} workflows")
    print("=" * 60)

if __name__ == "__main__":
    main()