#!/bin/bash

echo "=========================================="
echo "Testing Librarian Integration"
echo "=========================================="
echo ""

API_BASE="http://localhost:3000"

echo "1. Testing /api/librarian/ask endpoint..."
curl -s -X POST "${API_BASE}/api/librarian/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "How do I create a document?"}' | jq '.'
echo ""

echo "2. Testing /api/librarian/search endpoint..."
curl -s -X POST "${API_BASE}/api/librarian/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "state"}' | jq '.'
echo ""

echo "3. Testing /api/librarian/transcripts endpoint..."
curl -s "${API_BASE}/api/librarian/transcripts?limit=3" | jq '.'
echo ""

echo "4. Testing /api/librarian/overview endpoint..."
curl -s "${API_BASE}/api/librarian/overview" | jq '.'
echo ""

echo "=========================================="
echo "All Librarian API tests complete!"
echo "=========================================="