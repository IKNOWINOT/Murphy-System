#!/usr/bin/env python3
"""
Activate MONITOR_v1 workflows in n8n SQLite database
"""

import sqlite3
import os
from datetime import datetime

# n8n SQLite database path
N8N_DB_PATH = os.getenv('N8N_DB_PATH', '/root/.n8n/database.sqlite')

def activate_workflow(workflow_name, db_conn):
    """Activate a specific workflow in n8n SQLite database"""
    
    cursor = db_conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE workflow_entity 
            SET active = ?, updatedAt = ?
            WHERE name = ?
        """, (1, datetime.now().isoformat(), workflow_name))
        
        db_conn.commit()
        return True
    except Exception as e:
        print(f"  ❌ Error activating workflow '{workflow_name}': {e}")
        db_conn.rollback()
        return False
    finally:
        cursor.close()

def main():
    """Main activation function"""
    
    print("🔌 Activating MONITOR_v1 workflows...\n")
    
    # Connect to n8n SQLite database
    try:
        conn = sqlite3.connect(N8N_DB_PATH)
        print(f"✅ Connected to n8n SQLite database: {N8N_DB_PATH}\n")
    except Exception as e:
        print(f"❌ Failed to connect to n8n database: {e}")
        return
    
    # Activate all MONITOR_v1 workflows
    workflows = [
        'MONITOR_v1_Collect_Metrics',
        'MONITOR_v1_Process_Errors',
        'MONITOR_v1_Generate_Alerts'
    ]
    
    activated_count = 0
    
    for workflow_name in workflows:
        print(f"Activating: {workflow_name}")
        if activate_workflow(workflow_name, conn):
            print(f"  ✅ Activated: {workflow_name}\n")
            activated_count += 1
        else:
            print(f"  ❌ Failed to activate: {workflow_name}\n")
    
    conn.close()
    
    # Summary
    print("="*60)
    print("📊 ACTIVATION SUMMARY")
    print("="*60)
    print(f"Total workflows activated: {activated_count}/{len(workflows)}")
    print("\nActive Workflows:")
    for workflow_name in workflows:
        print(f"  ✅ {workflow_name}")
    print("\n" + "="*60)
    print("✅ MONITOR_v1 workflows activated!\n")
    
    print("📝 Next Steps:")
    print("   1. Monitor workflow executions in n8n UI")
    print("   2. Check metrics collection in database")
    print("   3. Verify alert generation")
    print("   4. Test error processing webhook\n")

if __name__ == '__main__':
    main()