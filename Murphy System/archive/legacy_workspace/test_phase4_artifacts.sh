#!/bin/bash

echo "=========================================="
echo "PHASE 4: ARTIFACT GENERATION SYSTEM TESTS"
echo "=========================================="
echo ""

API_BASE="http://localhost:3000"

# Test 1: Get supported artifact types
echo "Test 1: Get supported artifact types"
curl -s "$API_BASE/api/artifacts/types" | jq
echo ""

# Test 2: List artifacts (should be empty initially)
echo "Test 2: List artifacts"
curl -s "$API_BASE/api/artifacts/list" | jq
echo ""

# Test 3: Initialize system to create documents
echo "Test 3: Initialize system"
curl -s -X POST "$API_BASE/api/initialize" | jq '.success'
echo ""

# Test 4: Create a living document
echo "Test 4: Create a living document"
curl -s -X POST "$API_BASE/api/documents/create" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Document for Artifact Generation",
    "content": "This is a comprehensive test document that will be used to generate various types of artifacts. It contains detailed information about the Murphy System architecture, implementation details, and usage guidelines.",
    "domain_name": "engineering"
  }' | jq '.document.id' > /tmp/doc_id.txt
DOC_ID=$(cat /tmp/doc_id.txt | tr -d '"')
echo "Created document: $DOC_ID"
echo ""

# Test 5: Solidify the document
echo "Test 5: Solidify document"
curl -s -X POST "$API_BASE/api/documents/$DOC_ID/solidify" | jq '.success'
echo ""

# Test 6: Generate PDF artifact
echo "Test 6: Generate PDF artifact"
curl -s -X POST "$API_BASE/api/artifacts/generate" \
  -H "Content-Type: application/json" \
  -d "{
    &quot;type&quot;: &quot;pdf&quot;,
    &quot;document_id&quot;: &quot;$DOC_ID&quot;
  }" | jq '.artifact.id' > /tmp/pdf_id.txt
PDF_ID=$(cat /tmp/pdf_id.txt | tr -d '"')
echo "Generated PDF: $PDF_ID"
echo ""

# Test 7: Generate CODE artifact
echo "Test 7: Generate CODE artifact"
curl -s -X POST "$API_BASE/api/artifacts/generate" \
  -H "Content-Type: application/json" \
  -d "{
    &quot;type&quot;: &quot;code&quot;,
    &quot;document_id&quot;: &quot;$DOC_ID&quot;
  }" | jq '.artifact.id' > /tmp/code_id.txt
CODE_ID=$(cat /tmp/code_id.txt | tr -d '"')
echo "Generated CODE: $CODE_ID"
echo ""

# Test 8: Generate REPORT artifact
echo "Test 8: Generate REPORT artifact"
curl -s -X POST "$API_BASE/api/artifacts/generate" \
  -H "Content-Type: application/json" \
  -d "{
    &quot;type&quot;: &quot;report&quot;,
    &quot;document_id&quot;: &quot;$DOC_ID&quot;
  }" | jq '.artifact.id' > /tmp/report_id.txt
REPORT_ID=$(cat /tmp/report_id.txt | tr -d '"')
echo "Generated REPORT: $REPORT_ID"
echo ""

# Test 9: List all artifacts
echo "Test 9: List all artifacts"
curl -s "$API_BASE/api/artifacts/list" | jq '.count'
echo ""

# Test 10: Get specific artifact details
echo "Test 10: Get PDF artifact details"
curl -s "$API_BASE/api/artifacts/$PDF_ID" | jq '{id, name, type, status, quality_score}'
echo ""

# Test 11: Get artifact versions
echo "Test 11: Get artifact version history"
curl -s "$API_BASE/api/artifacts/$PDF_ID/versions" | jq '.count'
echo ""

# Test 12: Search artifacts
echo "Test 12: Search artifacts"
curl -s "$API_BASE/api/artifacts/search?q=Test" | jq '.count'
echo ""

# Test 13: Convert artifact format
echo "Test 13: Convert PDF to DOCX"
curl -s -X POST "$API_BASE/api/artifacts/$PDF_ID/convert" \
  -H "Content-Type: application/json" \
  -d '{"format": "docx"}' | jq '.success'
echo ""

# Test 14: Get artifact statistics
echo "Test 14: Get artifact statistics"
curl -s "$API_BASE/api/artifacts/stats" | jq
echo ""

# Test 15: List artifacts by type
echo "Test 15: List PDF artifacts"
curl -s "$API_BASE/api/artifacts/list?type=pdf" | jq '.count'
echo ""

# Test 16: List artifacts by status
echo "Test 16: List complete artifacts"
curl -s "$API_BASE/api/artifacts/list?status=complete" | jq '.count'
echo ""

echo ""
echo "=========================================="
echo "ALL PHASE 4 TESTS COMPLETED"
echo "=========================================="