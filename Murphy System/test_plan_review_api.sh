#!/bin/bash

echo "=========================================="
echo "Testing Plan Review API"
echo "=========================================="
echo ""

API_BASE="http://localhost:3000"

echo "1. Creating a new plan..."
PLAN_ID=$(curl -s -X POST "${API_BASE}/api/plans" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Business Proposal Creation",
    "plan_type": "document_creation",
    "description": "Create a comprehensive business proposal",
    "content": "Create a business proposal with market analysis and financial projections.",
    "steps": [
      {"command": "/document create proposal", "description": "Create initial proposal document", "estimated_time": 60},
      {"command": "/domain add business", "description": "Add business domain", "estimated_time": 30}
    ],
    "domains": ["business"]
  }' | jq -r '.plan.id')

echo "Created plan ID: $PLAN_ID"
echo ""

echo "2. Getting plan details..."
curl -s "${API_BASE}/api/plans/${PLAN_ID}" | jq '.plan | {id, name, current_state, current_version, steps: (.versions[0].steps | length)}'
echo ""

echo "3. Magnifying plan with financial domain..."
curl -s -X POST "${API_BASE}/api/plans/${PLAN_ID}/magnify" \
  -H "Content-Type: application/json" \
  -d '{"domain": "financial"}' | jq '{success, changes}'
echo ""

echo "4. Simplifying plan..."
curl -s -X POST "${API_BASE}/api/plans/${PLAN_ID}/simplify" \
  -H "Content-Type: application/json" | jq '{success, changes}'
echo ""

echo "5. Solidifying plan..."
curl -s -X POST "${API_BASE}/api/plans/${PLAN_ID}/solidify" \
  -H "Content-Type: application/json" | jq '{success, message}'
echo ""

echo "6. Approving plan..."
curl -s -X POST "${API_BASE}/api/plans/${PLAN_ID}/approve" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user"}' | jq '{success, message}'
echo ""

echo "7. Getting final plan state..."
curl -s "${API_BASE}/api/plans/${PLAN_ID}" | jq '.plan | {id, name, current_state, current_version, domains}'
echo ""

echo "8. Listing all plans..."
curl -s "${API_BASE}/api/plans" | jq '{count, plans: [.plans[] | {id, name, current_state}]}'
echo ""

echo "=========================================="
echo "All Plan Review API tests complete!"
echo "=========================================="