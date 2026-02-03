-- Add TASKS_v1 pack configuration for Acme Corp
INSERT INTO client_packs (client_id, pack_name, pack_version, enabled, enabled_at, enabled_by, created_at, updated_at)
VALUES (
    1, 
    'TASKS_v1',
    '1.0.0',
    true,
    NOW(),
    1,
    NOW(),
    NOW()
)
ON CONFLICT (client_id, pack_name) 
DO UPDATE SET enabled = true, enabled_at = NOW(), updated_at = NOW();

-- Insert sample tasks (only new ones)
INSERT INTO tasks (client_id, source_type, source_id, source_reference_id, title, description, priority, status, task_type, due_date, created_at, updated_at)
VALUES
    (1, 'manual', NULL, 'ref-001', 'Review Invoice INV-2025-001', 'Review and approve Q1 invoice from TechCorp', 'high', 'created', 'invoice', NOW() + INTERVAL '24 hours', NOW(), NOW()),
    (1, 'manual', NULL, 'ref-002', 'Update Service Contract', 'Renew annual service contract with TechStart', 'critical', 'created', 'contract', NOW() + INTERVAL '4 hours', NOW(), NOW()),
    (1, 'webhook', NULL, 'ticket-4567', 'Customer Support Ticket #4567', 'Resolve customer login issue', 'medium', 'created', 'support', NOW() + INTERVAL '72 hours', NOW(), NOW()),
    (1, 'manual', NULL, 'pay-003', 'Process Payment Request', 'Verify and process vendor payment', 'low', 'created', 'finance', NOW() + INTERVAL '168 hours', NOW(), NOW()),
    (1, 'manual', 1, 'doc-004', 'Update Documentation', 'Update API documentation for v2.0 release', 'medium', 'in_progress', 'documentation', NOW() + INTERVAL '48 hours', NOW() - INTERVAL '2 hours', NOW() - INTERVAL '2 hours');

-- Assign the documentation task to John Smith
INSERT INTO task_assignments (task_id, member_id, assignment_method, workload_at_assignment, assigned_at)
SELECT 
    t.task_id,
    tm.member_id,
    'manual',
    1,
    NOW() - INTERVAL '2 hours'
FROM tasks t
CROSS JOIN team_members tm
WHERE t.title = 'Update Documentation'
  AND tm.email = 'john.smith@acmecorp.com';

-- Update the task with assignment
UPDATE tasks 
SET assigned_to = (SELECT member_id FROM team_members WHERE email = 'john.smith@acmecorp.com' LIMIT 1),
    assigned_at = NOW() - INTERVAL '2 hours'
WHERE title = 'Update Documentation';

-- Insert a completed task
INSERT INTO tasks (client_id, source_type, source_id, source_reference_id, title, description, priority, status, task_type, due_date, assigned_to, assigned_at, completed_at, created_at, updated_at)
VALUES
    (1, 'manual', NULL, NULL, 'Initial System Setup', 'Complete initial platform configuration', 'high', 'completed', 'setup', NOW() - INTERVAL '48 hours', (SELECT member_id FROM team_members WHERE email = 'john.smith@acmecorp.com' LIMIT 1), NOW() - INTERVAL '72 hours', NOW() - INTERVAL '24 hours', NOW() - INTERVAL '72 hours', NOW() - INTERVAL '24 hours');

-- Insert assignment for completed task
INSERT INTO task_assignments (task_id, member_id, assignment_method, workload_at_assignment, assigned_at)
SELECT 
    (SELECT task_id FROM tasks WHERE title = 'Initial System Setup' ORDER BY task_id DESC LIMIT 1),
    (SELECT member_id FROM team_members WHERE email = 'john.smith@acmecorp.com' LIMIT 1),
    'manual',
    1,
    NOW() - INTERVAL '72 hours';

-- Insert SLA event
INSERT INTO sla_events (task_id, client_id, sla_type, sla_threshold_minutes, triggered_at, escalated, escalation_level, escalation_recipients, notification_sent, notification_method, resolved_at, created_at)
SELECT 
    (SELECT task_id FROM tasks WHERE title = 'Initial System Setup' ORDER BY task_id DESC LIMIT 1),
    1,
    'completion',
    2880,
    NOW() - INTERVAL '24 hours',
    false,
    0,
    '[]'::jsonb,
    true,
    'email',
    NOW() - INTERVAL '24 hours',
    NOW() - INTERVAL '24 hours';

-- Generate sample report
INSERT INTO reports (client_id, report_type, report_format, report_period_start, report_period_end, file_path, status, generated_at, created_at)
VALUES (
    1,
    'daily_task_summary',
    'html',
    NOW() - INTERVAL '7 days',
    NOW(),
    '/workspace/storage/reports/sample_report_001.html',
    'completed',
    NOW() - INTERVAL '1 hour',
    NOW() - INTERVAL '1 hour'
);

-- Verify data
SELECT 'TASKS_v1 Pack Configuration' as info, * FROM client_packs WHERE client_id = 1 AND pack_name = 'TASKS_v1';
SELECT 'Sample Tasks' as info, task_id, title, status, priority, task_type FROM tasks WHERE client_id = 1 ORDER BY task_id DESC LIMIT 6;
SELECT 'Task Assignments' as info, ta.*, tm.name FROM task_assignments ta JOIN team_members tm ON ta.member_id = tm.member_id ORDER BY ta.assignment_id DESC LIMIT 3;
SELECT 'SLA Events' as info, * FROM sla_events ORDER BY sla_event_id DESC LIMIT 1;
SELECT 'Reports' as info, * FROM reports ORDER BY report_id DESC LIMIT 1;