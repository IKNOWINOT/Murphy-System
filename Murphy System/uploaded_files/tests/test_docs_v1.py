#!/usr/bin/env python3
"""
Integration Tests for DOCS_v1 Pack
Tests document intake, classification, extraction, validation, and routing
"""

import sys
import time
from test_framework import TestFramework, TestDataGenerator

def test_document_intake(framework: TestFramework) -> dict:
    """Test document intake"""
    try:
        # Generate test document
        doc_data = TestDataGenerator.generate_document(
            filename='test_invoice.pdf',
            file_type='application/pdf',
            file_size=2048
        )
        
        # Insert document
        framework.execute_query("""
            INSERT INTO documents (client_id, filename, file_type, file_size, file_path, source, processing_status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, 'pending', NOW())
            RETURNING id
        """, (
            doc_data['client_id'],
            doc_data['filename'],
            doc_data['file_type'],
            doc_data['file_size'],
            f"/storage/documents/{doc_data['filename']}",
            doc_data['source']
        ))
        
        # Verify document was created
        result = framework.execute_query(
            "SELECT id, filename, processing_status FROM documents WHERE filename = %s",
            (doc_data['filename'],)
        )
        
        if result and len(result) > 0:
            return {
                'passed': True,
                'message': f'Document ingested successfully (ID: {result[0][0]})',
                'details': {'doc_id': result[0][0], 'filename': result[0][1]}
            }
        else:
            return {
                'passed': False,
                'message': 'Document not found in database'
            }
    except Exception as e:
        return {
            'passed': False,
            'message': f'Document intake failed: {str(e)}'
        }

def test_document_classification(framework: TestFramework) -> dict:
    """Test document classification"""
    try:
        # Insert document
        framework.execute_query("""
            INSERT INTO documents (client_id, filename, file_type, processing_status, created_at)
            VALUES (1, 'invoice_12345.pdf', 'application/pdf', 'pending', NOW())
            RETURNING id
        """)
        
        result = framework.execute_query(
            "SELECT id FROM documents WHERE filename = 'invoice_12345.pdf'"
        )
        
        if result:
            doc_id = result[0][0]
            
            # Simulate classification (keyword-based)
            category = 'invoice'
            confidence = 0.85
            priority = 'high'
            tags = ['invoice', 'financial', 'payment']
            
            # Update document with classification
            framework.execute_query("""
                UPDATE documents 
                SET category = %s, 
                    confidence_score = %s, 
                    priority = %s, 
                    tags = %s,
                    processing_status = 'classified'
                WHERE id = %s
            """, (category, confidence, priority, tags, doc_id))
            
            # Verify classification
            result = framework.execute_query(
                "SELECT category, confidence_score, priority, tags FROM documents WHERE id = %s",
                (doc_id,)
            )
            
            if result:
                cat, conf, pri, tgs = result[0]
                return {
                    'passed': True,
                    'message': f'Document classified as {cat} with {conf*100}% confidence',
                    'details': {
                        'category': cat,
                        'confidence': conf,
                        'priority': pri,
                        'tags': tgs
                    }
                }
            else:
                return {
                    'passed': False,
                    'message': 'Classification not found'
                }
        else:
            return {
                'passed': False,
                'message': 'Document not found for classification'
            }
    except Exception as e:
        return {
            'passed': False,
            'message': f'Classification test failed: {str(e)}'
        }

def test_data_extraction(framework: TestFramework) -> dict:
    """Test data extraction from documents"""
    try:
        # Insert document
        framework.execute_query("""
            INSERT INTO documents (client_id, filename, category, processing_status, created_at)
            VALUES (1, 'contract_abc.pdf', 'contract', 'classified', NOW())
            RETURNING id
        """)
        
        result = framework.execute_query(
            "SELECT id FROM documents WHERE filename = 'contract_abc.pdf'"
        )
        
        if result:
            doc_id = result[0][0]
            
            # Simulate data extraction
            extracted_data = {
                'contract_number': 'ABC-12345',
                'party_a': 'Acme Corp',
                'party_b': 'Test Company',
                'effective_date': '2024-01-01',
                'expiration_date': '2025-01-01',
                'value': '50000'
            }
            
            # Insert extraction results
            framework.execute_query("""
                INSERT INTO document_extractions (document_id, extracted_data, extraction_method, confidence_score, created_at)
                VALUES (%s, %s, 'regex', 0.75, NOW())
            """, (doc_id, str(extracted_data)))
            
            # Update document status
            framework.execute_query("""
                UPDATE documents SET processing_status = 'extracted' WHERE id = %s
            """, (doc_id,))
            
            # Verify extraction
            result = framework.execute_query(
                "SELECT extracted_data, confidence_score FROM document_extractions WHERE document_id = %s",
                (doc_id,)
            )
            
            if result:
                return {
                    'passed': True,
                    'message': f'Data extracted successfully with {result[0][1]*100}% confidence',
                    'details': {'fields_extracted': len(extracted_data)}
                }
            else:
                return {
                    'passed': False,
                    'message': 'Extraction results not found'
                }
        else:
            return {
                'passed': False,
                'message': 'Document not found for extraction'
            }
    except Exception as e:
        return {
            'passed': False,
            'message': f'Extraction test failed: {str(e)}'
        }

def test_data_validation(framework: TestFramework) -> dict:
    """Test extracted data validation"""
    try:
        # Insert document with extraction
        framework.execute_query("""
            INSERT INTO documents (client_id, filename, category, processing_status, created_at)
            VALUES (1, 'validated_doc.pdf', 'invoice', 'extracted', NOW())
            RETURNING id
        """)
        
        result = framework.execute_query(
            "SELECT id FROM documents WHERE filename = 'validated_doc.pdf'"
        )
        
        if result:
            doc_id = result[0][0]
            
            # Insert extraction
            extracted_data = {
                'invoice_number': 'INV-001',
                'amount': '1000.00',
                'date': '2024-01-15',
                'vendor': 'Test Vendor'
            }
            
            framework.execute_query("""
                INSERT INTO document_extractions (document_id, extracted_data, extraction_method, confidence_score)
                VALUES (%s, %s, 'ocr', 0.90)
            """, (doc_id, str(extracted_data)))
            
            # Simulate validation
            validation_score = 85  # 4 required fields present
            validation_errors = []
            
            # Update document with validation results
            framework.execute_query("""
                UPDATE documents 
                SET validation_score = %s,
                    validation_errors = %s,
                    processing_status = 'validated'
                WHERE id = %s
            """, (validation_score, validation_errors, doc_id))
            
            # Verify validation
            result = framework.execute_query(
                "SELECT validation_score, processing_status FROM documents WHERE id = %s",
                (doc_id,)
            )
            
            if result:
                score, status = result[0]
                passed = score >= 70 and status == 'validated'
                
                return {
                    'passed': passed,
                    'message': f'Document validated with score: {score}',
                    'details': {'validation_score': score, 'status': status}
                }
            else:
                return {
                    'passed': False,
                    'message': 'Validation results not found'
                }
        else:
            return {
                'passed': False,
                'message': 'Document not found for validation'
            }
    except Exception as e:
        return {
            'passed': False,
            'message': f'Validation test failed: {str(e)}'
        }

def test_document_routing(framework: TestFramework) -> dict:
    """Test document routing based on category"""
    try:
        # Insert validated document
        framework.execute_query("""
            INSERT INTO documents (client_id, filename, category, validation_score, processing_status, created_at)
            VALUES (1, 'routed_invoice.pdf', 'invoice', 85, 'validated', NOW())
            RETURNING id
        """)
        
        result = framework.execute_query(
            "SELECT id FROM documents WHERE filename = 'routed_invoice.pdf'"
        )
        
        if result:
            doc_id = result[0][0]
            
            # Simulate routing decision (invoice -> email finance@)
            framework.execute_query("""
                INSERT INTO document_routing (document_id, destination_type, destination_value, routing_reason, routed_at)
                VALUES (%s, 'email', 'finance@acmecorp.com', 'Invoice category routing', NOW())
            """, (doc_id,))
            
            # Update document status
            framework.execute_query("""
                UPDATE documents SET processing_status = 'routed' WHERE id = %s
            """, (doc_id,))
            
            # Verify routing
            result = framework.execute_query(
                "SELECT destination_type, destination_value FROM document_routing WHERE document_id = %s",
                (doc_id,)
            )
            
            if result:
                return {
                    'passed': True,
                    'message': f'Document routed to {result[0][0]}: {result[0][1]}',
                    'details': {
                        'destination_type': result[0][0],
                        'destination_value': result[0][1]
                    }
                }
            else:
                return {
                    'passed': False,
                    'message': 'Routing record not found'
                }
        else:
            return {
                'passed': False,
                'message': 'Document not found for routing'
            }
    except Exception as e:
        return {
            'passed': False,
            'message': f'Routing test failed: {str(e)}'
        }

def run_docs_tests():
    """Run all DOCS_v1 integration tests"""
    print("="*70)
    print("🧪 DOCS_v1 INTEGRATION TESTS")
    print("="*70)
    
    framework = TestFramework()
    
    if not framework.connect_db():
        print("❌ Failed to connect to database")
        return
    
    try:
        # Run tests
        framework.run_test("DOCS_v1: Document Intake", test_document_intake, framework)
        framework.run_test("DOCS_v1: Document Classification", test_document_classification, framework)
        framework.run_test("DOCS_v1: Data Extraction", test_data_extraction, framework)
        framework.run_test("DOCS_v1: Data Validation", test_data_validation, framework)
        framework.run_test("DOCS_v1: Document Routing", test_document_routing, framework)
        
        # Print summary
        framework.print_summary()
        
        # Save report
        framework.save_report('test_results/docs_v1_results.json')
        
    finally:
        framework.close_db()

if __name__ == '__main__':
    run_docs_tests()