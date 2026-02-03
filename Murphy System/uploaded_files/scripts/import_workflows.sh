#!/bin/bash

# Script to import workflows into n8n
# Usage: ./scripts/import_workflows.sh

set -e

echo "Importing workflows into n8n..."

# n8n API endpoint
N8N_URL="http://localhost:5678"
API_URL="${N8N_URL}/rest/workflows"

# Function to import a single workflow
import_workflow() {
    local workflow_file=$1
    local workflow_name=$(basename "$workflow_file" .json)
    
    echo "Importing workflow: $workflow_name"
    
    # Read workflow file
    workflow_json=$(cat "$workflow_file")
    
    # Import workflow via API
    response=$(curl -s -X POST "${API_URL}" \
        -H "Content-Type: application/json" \
        -d "$workflow_json")
    
    echo "Response: $response"
    echo "Successfully imported: $workflow_name"
    echo "---"
}

# Import all INTAKE_v1 workflows
import_workflow "/workspace/workflows/intake_v1/INTAKE_v1_Capture_Leads.json"
import_workflow "/workspace/workflows/intake_v1/INTAKE_v1_Normalize_Data.json"
import_workflow "/workspace/workflows/intake_v1/INTAKE_v1_Enrich_Leads.json"
import_workflow "/workspace/workflows/intake_v1/INTAKE_v1_Route_Leads.json"
import_workflow "/workspace/workflows/intake_v1/INTAKE_v1_DLQ_Processor.json"

echo "All workflows imported successfully!"