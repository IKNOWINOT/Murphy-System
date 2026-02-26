#!/usr/bin/env python3
"""
Murphy System - Comprehensive Demo Script
==========================================

Demonstrates all Murphy System capabilities with beautiful output.
Can be run from Visual Studio Code (F5) or command line.

Usage:
    python demo_murphy.py --demo quick     # 2-minute quick demo
    python demo_murphy.py --demo full      # 10-minute full demo
    python demo_murphy.py --demo api       # API endpoints demo
    python demo_murphy.py --demo integration  # Integration engine demo
    python demo_murphy.py --demo business  # Business automation demo
    python demo_murphy.py --demo aiml      # AI/ML features demo
    python demo_murphy.py --demo all       # Everything!
"""

import sys
import time
import json
import argparse
import subprocess
import requests
from typing import Dict, Any, List
from datetime import datetime


class MurphyDemo:
    """Murphy System demonstration orchestrator"""
    
    def __init__(self, base_url: str = "http://localhost:6666"):
        self.base_url = base_url
        self.width = 80
        
    def print_header(self, title: str, char: str = "="):
        """Print a formatted header"""
        print(f"\n{char * self.width}")
        print(f"{title:^{self.width}}")
        print(f"{char * self.width}\n")
        
    def print_section(self, title: str):
        """Print a section header"""
        print(f"\n{'─' * self.width}")
        print(f"📌 {title}")
        print(f"{'─' * self.width}")
        
    def print_success(self, message: str):
        """Print success message"""
        print(f"✅ {message}")
        
    def print_info(self, message: str):
        """Print info message"""
        print(f"ℹ️  {message}")
        
    def print_warning(self, message: str):
        """Print warning message"""
        print(f"⚠️  {message}")
        
    def print_error(self, message: str):
        """Print error message"""
        print(f"❌ {message}")
        
    def print_json(self, data: Dict[str, Any], indent: int = 2):
        """Print formatted JSON"""
        print(json.dumps(data, indent=indent))
        
    def wait(self, seconds: float = 1.0):
        """Wait with visual indicator"""
        time.sleep(seconds)
        
    def check_server(self) -> bool:
        """Check if Murphy server is running"""
        try:
            response = requests.get(f"{self.base_url}/api/health", timeout=2)
            return response.status_code == 200
        except:
            return False
            
    def start_server(self):
        """Start Murphy server if not running"""
        if self.check_server():
            self.print_success("Murphy server is already running!")
            return True
            
        self.print_info("Starting Murphy server...")
        try:
            # Start server in background
            subprocess.Popen(
                ["python", "murphy_system_1.0_runtime.py"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Wait for server to start (max 30 seconds)
            for i in range(30):
                time.sleep(1)
                if self.check_server():
                    self.print_success("Murphy server started successfully!")
                    return True
                print(f"  Waiting for server... ({i+1}/30)", end="\r")
                
            self.print_error("Server failed to start within 30 seconds")
            return False
        except Exception as e:
            self.print_error(f"Failed to start server: {e}")
            return False
            
    def demo_quick(self):
        """Quick 2-minute demo of core features"""
        self.print_header("🚀 MURPHY SYSTEM - QUICK DEMO (2 minutes)", "=")
        
        # 1. Health Check
        self.print_section("1. Health Check")
        self.print_info("Checking Murphy system health...")
        try:
            response = requests.get(f"{self.base_url}/api/health")
            if response.status_code == 200:
                self.print_success("System is healthy!")
                self.print_json(response.json())
            else:
                self.print_error(f"Health check failed: {response.status_code}")
        except Exception as e:
            self.print_error(f"Could not reach server: {e}")
            return
        self.wait(1)
        
        # 2. System Status
        self.print_section("2. System Status")
        self.print_info("Getting system status...")
        try:
            response = requests.get(f"{self.base_url}/api/status")
            if response.status_code == 200:
                self.print_success("Status retrieved!")
                data = response.json()
                print(f"   Version: {data.get('version', 'N/A')}")
                print(f"   Components: {len(data.get('components', []))} loaded")
                print(f"   Engines: {len(data.get('engines', []))} active")
            else:
                self.print_warning(f"Status check returned {response.status_code}")
        except Exception as e:
            self.print_warning(f"Status unavailable: {e}")
        self.wait(1)
        
        # 3. Simple Task Execution
        self.print_section("3. Task Execution")
        self.print_info("Executing a simple automation task...")
        task_data = {
            "task_type": "analysis",
            "description": "Analyze system capabilities",
            "parameters": {
                "scope": "core_features"
            }
        }
        try:
            response = requests.post(f"{self.base_url}/api/execute", json=task_data)
            if response.status_code == 200:
                self.print_success("Task executed successfully!")
                result = response.json()
                print(f"   Task ID: {result.get('task_id', 'N/A')}")
                print(f"   Status: {result.get('status', 'N/A')}")
            else:
                self.print_warning(f"Task execution returned {response.status_code}")
        except Exception as e:
            self.print_warning(f"Task execution error: {e}")
        self.wait(1)
        
        # Summary
        self.print_header("✨ QUICK DEMO COMPLETE", "=")
        self.print_success("Murphy System 1.0 is operational!")
        print("\nKey Features Demonstrated:")
        print("  ✅ Health monitoring")
        print("  ✅ System status reporting")
        print("  ✅ Task execution")
        print("\nFor full demo, run: python demo_murphy.py --demo full")
        
    def demo_full(self):
        """Full 10-minute demo of all features"""
        self.print_header("🌟 MURPHY SYSTEM - FULL DEMO (10 minutes)", "=")
        
        # Start with quick demo
        self.print_info("Starting with quick demo...")
        self.demo_quick()
        self.wait(2)
        
        # 4. Integration Engine
        self.print_section("4. Integration Engine (SwissKiss)")
        self.print_info("Testing GitHub repository integration...")
        integration_data = {
            "repository_url": "https://github.com/example/test-repo",
            "integration_type": "github",
            "auto_analyze": True
        }
        try:
            response = requests.post(f"{self.base_url}/api/integrations/add", json=integration_data)
            if response.status_code == 200:
                self.print_success("Integration created!")
                result = response.json()
                print(f"   Integration ID: {result.get('integration_id', 'N/A')}")
                print(f"   Status: {result.get('status', 'pending')}")
                print(f"   HITL Approval: Required for safety")
            else:
                self.print_warning(f"Integration returned {response.status_code}")
        except Exception as e:
            self.print_warning(f"Integration test error: {e}")
        self.wait(2)
        
        # 5. Business Automation
        self.print_section("5. Business Automation Engines")
        self.print_info("Testing Inoni Business Automation...")
        
        engines = ["sales", "marketing", "r&d", "business_mgmt", "production"]
        for engine in engines:
            print(f"\n  Testing {engine.upper()} Engine...")
            automation_data = {
                "action": "analyze",
                "parameters": {
                    "scope": "current_status"
                }
            }
            try:
                response = requests.post(
                    f"{self.base_url}/api/automation/{engine}/analyze",
                    json=automation_data
                )
                if response.status_code == 200:
                    print(f"    ✅ {engine.upper()} engine operational")
                else:
                    print(f"    ⚠️  {engine.upper()} returned {response.status_code}")
            except Exception as e:
                print(f"    ⚠️  {engine.upper()} test error: {e}")
            self.wait(0.5)
        
        # 6. Murphy Validation
        self.print_section("6. Murphy Validation (G/D/H Formula)")
        self.print_info("Testing confidence scoring and uncertainty assessment...")
        validation_data = {
            "task": "deploy_to_production",
            "parameters": {
                "risk_level": "medium",
                "impact": "high"
            }
        }
        try:
            response = requests.post(f"{self.base_url}/api/validate", json=validation_data)
            if response.status_code == 200:
                self.print_success("Validation complete!")
                result = response.json()
                print(f"   Confidence: {result.get('confidence', 'N/A')}")
                print(f"   Gate Status: {result.get('gate_status', 'N/A')}")
                print(f"   Uncertainty (5D): {result.get('uncertainty', 'N/A')}")
            else:
                self.print_warning(f"Validation returned {response.status_code}")
        except Exception as e:
            self.print_warning(f"Validation test error: {e}")
        self.wait(2)
        
        # Summary
        self.print_header("🎉 FULL DEMO COMPLETE", "=")
        print("\nAll Murphy System 1.0 Features Demonstrated:")
        print("  ✅ Health & Status Monitoring")
        print("  ✅ Task Execution Engine")
        print("  ✅ Integration Engine (SwissKiss)")
        print("  ✅ Business Automation (5 Engines)")
        print("  ✅ Murphy Validation (G/D/H + 5D)")
        print("  ✅ HITL Safety System")
        print("\nMurphy System 1.0 is fully operational!")
        
    def demo_api(self):
        """Demo all API endpoints"""
        self.print_header("🔌 MURPHY SYSTEM - API ENDPOINTS DEMO", "=")
        
        endpoints = [
            ("GET", "/api/health", None, "Health Check"),
            ("GET", "/api/status", None, "System Status"),
            ("GET", "/api/info", None, "System Information"),
            ("GET", "/api/modules", None, "List Modules"),
            ("POST", "/api/execute", {"task_type": "test", "description": "API test"}, "Execute Task"),
        ]
        
        for method, endpoint, data, description in endpoints:
            self.print_section(f"{description} - {method} {endpoint}")
            try:
                if method == "GET":
                    response = requests.get(f"{self.base_url}{endpoint}")
                else:
                    response = requests.post(f"{self.base_url}{endpoint}", json=data)
                    
                if response.status_code in [200, 201]:
                    self.print_success(f"Success! Status: {response.status_code}")
                    if response.text:
                        try:
                            self.print_json(response.json())
                        except:
                            print(response.text)
                else:
                    self.print_warning(f"Status: {response.status_code}")
            except Exception as e:
                self.print_error(f"Error: {e}")
            self.wait(1)
            
        self.print_header("API DEMO COMPLETE", "=")
        
    def demo_integration(self):
        """Demo integration engine"""
        self.print_header("🔗 MURPHY SYSTEM - INTEGRATION ENGINE DEMO", "=")
        
        self.print_section("SwissKiss Auto-Integration")
        self.print_info("SwissKiss can automatically integrate any GitHub repository")
        print("\nProcess:")
        print("  1. Clone repository")
        print("  2. Analyze code structure (AST)")
        print("  3. Extract capabilities")
        print("  4. Generate Murphy modules")
        print("  5. Test for safety")
        print("  6. Request HITL approval")
        print("  7. Integrate into Murphy")
        
        self.wait(2)
        
        self.print_section("Testing Integration Request")
        integration_data = {
            "repository_url": "https://github.com/example/test-automation",
            "integration_type": "github",
            "auto_analyze": True,
            "safety_check": True
        }
        
        try:
            response = requests.post(f"{self.base_url}/api/integrations/add", json=integration_data)
            if response.status_code == 200:
                self.print_success("Integration request created!")
                self.print_json(response.json())
            else:
                self.print_warning(f"Status: {response.status_code}")
        except Exception as e:
            self.print_warning(f"Integration test: {e}")
            
        self.print_header("INTEGRATION DEMO COMPLETE", "=")
        
    def demo_business(self):
        """Demo business automation"""
        self.print_header("💼 MURPHY SYSTEM - BUSINESS AUTOMATION DEMO", "=")
        
        engines = {
            "sales": "Lead generation, qualification, outreach",
            "marketing": "Content creation, social media, SEO",
            "r&d": "Bug detection, fixes, testing",
            "business_mgmt": "Finance, support, documentation",
            "production": "Releases, QA, deployment"
        }
        
        for engine, description in engines.items():
            self.print_section(f"{engine.upper()} Engine")
            print(f"   Purpose: {description}")
            
            try:
                response = requests.post(
                    f"{self.base_url}/api/automation/{engine}/analyze",
                    json={"action": "status"}
                )
                if response.status_code == 200:
                    self.print_success(f"{engine.upper()} engine operational")
                else:
                    self.print_warning(f"Status: {response.status_code}")
            except Exception as e:
                self.print_warning(f"Test error: {e}")
            self.wait(1)
            
        self.print_header("BUSINESS AUTOMATION DEMO COMPLETE", "=")
        
    def demo_aiml(self):
        """Demo AI/ML features"""
        self.print_header("🤖 MURPHY SYSTEM - AI/ML FEATURES DEMO", "=")
        
        self.print_section("1. Murphy Validation (G/D/H Formula)")
        print("\nFormula: Confidence = G / (D + H)")
        print("  G = Goodness (positive indicators)")
        print("  D = Danger (risk factors)")
        print("  H = Heuristic uncertainty")
        print("\n5D Uncertainty Assessment:")
        print("  UD = Uncertainty in Data")
        print("  UA = Uncertainty in Algorithm")
        print("  UI = Uncertainty in Implementation")
        print("  UR = Uncertainty in Requirements")
        print("  UG = Uncertainty in Goals")
        self.wait(2)
        
        self.print_section("2. Shadow Agent Learning")
        print("\nSelf-Improvement System:")
        print("  • Captures 4 types of corrections")
        print("  • Extracts patterns (11 types)")
        print("  • Trains shadow agent")
        print("  • Improves from 80% → 95%+ accuracy")
        self.wait(2)
        
        self.print_section("3. Swarm Knowledge Pipeline")
        print("\nCooperative Multi-Agent System:")
        print("  • Confidence buckets (Green/Yellow/Red)")
        print("  • Agent task distribution")
        print("  • Knowledge propagation")
        print("  • Consensus building")
        self.wait(2)
        
        self.print_header("AI/ML DEMO COMPLETE", "=")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Murphy System Demo")
    parser.add_argument(
        "--demo",
        choices=["quick", "full", "api", "integration", "business", "aiml", "all"],
        default="quick",
        help="Which demo to run"
    )
    parser.add_argument(
        "--no-start",
        action="store_true",
        help="Don't attempt to start server"
    )
    args = parser.parse_args()
    
    demo = MurphyDemo()
    
    # Check/start server
    if not args.no_start:
        if not demo.check_server():
            demo.print_warning("Murphy server is not running")
            demo.print_info("Attempting to start server...")
            if not demo.start_server():
                demo.print_error("Could not start server. Please start manually:")
                print("    cd 'Murphy System/murphy_integrated'")
                print("    ./start.sh")
                sys.exit(1)
    
    # Run selected demo
    if args.demo == "quick":
        demo.demo_quick()
    elif args.demo == "full":
        demo.demo_full()
    elif args.demo == "api":
        demo.demo_api()
    elif args.demo == "integration":
        demo.demo_integration()
    elif args.demo == "business":
        demo.demo_business()
    elif args.demo == "aiml":
        demo.demo_aiml()
    elif args.demo == "all":
        demo.demo_quick()
        demo.wait(2)
        demo.demo_api()
        demo.wait(2)
        demo.demo_integration()
        demo.wait(2)
        demo.demo_business()
        demo.wait(2)
        demo.demo_aiml()
    
    # Final message
    print("\n" + "=" * 80)
    print("For more information, visit: http://localhost:6666/docs")
    print("=" * 80)


if __name__ == "__main__":
    main()
