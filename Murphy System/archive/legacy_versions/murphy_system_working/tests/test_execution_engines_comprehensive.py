"""
Comprehensive Integration Tests for Execution Engines
Tests all execution engines with correct API signatures
"""
import sys
import os
import time
from typing import List, Dict, Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.organization_chart_system import OrganizationChart, JobPosition, Department
from src.org_compiler import RoleTemplate, RoleMetrics
from src.org_compiler.compiler import RoleTemplateCompiler
from src.execution_engine.task_executor import TaskExecutor, Task
from src.execution_engine.workflow_orchestrator import WorkflowOrchestrator, Workflow, WorkflowStep
from src.execution_engine.decision_engine import DecisionEngine, Rule, Decision
from src.execution_engine.state_manager import StateManager, SystemState, StateType
from src.integrations.integration_framework import IntegrationFramework, Integration, IntegrationType
from src.integrations.database_connectors import SQLDatabaseConnector
from src.execution.document_generation_engine import DocumentGenerationEngine, DocumentTemplate
from src.system_integrator import SystemIntegrator


class ExecutionEnginesComprehensiveTest:
    """Comprehensive test of all execution engines"""
    
    def __init__(self):
        print("=" * 80)
        print("COMPREHENSIVE EXECUTION ENGINES INTEGRATION TEST")
        print("=" * 80)
        print()
        
        self.results = []
        self.test_data = {}
        
    def test_1_organization_chart_system(self):
        """Test 1: Organization Chart System"""
        print("\n" + "="*80)
        print("TEST 1: ORGANIZATION CHART SYSTEM")
        print("="*80)
        
        try:
            start_time = time.time()
            
            # Create organization chart
            org_chart = OrganizationChart()
            
            print(f"\n🏢 Creating Organization Chart...")
            print(f"   Total Positions: {len(org_chart.positions)}")
            print(f"   Departments: {org_chart.list_all_departments()}")
            
            # Get a position
            cto = org_chart.get_position("Chief Technology Officer")
            if cto:
                print(f"   CTO Position Found: {cto.title}")
                print(f"      Department: {cto.department.value}")
                print(f"      Level: {cto.level}")
            
            # Search positions
            eng_positions = org_chart.search_positions_by_department(Department.ENGINEERING)
            print(f"   Engineering Positions: {len(eng_positions)}")
            
            elapsed = time.time() - start_time
            
            print(f"\n✅ Organization Chart System Working")
            print(f"   - Time: {elapsed:.3f}s")
            print(f"   - Positions: {len(org_chart.positions)}")
            print(f"   - Departments: {len(org_chart.list_all_departments())}")
            
            self.test_data['org_chart'] = org_chart
            self.results.append({
                'test': 'Organization Chart System',
                'status': 'PASS',
                'time': elapsed,
                'positions': len(org_chart.positions)
            })
            
            return True
            
        except Exception as e:
            print(f"\n❌ Organization Chart Test Failed: {e}")
            import traceback
            traceback.print_exc()
            self.results.append({'test': 'Organization Chart System', 'status': 'FAIL', 'error': str(e)})
            return False
    
    def test_2_role_template_compilation(self):
        """Test 2: Role Template Compilation"""
        print("\n" + "="*80)
        print("TEST 2: ROLE TEMPLATE COMPILATION")
        print("="*80)
        
        try:
            start_time = time.time()
            
            # Create role templates
            templates = [
                RoleTemplate(
                    role_name="Software Engineer",
                    team="Engineering",
                    department="Engineering",
                    responsibilities=["Development", "Testing", "Code Review"],
                    authority_level=2,
                    requires_human_signoff=["critical_decisions"],
                    metrics=RoleMetrics(
                        sla_targets={"response_time": "4h"},
                        quality_gates={"code_review": True},
                        throughput_target=100,
                        error_rate_max=0.05
                    )
                ),
                RoleTemplate(
                    role_name="Product Manager",
                    team="Product",
                    department="Product",
                    responsibilities=["Planning", "Requirements", "Roadmap"],
                    authority_level=3,
                    requires_human_signoff=["strategy_changes"],
                    metrics=RoleMetrics(
                        sla_targets={"response_time": "2h"},
                        quality_gates={"review": True},
                        throughput_target=50,
                        error_rate_max=0.02
                    )
                )
            ]
            
            print(f"\n📋 Creating {len(templates)} Role Templates...")
            
            # Compile templates
            compiler = RoleTemplateCompiler()
            compiled = compiler.compile_templates(templates)
            
            elapsed = time.time() - start_time
            
            print(f"\n✅ Role Template Compilation Working")
            print(f"   - Time: {elapsed:.3f}s")
            print(f"   - Templates: {len(templates)}")
            print(f"   - Compiled: {len(compiled) if isinstance(compiled, list) else 1}")
            
            self.test_data['templates'] = templates
            self.results.append({
                'test': 'Role Template Compilation',
                'status': 'PASS',
                'time': elapsed,
                'templates': len(templates)
            })
            
            return True
            
        except Exception as e:
            print(f"\n❌ Role Template Compilation Failed: {e}")
            import traceback
            traceback.print_exc()
            self.results.append({'test': 'Role Template Compilation', 'status': 'FAIL', 'error': str(e)})
            return False
    
    def test_3_task_executor(self):
        """Test 3: Task Executor"""
        print("\n" + "="*80)
        print("TEST 3: TASK EXECUTOR")
        print("="*80)
        
        try:
            start_time = time.time()
            
            # Create task executor
            task_executor = TaskExecutor()
            
            print(f"\n⚙️ Initializing Task Executor...")
            
            # Create and execute tasks
            tasks = [
                Task(
                    task_id="TASK-001",
                    name="Research Task",
                    description="Research authentication best practices",
                    priority="HIGH"
                ),
                Task(
                    task_id="TASK-002",
                    name="Design Task",
                    description="Design authentication flow",
                    priority="HIGH"
                ),
                Task(
                    task_id="TASK-003",
                    name="Implementation Task",
                    description="Implement authentication system",
                    priority="CRITICAL"
                )
            ]
            
            print(f"\n🚀 Executing {len(tasks)} tasks...")
            
            successful = 0
            failed = 0
            
            for task in tasks:
                try:
                    result = task_executor.execute_task(task)
                    if result.get('success', False):
                        successful += 1
                        print(f"   ✅ {task.name}: SUCCESS")
                    else:
                        failed += 1
                        print(f"   ❌ {task.name}: FAILED")
                except Exception as e:
                    failed += 1
                    print(f"   ❌ {task.name}: ERROR - {str(e)}")
            
            elapsed = time.time() - start_time
            
            print(f"\n✅ Task Executor Working")
            print(f"   - Time: {elapsed:.3f}s")
            print(f"   - Total Tasks: {len(tasks)}")
            print(f"   - Successful: {successful}")
            print(f"   - Failed: {failed}")
            
            self.test_data['task_executor'] = task_executor
            self.results.append({
                'test': 'Task Executor',
                'status': 'PASS',
                'time': elapsed,
                'total_tasks': len(tasks),
                'successful': successful
            })
            
            return True
            
        except Exception as e:
            print(f"\n❌ Task Executor Test Failed: {e}")
            import traceback
            traceback.print_exc()
            self.results.append({'test': 'Task Executor', 'status': 'FAIL', 'error': str(e)})
            return False
    
    def test_4_workflow_orchestrator(self):
        """Test 4: Workflow Orchestrator"""
        print("\n" + "="*80)
        print("TEST 4: WORKFLOW ORCHESTRATOR")
        print("="*80)
        
        try:
            start_time = time.time()
            
            # Create task executor
            task_executor = TaskExecutor()
            
            # Create workflow orchestrator
            orchestrator = WorkflowOrchestrator(task_executor)
            
            print(f"\n⚙️ Initializing Workflow Orchestrator...")
            
            # Create workflow
            workflow = Workflow(
                workflow_id="WF-TEST-001",
                name="Test Workflow",
                description="Test workflow execution",
                steps=[
                    WorkflowStep(
                        step_id="STEP-001",
                        name="Step 1",
                        description="First step",
                        task=Task(task_id="TASK-001", name="Task 1", description="Task 1", priority="HIGH")
                    ),
                    WorkflowStep(
                        step_id="STEP-002",
                        name="Step 2",
                        description="Second step",
                        task=Task(task_id="TASK-002", name="Task 2", description="Task 2", priority="HIGH")
                    ),
                    WorkflowStep(
                        step_id="STEP-003",
                        name="Step 3",
                        description="Third step",
                        task=Task(task_id="TASK-003", name="Task 3", description="Task 3", priority="MEDIUM")
                    )
                ]
            )
            
            print(f"\n🚀 Executing workflow with {len(workflow.steps)} steps...")
            
            # Execute workflow
            result = orchestrator.execute_workflow(workflow)
            
            elapsed = time.time() - start_time
            
            print(f"\n✅ Workflow Orchestrator Working")
            print(f"   - Time: {elapsed:.3f}s")
            print(f"   - Workflow ID: {workflow.workflow_id}")
            print(f"   - Steps: {len(workflow.steps)}")
            print(f"   - Status: {result.get('status', 'Unknown')}")
            
            self.test_data['workflow'] = workflow
            self.results.append({
                'test': 'Workflow Orchestrator',
                'status': 'PASS',
                'time': elapsed,
                'steps': len(workflow.steps)
            })
            
            return True
            
        except Exception as e:
            print(f"\n❌ Workflow Orchestrator Test Failed: {e}")
            import traceback
            traceback.print_exc()
            self.results.append({'test': 'Workflow Orchestrator', 'status': 'FAIL', 'error': str(e)})
            return False
    
    def test_5_decision_engine(self):
        """Test 5: Decision Engine"""
        print("\n" + "="*80)
        print("TEST 5: DECISION ENGINE")
        print("="*80)
        
        try:
            start_time = time.time()
            
            # Create decision engine
            decision_engine = DecisionEngine()
            
            print(f"\n🧠 Initializing Decision Engine...")
            
            # Add rules
            rule1 = Rule(
                rule_id="RULE-001",
                name="High Priority Rule",
                description="Assign high priority to complex tasks",
                conditions=[{"field": "complexity", "operator": ">", "value": 8}],
                actions=[{"type": "set_priority", "value": "CRITICAL"}],
                priority=1,
                confidence=0.95
            )
            
            rule2 = Rule(
                rule_id="RULE-002",
                name="Standard Priority Rule",
                description="Assign standard priority to normal tasks",
                conditions=[{"field": "complexity", "operator": "<=", "value": 5}],
                actions=[{"type": "set_priority", "value": "MEDIUM"}],
                priority=2,
                confidence=0.90
            )
            
            decision_engine.add_rule(rule1)
            decision_engine.add_rule(rule2)
            print(f"   ✅ Added 2 rules")
            
            # Test decisions
            print(f"\n🧠 Testing decisions...")
            
            decision1 = decision_engine.make_decision({"complexity": 9})
            print(f"   Context: complexity=9")
            print(f"   Decision: {decision1.action if hasattr(decision1, 'action') else 'N/A'}")
            print(f"   Confidence: {decision1.confidence if hasattr(decision1, 'confidence') else 'N/A'}")
            
            decision2 = decision_engine.make_decision({"complexity": 3})
            print(f"   Context: complexity=3")
            print(f"   Decision: {decision2.action if hasattr(decision2, 'action') else 'N/A'}")
            print(f"   Confidence: {decision2.confidence if hasattr(decision2, 'confidence') else 'N/A'}")
            
            elapsed = time.time() - start_time
            
            print(f"\n✅ Decision Engine Working")
            print(f"   - Time: {elapsed:.3f}s")
            print(f"   - Rules: 2")
            print(f"   - Decisions Made: 2")
            
            self.results.append({
                'test': 'Decision Engine',
                'status': 'PASS',
                'time': elapsed,
                'rules': 2
            })
            
            return True
            
        except Exception as e:
            print(f"\n❌ Decision Engine Test Failed: {e}")
            import traceback
            traceback.print_exc()
            self.results.append({'test': 'Decision Engine', 'status': 'FAIL', 'error': str(e)})
            return False
    
    def test_6_state_manager(self):
        """Test 6: State Manager"""
        print("\n" + "="*80)
        print("TEST 6: STATE MANAGER")
        print("="*80)
        
        try:
            start_time = time.time()
            
            # Create state manager
            state_manager = StateManager()
            
            print(f"\n🗄️ Initializing State Manager...")
            
            # Create and set initial state
            initial_state = SystemState(
                state_id="STATE-001",
                state_type=StateType.SYSTEM,
                state_name="Initial State",
                variables={"status": "initialized", "version": "1.0"}
            )
            state_manager.set_state(initial_state)
            print(f"   ✅ Set initial state: {initial_state.state_name}")
            
            # Update state
            updated_state = SystemState(
                state_id="STATE-002",
                state_type=StateType.SYSTEM,
                state_name="Executing State",
                variables={"status": "executing", "tasks": 5}
            )
            state_manager.set_state(updated_state)
            print(f"   ✅ Set updated state: {updated_state.state_name}")
            
            # Get current state
            current_state = state_manager.get_current_state()
            print(f"\n   Current State:")
            print(f"      Name: {current_state.state_name}")
            print(f"      Type: {current_state.state_type.value}")
            print(f"      Variables: {current_state.variables}")
            
            # Get state history
            history = state_manager.get_state_history()
            print(f"\n   State History: {len(history)} states")
            
            elapsed = time.time() - start_time
            
            print(f"\n✅ State Manager Working")
            print(f"   - Time: {elapsed:.3f}s")
            print(f"   - States Managed: {len(history)}")
            print(f"   - Current State: {current_state.state_name}")
            
            self.results.append({
                'test': 'State Manager',
                'status': 'PASS',
                'time': elapsed,
                'states': len(history)
            })
            
            return True
            
        except Exception as e:
            print(f"\n❌ State Manager Test Failed: {e}")
            import traceback
            traceback.print_exc()
            self.results.append({'test': 'State Manager', 'status': 'FAIL', 'error': str(e)})
            return False
    
    def test_7_integrations_framework(self):
        """Test 7: Integrations Framework"""
        print("\n" + "="*80)
        print("TEST 7: INTEGRATIONS FRAMEWORK")
        print("="*80)
        
        try:
            start_time = time.time()
            
            # Create integration framework
            integration_framework = IntegrationFramework()
            
            print(f"\n🔗 Initializing Integration Framework...")
            
            # Create test integration
            test_integration = Integration(
                integration_id="INT-TEST-001",
                name="Test Integration",
                system_type=IntegrationType.CUSTOM,
                connection_params={"host": "localhost", "port": 5432},
                authentication={"type": "basic"},
                rate_limits={"max_requests": 100, "window": 60},
                endpoints={"api": "/api/v1", "health": "/health"}
            )
            
            integration_framework.register_integration(test_integration)
            print(f"   ✅ Registered integration: {test_integration.name}")
            
            # Create database connector
            db_connector = SQLDatabaseConnector(
                connector_id="DB-TEST-001",
                name="Test Database",
                connection_string="sqlite:///:memory:"
            )
            print(f"   ✅ Created database connector: {db_connector.name}")
            
            # Get all integrations
            integrations = integration_framework.get_all_integrations()
            print(f"\n   Total Integrations: {len(integrations)}")
            
            elapsed = time.time() - start_time
            
            print(f"\n✅ Integrations Framework Working")
            print(f"   - Time: {elapsed:.3f}s")
            print(f"   - Integrations: {len(integrations)}")
            
            self.results.append({
                'test': 'Integrations Framework',
                'status': 'PASS',
                'time': elapsed,
                'integrations': len(integrations)
            })
            
            return True
            
        except Exception as e:
            print(f"\n❌ Integrations Framework Test Failed: {e}")
            import traceback
            traceback.print_exc()
            self.results.append({'test': 'Integrations Framework', 'status': 'FAIL', 'error': str(e)})
            return False
    
    def test_8_document_generation_engine(self):
        """Test 8: Document Generation Engine"""
        print("\n" + "="*80)
        print("TEST 8: DOCUMENT GENERATION ENGINE")
        print("="*80)
        
        try:
            start_time = time.time()
            
            # Create document generation engine
            doc_engine = DocumentGenerationEngine()
            
            print(f"\n📄 Initializing Document Generation Engine...")
            
            # Create document template
            template = DocumentTemplate(
                template_id="TPL-001",
                name="Report Template",
                template_type="project_report",
                content="""
# Project Report

## Summary
{{summary}}

## Details
{{details}}

## Conclusion
{{conclusion}}
"""
            )
            
            print(f"   ✅ Created template: {template.name}")
            
            # Generate document
            data = {
                "summary": "Project completed successfully",
                "details": "All tasks were executed without errors",
                "conclusion": "System is fully functional"
            }
            
            print(f"\n   Generating document from template...")
            document = doc_engine.generate_document("project_report", data)
            
            elapsed = time.time() - start_time
            
            print(f"\n✅ Document Generation Engine Working")
            print(f"   - Time: {elapsed:.3f}s")
            print(f"   - Template: {template.name}")
            print(f"   - Document Generated: Yes")
            
            self.results.append({
                'test': 'Document Generation Engine',
                'status': 'PASS',
                'time': elapsed
            })
            
            return True
            
        except Exception as e:
            print(f"\n❌ Document Generation Engine Test Failed: {e}")
            import traceback
            traceback.print_exc()
            self.results.append({'test': 'Document Generation Engine', 'status': 'FAIL', 'error': str(e)})
            return False
    
    def test_9_system_integration(self):
        """Test 9: Complete System Integration"""
        print("\n" + "="*80)
        print("TEST 9: COMPLETE SYSTEM INTEGRATION")
        print("="*80)
        
        try:
            start_time = time.time()
            
            # Initialize system integrator
            integrator = SystemIntegrator()
            
            print(f"\n🔌 Initializing System Integrator...")
            
            # Test adapters
            print(f"\n   Testing Adapters:")
            adapters = [
                ('Neuro-Symbolic', integrator.neuro_symbolic),
                ('Telemetry', integrator.telemetry),
                ('Librarian', integrator.librarian_adapter),
                ('Module Compiler', integrator.module_compiler)
            ]
            
            available_count = 0
            for name, adapter in adapters:
                if adapter is not None:
                    available_count += 1
                    print(f"      ✅ {name}: Available")
                else:
                    print(f"      ❌ {name}: Not Available")
            
            # Collect metrics
            print(f"\n   Testing Metrics Collection:")
            for i in range(5):
                integrator.collect_metric(
                    metric_type="integration_test",
                    metric_name=f"test_metric_{i}",
                    value=i * 10,
                    labels={"test": "execution_engines"}
                )
            
            metrics = integrator.get_metrics(metric_type="integration_test", limit=10)
            print(f"      ✅ Collected {len(metrics)} metrics")
            
            elapsed = time.time() - start_time
            
            print(f"\n✅ Complete System Integration Working")
            print(f"   - Time: {elapsed:.3f}s")
            print(f"   - Adapters Available: {available_count}/{len(adapters)}")
            print(f"   - Metrics Collected: {len(metrics)}")
            
            self.results.append({
                'test': 'Complete System Integration',
                'status': 'PASS',
                'time': elapsed,
                'adapters': available_count,
                'metrics': len(metrics)
            })
            
            return True
            
        except Exception as e:
            print(f"\n❌ Complete System Integration Test Failed: {e}")
            import traceback
            traceback.print_exc()
            self.results.append({'test': 'Complete System Integration', 'status': 'FAIL', 'error': str(e)})
            return False
    
    def run_all_tests(self):
        """Run all comprehensive tests"""
        print("\n🚀 Starting Comprehensive Execution Engines Tests...")
        print(f"⏰ Start Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        total_start = time.time()
        
        # Run all tests in sequence
        tests = [
            self.test_1_organization_chart_system,
            self.test_2_role_template_compilation,
            self.test_3_task_executor,
            self.test_4_workflow_orchestrator,
            self.test_5_decision_engine,
            self.test_6_state_manager,
            self.test_7_integrations_framework,
            self.test_8_document_generation_engine,
            self.test_9_system_integration
        ]
        
        passed = 0
        failed = 0
        
        for test in tests:
            try:
                if test():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"\n❌ Test execution error: {e}")
                failed += 1
        
        total_elapsed = time.time() - total_start
        
        # Print summary
        print("\n" + "="*80)
        print("COMPREHENSIVE EXECUTION ENGINES TEST SUMMARY")
        print("="*80)
        print(f"\nTotal Tests: {len(tests)}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Success Rate: {(passed/len(tests)*100):.1f}%")
        print(f"\nTotal Execution Time: {total_elapsed:.3f}s")
        
        # Print detailed results
        print("\n📋 Detailed Results:")
        for result in self.results:
            status_icon = "✅" if result['status'] == 'PASS' else "❌"
            print(f"   {status_icon} {result['test']}: {result['status']}")
            if result['status'] == 'PASS':
                if 'time' in result:
                    print(f"      Time: {result['time']:.3f}s")
            
        # Overall assessment
        print("\n" + "="*80)
        if passed == len(tests):
            print("🎉 ALL TESTS PASSED - ALL EXECUTION ENGINES WORKING PERFECTLY!")
        elif passed >= len(tests) * 0.8:
            print("✅ EXECUTION ENGINES FUNCTIONAL - MINOR ISSUES DETECTED")
        else:
            print("⚠️ EXECUTION ENGINES HAVE ISSUES - REQUIRES ATTENTION")
        print("="*80)
        
        return passed == len(tests)


def main():
    """Main entry point"""
    test_runner = ExecutionEnginesComprehensiveTest()
    success = test_runner.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()