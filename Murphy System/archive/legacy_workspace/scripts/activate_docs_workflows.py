#!/usr/bin/env python3
"""
Script to activate DOCS_v1 workflows in n8n database.
"""

import sqlite3

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
    """Activate all DOCS_v1 workflows."""
    
    print("Activating DOCS_v1 workflows...")
    print("=" * 60)
    
    workflows = [
        "DOCS_v1_Intake_Docs",
        "DOCS_v1_Classify_Docs",
        "DOCS_v1_Extract_Data",
        "DOCS_v1_Validate_Data",
        "DOCS_v1_Route_Docs",
        "DOCS_v1_Human_Review_Queue"
    ]
    
    success_count = 0
    
    for workflow in workflows:
        if activate_workflow(workflow):
            success_count += 1
    
    print("=" * 60)
    print(f"Activated {success_count}/{len(workflows)} workflows")

if __name__ == "__main__":
    main()