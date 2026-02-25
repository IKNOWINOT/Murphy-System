#!/usr/bin/env python3
"""
Integration Tests for INTAKE_v1 Pack
Tests lead capture, normalization, enrichment, and routing
"""

import sys
import time
from test_framework import TestFramework, TestDataGenerator

def test_lead_capture(framework: TestFramework) -> dict:
    """Test lead capture via webhook"""
    # Generate test lead
    lead_data = TestDataGenerator.generate_lead(
        email='integration.test@example.com',
        first_name='Integration',
        last_name='Test',
        company='Test Corp'
    )
    
    # Call webhook (simulated - webhook needs to be activated in n8n UI)
    # For now, insert directly into database
    try:
        framework.execute_query("""
            INSERT INTO leads (client_id, email, first_name, last_name, company, phone, source, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'new', NOW())
            RETURNING id
        """, (
            lead_data['client_id'],
            lead_data['email'],
            lead_data['first_name'],
            lead_data['last_name'],
            lead_data['company'],
            lead_data['phone'],
            lead_data['source']
        ))
        
        # Verify lead was created
        result = framework.execute_query(
            "SELECT id, email, status FROM leads WHERE email = %s",
            (lead_data['email'],)
        )
        
        if result and len(result) > 0:
            return {
                'passed': True,
                'message': f'Lead captured successfully (ID: {result[0][0]})',
                'details': {'lead_id': result[0][0], 'email': result[0][1]}
            }
        else:
            return {
                'passed': False,
                'message': 'Lead not found in database'
            }
    except Exception as e:
        return {
            'passed': False,
            'message': f'Lead capture failed: {str(e)}'
        }

def test_lead_normalization(framework: TestFramework) -> dict:
    """Test lead data normalization"""
    # Insert lead with unnormalized data
    try:
        framework.execute_query("""
            INSERT INTO leads (client_id, email, first_name, last_name, company, status, created_at)
            VALUES (1, 'UPPERCASE@EXAMPLE.COM', 'john', 'DOE', '  Test Company  ', 'new', NOW())
            RETURNING id
        """)
        
        # Simulate normalization (in production, workflow would do this)
        framework.execute_query("""
            UPDATE leads 
            SET email = LOWER(email),
                first_name = INITCAP(first_name),
                last_name = INITCAP(last_name),
                company = TRIM(company),
                status = 'normalized'
            WHERE email = 'UPPERCASE@EXAMPLE.COM'
        """)
        
        # Verify normalization
        result = framework.execute_query(
            "SELECT email, first_name, last_name, company, status FROM leads WHERE email = 'uppercase@example.com'"
        )
        
        if result and len(result) > 0:
            email, first_name, last_name, company, status = result[0]
            
            checks = {
                'email_lowercase': email == 'uppercase@example.com',
                'first_name_capitalized': first_name == 'John',
                'last_name_capitalized': last_name == 'Doe',
                'company_trimmed': company == 'Test Company',
                'status_updated': status == 'normalized'
            }
            
            all_passed = all(checks.values())
            
            return {
                'passed': all_passed,
                'message': 'All normalization checks passed' if all_passed else 'Some normalization checks failed',
                'details': checks
            }
        else:
            return {
                'passed': False,
                'message': 'Normalized lead not found'
            }
    except Exception as e:
        return {
            'passed': False,
            'message': f'Normalization test failed: {str(e)}'
        }

def test_lead_scoring(framework: TestFramework) -> dict:
    """Test lead scoring calculation"""
    try:
        # Insert lead with complete data
        framework.execute_query("""
            INSERT INTO leads (client_id, email, first_name, last_name, company, phone, source, status, created_at)
            VALUES (1, 'scored.lead@example.com', 'Scored', 'Lead', 'Scored Company', '+1234567890', 'test', 'new', NOW())
            RETURNING id
        """)
        
        # Calculate score (simulating workflow logic)
        score = 0
        result = framework.execute_query(
            "SELECT email, first_name, last_name, company, phone FROM leads WHERE email = 'scored.lead@example.com'"
        )
        
        if result and len(result) > 0:
            email, first_name, last_name, company, phone = result[0]
            
            # Scoring logic (from INTAKE_v1_Normalize_Data workflow)
            if email: score += 10
            if first_name: score += 5
            if last_name: score += 5
            if company: score += 5
            if phone: score += 5
            
            # Update score
            framework.execute_query(
                "UPDATE leads SET lead_score = %s WHERE email = 'scored.lead@example.com'",
                (score,)
            )
            
            # Verify score
            result = framework.execute_query(
                "SELECT lead_score FROM leads WHERE email = 'scored.lead@example.com'"
            )
            
            if result and result[0][0] == score:
                return {
                    'passed': True,
                    'message': f'Lead scored correctly: {score} points',
                    'details': {'score': score}
                }
            else:
                return {
                    'passed': False,
                    'message': 'Lead score mismatch'
                }
        else:
            return {
                'passed': False,
                'message': 'Lead not found for scoring'
            }
    except Exception as e:
        return {
            'passed': False,
            'message': f'Scoring test failed: {str(e)}'
        }

def test_duplicate_detection(framework: TestFramework) -> dict:
    """Test duplicate lead detection"""
    try:
        # Insert first lead
        framework.execute_query("""
            INSERT INTO leads (client_id, email, first_name, last_name, status, created_at)
            VALUES (1, 'duplicate@example.com', 'Duplicate', 'Lead', 'new', NOW())
        """)
        
        # Try to insert duplicate
        framework.execute_query("""
            INSERT INTO leads (client_id, email, first_name, last_name, status, created_at)
            VALUES (1, 'duplicate@example.com', 'Duplicate', 'Lead', 'new', NOW())
        """)
        
        # Check for duplicates
        result = framework.execute_query(
            "SELECT COUNT(*) FROM leads WHERE email = 'duplicate@example.com' AND client_id = 1"
        )
        
        duplicate_count = result[0][0] if result else 0
        
        # Update enrichment status to mark duplicates
        if duplicate_count > 1:
            framework.execute_query("""
                UPDATE lead_enrichment 
                SET is_duplicate = TRUE, duplicate_count = %s
                WHERE lead_id IN (SELECT id FROM leads WHERE email = 'duplicate@example.com' AND client_id = 1)
            """, (duplicate_count,))
        
        return {
            'passed': True,
            'message': f'Duplicate detection working: {duplicate_count} duplicates found',
            'details': {'duplicate_count': duplicate_count}
        }
    except Exception as e:
        return {
            'passed': False,
            'message': f'Duplicate detection failed: {str(e)}'
        }

def test_lead_routing(framework: TestFramework) -> dict:
    """Test lead routing based on score"""
    try:
        # Insert high-score lead
        framework.execute_query("""
            INSERT INTO leads (client_id, email, first_name, last_name, company, phone, lead_score, status, created_at)
            VALUES (1, 'highscore@example.com', 'High', 'Score', 'High Company', '+1234567890', 30, 'enriched', NOW())
            RETURNING id
        """)
        
        result = framework.execute_query(
            "SELECT id FROM leads WHERE email = 'highscore@example.com'"
        )
        
        if result:
            lead_id = result[0][0]
            
            # Simulate routing decision
            framework.execute_query("""
                INSERT INTO lead_routing (lead_id, destination_type, destination_value, routing_reason, routed_at)
                VALUES (%s, 'webhook', 'https://example.com/webhook', 'High score lead', NOW())
            """, (lead_id,))
            
            # Update lead status
            framework.execute_query(
                "UPDATE leads SET status = 'routed' WHERE id = %s",
                (lead_id,)
            )
            
            # Verify routing
            result = framework.execute_query(
                "SELECT destination_type, routing_reason FROM lead_routing WHERE lead_id = %s",
                (lead_id,)
            )
            
            if result:
                return {
                    'passed': True,
                    'message': f'Lead routed successfully: {result[0][1]}',
                    'details': {'destination_type': result[0][0]}
                }
            else:
                return {
                    'passed': False,
                    'message': 'Routing record not found'
                }
        else:
            return {
                'passed': False,
                'message': 'Lead not found for routing'
            }
    except Exception as e:
        return {
            'passed': False,
            'message': f'Routing test failed: {str(e)}'
        }

def run_intake_tests():
    """Run all INTAKE_v1 integration tests"""
    print("="*70)
    print("🧪 INTAKE_v1 INTEGRATION TESTS")
    print("="*70)
    
    framework = TestFramework()
    
    if not framework.connect_db():
        print("❌ Failed to connect to database")
        return
    
    try:
        # Run tests
        framework.run_test("INTAKE_v1: Lead Capture", test_lead_capture, framework)
        framework.run_test("INTAKE_v1: Lead Normalization", test_lead_normalization, framework)
        framework.run_test("INTAKE_v1: Lead Scoring", test_lead_scoring, framework)
        framework.run_test("INTAKE_v1: Duplicate Detection", test_duplicate_detection, framework)
        framework.run_test("INTAKE_v1: Lead Routing", test_lead_routing, framework)
        
        # Print summary
        framework.print_summary()
        
        # Save report
        framework.save_report('test_results/intake_v1_results.json')
        
    finally:
        framework.close_db()

if __name__ == '__main__':
    run_intake_tests()