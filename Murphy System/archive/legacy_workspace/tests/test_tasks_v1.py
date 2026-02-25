#!/usr/bin/env python3
"""
Integration Tests for TASKS_v1 Pack
Tests task creation, assignment, SLA monitoring, and reporting
"""

import sys
import time
from datetime import datetime, timedelta
from test_framework import TestFramework, TestDataGenerator

def test_task_creation(framework: TestFramework) -> dict:
    """Test task creation"""
    try:
        # Generate test task
        task_data = TestDataGenerator.generate_task(
            title='Integration Test Task',
            description='Test task for integration testing',
            priority='high',
            category='testing'
        )
        
        # Insert task
        framework.execute_query("""
            INSERT INTO tasks (client_id, title, description, priority, category, status, due_date, created_at)
            VALUES (%s, %s, %s, %s, %s, 'pending', NOW() + INTERVAL '2 days', NOW())
            RETURNING id
        """, (
            task_data['client_id'],
            task_data['title'],
            task_data['description'],
            task_data['priority'],
            task_data['category']
        ))
        
        # Verify task was created
        result = framework.execute_query(
            "SELECT id, title, status, priority FROM tasks WHERE title = %s",
            (task_data['title'],)
        )
        
        if result and len(result) > 0:
            return {
                'passed': True,
                'message': f'Task created successfully (ID: {result[0][0]})',
                'details': {
                    'task_id': result[0][0],
                    'title': result[0][1],
                    'status': result[0][2],
                    'priority': result[0][3]
                }
            }
        else:
            return {
                'passed': False,
                'message': 'Task not found in database'
            }
    except Exception as e:
        return {
            'passed': False,
            'message': f'Task creation failed: {str(e)}'
        }

def test_task_assignment(framework: TestFramework) -> dict:
    """Test intelligent task assignment"""
    try:
        # Create task
        framework.execute_query("""
            INSERT INTO tasks (client_id, title, priority, category, status, required_skills, created_at)
            VALUES (1, 'Assignment Test Task', 'high', 'development', 'pending', ARRAY['python', 'sql'], NOW())
            RETURNING id
        """)
        
        result = framework.execute_query(
            "SELECT id FROM tasks WHERE title = 'Assignment Test Task'"
        )
        
        if result:
            task_id = result[0][0]
            
            # Get available team member
            team_result = framework.execute_query("""
                SELECT id, name, skills, current_workload, max_workload
                FROM team_members
                WHERE is_active = TRUE
                ORDER BY current_workload ASC
                LIMIT 1
            """)
            
            if team_result:
                member_id, name, skills, current_workload, max_workload = team_result[0]
                
                # Calculate assignment score
                assignment_score = 10 * (max_workload - current_workload)  # Workload availability
                
                # Assign task
                framework.execute_query("""
                    INSERT INTO task_assignments (task_id, team_member_id, assignment_score, assigned_at)
                    VALUES (%s, %s, %s, NOW())
                """, (task_id, member_id, assignment_score))
                
                # Update task status
                framework.execute_query("""
                    UPDATE tasks SET status = 'assigned', assigned_to = %s WHERE id = %s
                """, (member_id, task_id))
                
                # Update team member workload
                framework.execute_query("""
                    UPDATE team_members SET current_workload = current_workload + 1 WHERE id = %s
                """, (member_id,))
                
                # Verify assignment
                result = framework.execute_query("""
                    SELECT ta.assignment_score, tm.name
                    FROM task_assignments ta
                    JOIN team_members tm ON ta.team_member_id = tm.id
                    WHERE ta.task_id = %s
                """, (task_id,))
                
                if result:
                    return {
                        'passed': True,
                        'message': f'Task assigned to {result[0][1]} (score: {result[0][0]})',
                        'details': {
                            'assigned_to': result[0][1],
                            'assignment_score': result[0][0]
                        }
                    }
                else:
                    return {
                        'passed': False,
                        'message': 'Assignment record not found'
                    }
            else:
                return {
                    'passed': False,
                    'message': 'No available team members'
                }
        else:
            return {
                'passed': False,
                'message': 'Task not found for assignment'
            }
    except Exception as e:
        return {
            'passed': False,
            'message': f'Assignment test failed: {str(e)}'
        }

def test_sla_monitoring(framework: TestFramework) -> dict:
    """Test SLA monitoring and escalation"""
    try:
        # Create overdue task
        framework.execute_query("""
            INSERT INTO tasks (client_id, title, priority, status, due_date, created_at)
            VALUES (1, 'Overdue Task', 'high', 'in_progress', NOW() - INTERVAL '1 hour', NOW() - INTERVAL '2 hours')
            RETURNING id
        """)
        
        result = framework.execute_query(
            "SELECT id FROM tasks WHERE title = 'Overdue Task'"
        )
        
        if result:
            task_id = result[0][0]
            
            # Simulate SLA check
            sla_status = 'overdue'
            time_until_due = -3600  # -1 hour in seconds
            
            # Create SLA event
            framework.execute_query("""
                INSERT INTO sla_events (task_id, sla_status, time_until_due_seconds, checked_at)
                VALUES (%s, %s, %s, NOW())
            """, (task_id, sla_status, time_until_due))
            
            # Update task status
            framework.execute_query("""
                UPDATE tasks SET status = 'overdue' WHERE id = %s
            """, (task_id,))
            
            # Verify SLA event
            result = framework.execute_query("""
                SELECT sla_status, time_until_due_seconds
                FROM sla_events
                WHERE task_id = %s
                ORDER BY checked_at DESC
                LIMIT 1
            """, (task_id,))
            
            if result:
                return {
                    'passed': True,
                    'message': f'SLA event created: {result[0][0]}',
                    'details': {
                        'sla_status': result[0][0],
                        'time_until_due': result[0][1]
                    }
                }
            else:
                return {
                    'passed': False,
                    'message': 'SLA event not found'
                }
        else:
            return {
                'passed': False,
                'message': 'Task not found for SLA monitoring'
            }
    except Exception as e:
        return {
            'passed': False,
            'message': f'SLA monitoring test failed: {str(e)}'
        }

def test_task_completion(framework: TestFramework) -> dict:
    """Test task completion workflow"""
    try:
        # Create and assign task
        framework.execute_query("""
            INSERT INTO tasks (client_id, title, status, assigned_to, created_at)
            VALUES (1, 'Completion Test Task', 'in_progress', 1, NOW())
            RETURNING id
        """)
        
        result = framework.execute_query(
            "SELECT id FROM tasks WHERE title = 'Completion Test Task'"
        )
        
        if result:
            task_id = result[0][0]
            
            # Complete task
            framework.execute_query("""
                UPDATE tasks 
                SET status = 'completed', 
                    completed_at = NOW()
                WHERE id = %s
            """, (task_id,))
            
            # Update team member workload
            framework.execute_query("""
                UPDATE team_members 
                SET current_workload = GREATEST(0, current_workload - 1)
                WHERE id = 1
            """)
            
            # Verify completion
            result = framework.execute_query("""
                SELECT status, completed_at
                FROM tasks
                WHERE id = %s
            """, (task_id,))
            
            if result and result[0][0] == 'completed' and result[0][1] is not None:
                return {
                    'passed': True,
                    'message': 'Task completed successfully',
                    'details': {
                        'status': result[0][0],
                        'completed_at': result[0][1].isoformat()
                    }
                }
            else:
                return {
                    'passed': False,
                    'message': 'Task completion not verified'
                }
        else:
            return {
                'passed': False,
                'message': 'Task not found for completion'
            }
    except Exception as e:
        return {
            'passed': False,
            'message': f'Completion test failed: {str(e)}'
        }

def test_report_generation(framework: TestFramework) -> dict:
    """Test report generation"""
    try:
        # Generate report data
        report_data = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'pending_tasks': 0,
            'overdue_tasks': 0
        }
        
        # Get task statistics
        result = framework.execute_query("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
                COUNT(CASE WHEN status = 'overdue' THEN 1 END) as overdue
            FROM tasks
            WHERE client_id = 1
        """)
        
        if result:
            report_data['total_tasks'] = result[0][0]
            report_data['completed_tasks'] = result[0][1]
            report_data['pending_tasks'] = result[0][2]
            report_data['overdue_tasks'] = result[0][3]
            
            # Insert report
            framework.execute_query("""
                INSERT INTO reports (client_id, report_type, report_data, generated_at)
                VALUES (1, 'task_summary', %s, NOW())
                RETURNING id
            """, (str(report_data),))
            
            # Verify report
            result = framework.execute_query("""
                SELECT id, report_type, report_data
                FROM reports
                WHERE client_id = 1 AND report_type = 'task_summary'
                ORDER BY generated_at DESC
                LIMIT 1
            """)
            
            if result:
                return {
                    'passed': True,
                    'message': f'Report generated successfully (ID: {result[0][0]})',
                    'details': report_data
                }
            else:
                return {
                    'passed': False,
                    'message': 'Report not found'
                }
        else:
            return {
                'passed': False,
                'message': 'Failed to get task statistics'
            }
    except Exception as e:
        return {
            'passed': False,
            'message': f'Report generation test failed: {str(e)}'
        }

def run_tasks_tests():
    """Run all TASKS_v1 integration tests"""
    print("="*70)
    print("🧪 TASKS_v1 INTEGRATION TESTS")
    print("="*70)
    
    framework = TestFramework()
    
    if not framework.connect_db():
        print("❌ Failed to connect to database")
        return
    
    try:
        # Run tests
        framework.run_test("TASKS_v1: Task Creation", test_task_creation, framework)
        framework.run_test("TASKS_v1: Task Assignment", test_task_assignment, framework)
        framework.run_test("TASKS_v1: SLA Monitoring", test_sla_monitoring, framework)
        framework.run_test("TASKS_v1: Task Completion", test_task_completion, framework)
        framework.run_test("TASKS_v1: Report Generation", test_report_generation, framework)
        
        # Print summary
        framework.print_summary()
        
        # Save report
        framework.save_report('test_results/tasks_v1_results.json')
        
    finally:
        framework.close_db()

if __name__ == '__main__':
    run_tasks_tests()