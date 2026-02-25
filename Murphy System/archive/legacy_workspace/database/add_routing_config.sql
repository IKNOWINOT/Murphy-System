-- Add routing configuration for Acme Corp
INSERT INTO client_config (client_id, pack_name, config_key, config_value, value_type, created_at, updated_at) 
VALUES 
(1, 'INTAKE_v1', 'routing_destinations', '[{"type": "webhook", "config": {"url": "https://example.com/webhook"}}]', 'json', NOW(), NOW()),
(1, 'INTAKE_v1', 'routing_min_score', '20', 'number', NOW(), NOW()),
(1, 'INTAKE_v1', 'routing_auto', 'true', 'boolean', NOW(), NOW());