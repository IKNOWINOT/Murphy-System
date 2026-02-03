#!/usr/bin/env python3
"""
Import MONITOR_v1 workflows into n8n SQLite database
"""

import json
import os
import sqlite3
from datetime import datetime
import uuid

# n8n SQLite database path
N8N_DB_PATH = os.getenv('N8N_DB_PATH', '/root/.n8n/database.sqlite')

def import_workflow(workflow_path, db_conn):
    """Import a single workflow from JSON file into n8n SQLite database"""
    
    with open(workflow_path, 'r') as f:
        workflow_data = json.load(f)
    
    workflow_name = workflow_data.get('name', 'Unknown')
    workflow_id = str(uuid.uuid4())
    active = False
    
    # Create workflow JSON structure for n8n
    workflow_json = {
        "name": workflow_name,
        "nodes": workflow_data.get('nodes', []),
        "connections": workflow_data.get('connections', {}),
        "settings": workflow_data.get('settings', {}),
        "staticData": workflow_data.get('staticData', None),
        "pinData": workflow_data.get('pinData', {}),
        "versionId": str(uuid.uuid4()),
        "id": workflow_id,
        "meta": {
            "instanceId": str(uuid.uuid4())
        },
        "active": active,
        "updatedAt": datetime.now().isoformat()
    }
    
    # Insert into n8n SQLite database
    cursor = db_conn.cursor()
    
    try:
        # Check if workflow already exists
        cursor.execute("SELECT id FROM workflow_entity WHERE name = ?", (workflow_name,))
        existing = cursor.fetchone()
        
        if existing:
            print(f"  ⚠️  Workflow '{workflow_name}' already exists, updating...")
            cursor.execute("""
                UPDATE workflow_entity 
                SET nodes = ?, connections = ?, settings = ?, 
                    staticData = ?, pinData = ?, 
                    versionId = ?, active = ?, updatedAt = ?
                WHERE name = ?
            """, (
                json.dumps(workflow_json.get('nodes', [])),
                json.dumps(workflow_json.get('connections', {})),
                json.dumps(workflow_json.get('settings', {})),
                json.dumps(workflow_json.get('staticData')),
                json.dumps(workflow_json.get('pinData', {})),
                str(uuid.uuid4()),
                active,
                datetime.now().isoformat(),
                workflow_name
            ))
        else:
            print(f"  ✅ Importing workflow: {workflow_name}")
            cursor.execute("""
                INSERT INTO workflow_entity 
                (id, name, nodes, connections, settings, staticData, pinData, versionId, active, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                workflow_id,
                workflow_name,
                json.dumps(workflow_json.get('nodes', [])),
                json.dumps(workflow_json.get('connections', {})),
                json.dumps(workflow_json.get('settings', {})),
                json.dumps(workflow_json.get('staticData')),
                json.dumps(workflow_json.get('pinData', {})),
                str(uuid.uuid4()),
                active,
                datetime.now().isoformat()
            ))
        
        db_conn.commit()
        return workflow_id
        
    except Exception as e:
        print(f"  ❌ Error importing workflow '{workflow_name}': {e}")
        db_conn.rollback()
        return None
    finally:
        cursor.close()

def main():
    """Main import function"""
    
    print("🚀 Starting MONITOR_v1 workflow import...\n")
    
    # Connect to n8n SQLite database
    try:
        conn = sqlite3.connect(N8N_DB_PATH)
        print(f"✅ Connected to n8n SQLite database: {N8N_DB_PATH}\n")
    except Exception as e:
        print(f"❌ Failed to connect to n8n database: {e}")
        return
    
    # Import all MONITOR_v1 workflows
    workflows_dir = '/workspace/workflows/monitor_v1'
    workflow_files = [
        'MONITOR_v1_Collect_Metrics.json',
        'MONITOR_v1_Process_Errors.json',
        'MONITOR_v1_Generate_Alerts.json'
    ]
    
    imported_workflows = []
    
    for workflow_file in workflow_files:
        workflow_path = os.path.join(workflows_dir, workflow_file)
        
        if not os.path.exists(workflow_path):
            print(f"❌ Workflow file not found: {workflow_path}")
            continue
        
        workflow_id = import_workflow(workflow_path, conn)
        if workflow_id:
            imported_workflows.append((workflow_file, workflow_id))
    
    conn.close()
    
    # Summary
    print("\n" + "="*60)
    print("📊 IMPORT SUMMARY")
    print("="*60)
    print(f"Total workflows imported: {len(imported_workflows)}")
    print("\nImported Workflows:")
    for filename, workflow_id in imported_workflows:
        print(f"  ✅ {filename} (ID: {workflow_id})")
    print("\n" + "="*60)
    print("✅ MONITOR_v1 workflow import complete!\n")
    
    print("📝 Next Steps:")
    print("   1. Run activate_monitor_workflows.py to activate workflows")
    print("   2. Test workflows in n8n UI")
    print("   3. Verify metrics collection in database")
    print("   4. Configure webhook endpoints for production use\n")

if __name__ == '__main__':
    main()