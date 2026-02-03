#!/usr/bin/env python3
"""
Activate SECURITY_v1 workflows in n8n SQLite database
"""

import sqlite3
from datetime import datetime

def activate_workflow(conn, workflow_name):
    """Activate a workflow by name"""
    
    try:
        cursor = conn.cursor()
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        
        cursor.execute(
            "UPDATE workflow_entity SET active = true, updatedAt = ? WHERE name = ?",
            (now, workflow_name)
        )
        
        if cursor.rowcount > 0:
            conn.commit()
            cursor.close()
            return True
        else:
            print(f"✗ Workflow not found: {workflow_name}")
            cursor.close()
            return False
        
    except Exception as e:
        print(f"✗ Error activating {workflow_name}: {str(e)}")
        conn.rollback()
        return False

def main():
    """Main activation function"""
    
    print("=" * 60)
    print("SECURITY_v1 Workflows Activation")
    print("=" * 60)
    
    # Database connection
    try:
        conn = sqlite3.connect('/root/.n8n/database.sqlite')
        print("✓ Connected to n8n SQLite database")
    except Exception as e:
        print(f"✗ Database connection error: {str(e)}")
        return
    
    # List of SECURITY_v1 workflows to activate
    workflows = [
        "SECURITY_v1_Manage_Credentials",
        "SECURITY_v1_Validate_Configuration"
    ]
    
    # Activate each workflow
    success_count = 0
    for workflow_name in workflows:
        print(f"Activating: {workflow_name}")
        if activate_workflow(conn, workflow_name):
            print(f"✓ Activated: {workflow_name}")
            success_count += 1
        else:
            print(f"✗ Failed: {workflow_name}")
    
    conn.close()
    
    print("\n" + "=" * 60)
    print(f"Activation Complete: {success_count}/{len(workflows)} workflows")
    print("=" * 60)

if __name__ == "__main__":
    main()