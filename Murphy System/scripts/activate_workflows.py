#!/usr/bin/env python3
"""
Script to activate n8n workflows in the database.
"""

import sqlite3
import json

N8N_DB_PATH = "/root/.n8n/database.sqlite"

def activate_workflow(workflow_name):
    """Activate a specific workflow by name."""
    
    conn = sqlite3.connect(N8N_DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Update workflow to active
        cursor.execute('''
            UPDATE workflow_entity 
            SET active = 1, updatedAt = datetime('now')
            WHERE name = ?
        ''', (workflow_name,))
        
        if cursor.rowcount > 0:
            print(f"✓ Activated: {workflow_name}")
            return True
        else:
            print(f"✗ Not found: {workflow_name}")
            return False
            
    except Exception as e:
        print(f"✗ Error activating {workflow_name}: {str(e)}")
        return False
    finally:
        conn.commit()
        conn.close()

def main():
    """Activate all INTAKE_v1 workflows."""
    
    print("Activating INTAKE_v1 workflows...")
    print("=" * 60)
    
    workflows = [
        "INTAKE_v1_Capture_Leads",
        "INTAKE_v1_Normalize_Data",
        "INTAKE_v1_Enrich_Leads",
        "INTAKE_v1_Route_Leads",
        "INTAKE_v1_DLQ_Processor"
    ]
    
    success_count = 0
    
    for workflow in workflows:
        if activate_workflow(workflow):
            success_count += 1
    
    print("=" * 60)
    print(f"Activated {success_count}/{len(workflows)} workflows")
    print("\nNote: Webhook workflows may take a few seconds to register")
    print("      after activation. You may need to wait 10-15 seconds")
    print("      before testing the webhook endpoint.")

if __name__ == "__main__":
    main()