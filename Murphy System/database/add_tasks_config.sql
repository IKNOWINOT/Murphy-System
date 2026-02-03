-- Add TASKS_v1 pack configuration for Acme Corp
INSERT INTO client_packs (client_id, pack_name, pack_version, enabled, enabled_at, enabled_by, created_at, updated_at)
VALUES (
    1, -- Acme Corp
    'TASKS_v1',
    '1.0.0',
    true,
    NOW(),
    1,
    NOW(),
    NOW()
) ON CONFLICT (client_id, pack_name) DO UPDATE SET
    enabled = true,
    enabled_at = NOW(),
    updated_at = NOW();

-- Add routing configuration for task types
INSERT INTO client_config (client_id, config_key, config_value, description, created_at, updated_at)
VALUES
    (1, 'tasks_routing_invoice', '{
        "destination_type": "email",
        "destination": "finance@acmecorp.com",
        "priority": "high"
    }'::jsonb, 'Invoice task routing', NOW(), NOW()),
    (1, 'tasks_routing_contract', '{
        "destination_type": "email",
        "destination": "legal@acmecorp.com",
        "priority": "critical"
    }'::jsonb, 'Contract task routing', NOW(), NOW()),
    (1, 'tasks_routing_support', '{
        "destination_type": "webhook",
        "destination": "https://support.acmecorp.com/api/tasks",
        "priority": "medium"
    }'::jsonb, 'Support task routing', NOW(), NOW())
ON CONFLICT (client_id, config_key) DO UPDATE SET
    config_value = EXCLUDED.config_value,
    updated_at = NOW();

-- Add additional team members for testing
INSERT INTO team_members (client_id, member_uuid, name, email, phone, skills, working_hours, max_concurrent_tasks, active, created_at, updated_at)
VALUES
    (1, gen_random_uuid(), 'Jane Doe', 'jane.doe@acmecorp.com', '+1-555-0101', '["invoice", "contract", "review"]'::jsonb, '{"start": "09:00", "end": "17:00"}'::jsonb, 5, true, NOW(), NOW()),
    (1, gen_random_uuid(), 'Bob Smith', 'bob.smith@acmecorp.com', '+1-555-0102', '["contract", "approval", "high_priority"]'::jsonb, '{"start": "09:00", "end": "17:00"}'::jsonb, 3, true, NOW(), NOW()),
    (1, gen_random_uuid(), 'Alice Johnson', 'alice.johnson@acmecorp.com', '+1-555-0103', '["support", "review", "documentation"]'::jsonb, '{"start": "08:00", "end": "16:00"}'::jsonb, 8, true, NOW(), NOW());

-- Insert sample tasks
INSERT INTO tasks (client_id, source_type, source_id, source_reference_id, title, description, priority, status, task_type, due_date, assigned_to, assigned_at, completed_at, cancelled_at, custom_fields, created_at, updated_at)
VALUES
    (1, 'manual', NULL, 'ref-001', 'Review Invoice INV-2025-001', 'Review and approve Q1 invoice from TechCorp', 'high', 'created', 'invoice', NOW() + INTERVAL '24 hours', NULL, NULL, NULL, NULL, NULL, NOW(), NOW()),
    (1, 'manual', NULL, 'ref-002', 'Update Service Contract', 'Renew annual service contract with TechStart', 'critical', 'created', 'contract', NOW() + INTERVAL '4 hours', NULL, NULL, NULL, NULL, NULL, NOW(), NOW()),
    (1, 'webhook', NULL, 'ticket-4567', 'Customer Support Ticket #4567', 'Resolve customer login issue', 'medium', 'created', 'support', NOW() + INTERVAL '72 hours', NULL, NULL, NULL, NULL, NULL, NOW(), NOW()),
    (1, 'manual', NULL, 'pay-003', 'Process Payment Request', 'Verify and process vendor payment', 'low', 'created', 'finance', NOW() + INTERVAL '168 hours', NULL, NULL, NULL, NULL, NULL, NOW(), NOW()),
    (1, 'manual', 1, 'doc-004', 'Update Documentation', 'Update API documentation for v2.0 release', 'medium', 'in_progress', 'documentation', NOW() + INTERVAL '48 hours', (SELECT member_id FROM team_members WHERE email = 'john.smith@acmecorp.com' LIMIT 1), NOW() - INTERVAL '2 hours', NULL, NULL, NULL, NOW() - INTERVAL '2 hours', NOW());

-- Assign some tasks manually for testing
INSERT INTO task_assignments (task_id, member_id, assignment_method, workload_at_assignment, assigned_at)
SELECT 
    t.task_id,
    tm.member_id,
    'manual',
    1,
    NOW()
FROM tasks t
CROSS JOIN team_members tm
WHERE t.title IN ('Update Documentation')
  AND tm.email = 'john.smith@acmecorp.com';

-- Insert a completed task for report testing
INSERT INTO tasks (client_id, source_type, source_id, source_reference_id, title, description, priority, status, task_type, due_date, assigned_to, assigned_at, completed_at, cancelled_at, custom_fields, created_at, updated_at)
VALUES
    (1, 'manual', NULL, NULL, 'Initial System Setup', 'Complete initial platform configuration', 'high', 'completed', 'setup', NOW() - INTERVAL '48 hours', (SELECT member_id FROM team_members WHERE email = 'john.smith@acmecorp.com' LIMIT 1), NOW() - INTERVAL '72 hours', NOW() - INTERVAL '24 hours', NULL, NULL, NOW() - INTERVAL '72 hours', NOW() - INTERVAL '24 hours');

-- Insert assignment for the completed task
INSERT INTO task_assignments (task_id, member_id, assignment_method, workload_at_assignment, assigned_at)
SELECT 
    (SELECT task_id FROM tasks WHERE title = 'Initial System Setup' ORDER BY task_id DESC LIMIT 1),
    (SELECT member_id FROM team_members WHERE email = 'john.smith@acmecorp.com' LIMIT 1),
    'manual',
    1,
    NOW() - INTERVAL '72 hours';

-- Insert SLA event for the completed task
INSERT INTO sla_events (task_id, client_id, sla_type, sla_threshold_minutes, triggered_at, escalated, escalation_level, escalation_recipients, notification_sent, notification_method, resolved_at, created_at, updated_at)
SELECT 
    (SELECT task_id FROM tasks WHERE title = 'Initial System Setup' ORDER BY task_id DESC LIMIT 1),
    1,
    'completion',
    2880, -- 48 hours in minutes
    NOW() - INTERVAL '24 hours',
    false,
    0,
    '[]'::jsonb,
    true,
    'email',
    NOW() - INTERVAL '24 hours',
    NOW() - INTERVAL '24 hours',
    NOW() - INTERVAL '24 hours';

-- Generate a sample report
INSERT INTO reports (client_id, report_type, report_format, report_period_start, report_period_end, file_path, status, generated_at, created_at, updated_at)
VALUES (
    1,
    'daily_task_summary',
    'html',
    NOW() - INTERVAL '7 days',
    NOW(),
    '/workspace/storage/reports/sample_report_001.html',
    'completed',
    NOW() - INTERVAL '1 hour',
    NOW() - INTERVAL '1 hour',
    NOW() - INTERVAL '1 hour'
);