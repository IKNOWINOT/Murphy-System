#!/bin/bash

echo "=========================================="
echo "Testing Living Document API"
echo "=========================================="
echo ""

API_BASE="http://localhost:3000"

echo "1. Creating a new living document..."
DOC_ID=$(curl -s -X POST "${API_BASE}/api/documents" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Business Proposal",
    "doc_type": "proposal",
    "description": "Comprehensive business proposal for new product",
    "content": "We propose to develop a new product that solves customer pain points and creates market value.",
    "domains": ["business"],
    "tags": ["proposal", "product"]
  }' | jq -r '.document.id')

echo "Created document ID: $DOC_ID"
echo ""

echo "2. Getting document details..."
curl -s "${API_BASE}/api/documents/${DOC_ID}" | jq '.document | {id, name, current_state, expertise_depth, domains}'
echo ""

echo "3. Magnifying document with financial domain..."
curl -s -X POST "${API_BASE}/api/documents/${DOC_ID}/magnify" \
  -H "Content-Type: application/json" \
  -d '{"domain": "financial"}' | jq '{success, changes, key_additions}'
echo ""

echo "4. Magnifying document with marketing domain..."
curl -s -X POST "${API_BASE}/api/documents/${DOC_ID}/magnify" \
  -H "Content-Type: application/json" \
  -d '{"domain": "marketing"}' | jq '{success, changes}'
echo ""

echo "5. Checking expertise depth..."
curl -s "${API_BASE}/api/documents/${DOC_ID}" | jq '.document | {expertise_depth, domains, current_version}'
echo ""

echo "6. Simplifying document..."
curl -s -X POST "${API_BASE}/api/documents/${DOC_ID}/simplify" \
  -H "Content-Type: application/json" | jq '{success, changes, removed_sections}'
echo ""

echo "7. Solidifying document into generative prompts..."
curl -s -X POST "${API_BASE}/api/documents/${DOC_ID}/solidify" \
  -H "Content-Type: application/json" | jq '{success, strategy, prompts: [.prompts[] | {swarm_type, estimated_tokens}]}'
echo ""

echo "8. Saving as template..."
TEMPLATE_ID=$(curl -s -X POST "${API_BASE}/api/documents/${DOC_ID}/template" \
  -H "Content-Type: application/json" \
  -d '{"name": "Business Proposal Template"}' | jq -r '.template.id')

echo "Template ID: $TEMPLATE_ID"
echo ""

echo "9. Creating new document from template..."
curl -s -X POST "${API_BASE}/api/templates/${TEMPLATE_ID}/create" \
  -H "Content-Type: application/json" \
  -d '{"name": "New Proposal from Template"}' | jq '{success, message, document: {id, name, current_state}}'
echo ""

echo "10. Listing all documents..."
curl -s "${API_BASE}/api/documents" | jq '{count, documents: [.documents[] | {id, name, current_state, expertise_depth}]}'
echo ""

echo "11. Listing all templates..."
curl -s "${API_BASE}/api/templates" | jq '{count, templates: [.templates[] | {id, name, doc_type}]}'
echo ""

echo "=========================================="
echo "All Living Document API tests complete!"
echo "=========================================="