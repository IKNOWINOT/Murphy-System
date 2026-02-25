-- Add document routing configuration for Acme Corp
INSERT INTO client_config (client_id, pack_name, config_key, config_value, value_type, created_at, updated_at) 
VALUES 
(1, 'DOCS_v1', 'routing_destinations', '[{"type": "storage", "config": {"path": "/storage/processed/acme-corp"}}]', 'json', NOW(), NOW()),
(1, 'DOCS_v1', 'category_mappings', '{"invoice": [{"type": "email", "config": {"recipient": "finance@acme-corp.com"}}, {"type": "storage", "config": {"path": "/storage/finance/invoices"}}], "contract": [{"type": "email", "config": {"recipient": "legal@acme-corp.com"}}, {"type": "storage", "config": {"path": "/storage/legal/contracts"}}], "resume": [{"type": "email", "config": {"recipient": "hr@acme-corp.com"}}]}', 'json', NOW(), NOW()),
(1, 'DOCS_v1', 'routing_min_validation_score', '70', 'number', NOW(), NOW()),
(1, 'DOCS_v1', 'routing_auto', 'true', 'boolean', NOW(), NOW());