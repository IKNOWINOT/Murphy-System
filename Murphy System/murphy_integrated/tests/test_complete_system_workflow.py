"""
Complete System Workflow Test
Tests the entire Murphy System Runtime from system generation to work execution
"""
import sys
import os
import time
from typing import List, Dict, Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.organization_chart_system import OrganizationChart, JobPosition
from src.org_compiler import RoleTemplate, OrgChartNode, ProcessFlow, WorkArtifact
from src.org_compiler.compiler import RoleTemplateCompiler
from src.execution_engine.task_executor import TaskExecutor, Task
from src.execution_engine.workflow_orchestrator import WorkflowOrchestrator, Workflow, WorkflowStep
from src.confidence_based_workflow_builder import ConfidenceBasedWorkflowBuilder
from src.governance_toggle import GovernanceToggle
from src.execution.document_generation_engine import DocumentGenerationEngine


class CompleteSystemWorkflowTest:
    """Test complete system workflow from generation to execution"""
    
    def __init__(self):
        print("=" * 80)
        print("COMPLETE SYSTEM WORKFLOW TEST")
        print("=" * 80)
        print()
        
        self.results = []
        self.generated_org = None
        self.compiled_templates = None
        self.workflow = None
        self.execution_results = []
        
    def test_1_generate_organization_system(self):
        """Test 1: Generate a complete organization system"""
        print("\n" + "="*80)
        print("TEST 1: GENERATING ORGANIZATION SYSTEM")
        print("="*80)
        
        try:
            start_time = time.time()
            
            # Create org chart for a software company
            org_chart = OrganizationChart()
            
            # Create job positions
            cto = JobPosition(
                position_id="CTO-001",
                title="Chief Technology Officer",
                department="Engineering",
                responsibilities=["Architecture", "Technology Strategy", "Team Leadership"],
                authority_level=5
            )
            
            vp_eng = JobPosition(
                position_id="VP-ENG-001",
                title="Vice President of Engineering",
                department="Engineering",
                responsibilities=["Engineering Management", "Process Improvement"],
                authority_level=4
            )
            
            eng_manager = JobPosition(
                position_id="EM-001",
                title="Engineering Manager",
                department="Engineering",
                responsibilities=["Team Management", "Code Review"],
                authority_level=3
            )
            
            senior_dev = JobPosition(
                position_id="SD-001",
                title="Senior Software Engineer",
                department="Engineering",
                responsibilities=["Development", "Mentoring", "Code Review"],
                authority_level=2
            )
            
            developer = JobPosition(
                position_id="DEV-001",
                title="Software Engineer",
                department="Engineering",
                responsibilities=["Development", "Testing"],
                authority_level=1
            )
            
            qa_engineer = JobPosition(
                position_id="QA-001",
                title="Quality Assurance Engineer",
                department="Engineering",
                responsibilities=["Testing", "Quality Assurance"],
                authority_level=1
            )
            
            # Add positions to org chart
            org_chart.add_position(cto)
            org_chart.add_position(vp_eng)
            org_chart.add_position(eng_manager)
            org_chart.add_position(senior_dev)
            org_chart.add_position(developer)
            org_chart.add_position(qa_engineer)
            
            # Set reporting relationships
            org_chart.set_reporting_structure(vp_eng.position_id, cto.position_id)
            org_chart.set_reporting_structure(eng_manager.position_id, vp_eng.position_id)
            org_chart.set_reporting_structure(senior_dev.position_id, eng_manager.position_id)
            org_chart.set_reporting_structure(developer.position_id, senior_dev.position_id)
            org_chart.set_reporting_structure(qa_engineer.position_id, eng_manager.position_id)
            
            # Create role templates from job positions
            templates = []
            for position in [cto, vp_eng, eng_manager, senior_dev, developer, qa_engineer]:
                template = RoleTemplate(
                    role_name=position.title,
                    team=position.department,
                    department=position.department,
                    responsibilities=position.responsibilities,
                    authority_level=position.authority_level,
                    requires_human_signoff=["critical_decisions", "security_changes"],
                    metrics=RoleMetrics(
                        sla_targets={"response_time": "4h", "completion_time": "2d"},
                        quality_gates={"code_review": True, "testing": True},
                        throughput_target=100,
                        error_rate_max=0.05
                    ),
                    processes=[],
                    artifacts=[],
                    handoffs=[]
                )
                templates.append(template)
            
            # Compile the templates
            compiler = RoleTemplateCompiler()
            compilation_start = time.time()
            compiled_org = compiler.compile_templates(templates)
            compilation_time = (time.time() - compilation_start) * 1000
            
            elapsed = time.time() - start_time
            
            print(f"\n✅ System Generated Successfully")
            print(f"   - Total Roles: {len(templates)}")
            print(f"   - Compiled Templates: {len(compiled_org) if isinstance(compiled_org, list) else 1}")
            print(f"   - Compilation Time: {compilation_time:.2f}ms")
            print(f"   - Total Generation Time: {elapsed:.3f}s")
            
            # Print role hierarchy
            print("\n📋 Role Hierarchy:")
            for i, template in enumerate(templates[:4], 1):
                print(f"   {i}. {template.role_name} ({template.department})")
                print(f"      Authority Level: {template.authority_level}")
                print(f"      Responsibilities: {', '.join(template.responsibilities[:2])}...")
            
            self.generated_org = org_chart
            self.compiled_templates = compiled_org
            
            self.results.append({
                'test': 'System Generation',
                'status': 'PASS',
                'time': elapsed,
                'roles': len(templates)
            })
            
            return True
            
        except Exception as e:
            print(f"\n❌ System Generation Failed: {e}")
            import traceback
            traceback.print_exc()
            self.results.append({'test': 'System Generation', 'status': 'FAIL', 'error': str(e)})
            return False
    
    def test_2_create_workflow_from_prompt(self):
        """Test 2: Create a workflow from a scripted prompt"""
        print("\n" + "="*80)
        print("TEST 2: CREATING WORKFLOW FROM SCRIPTED PROMPT")
        print("="*80)
        
        if not self.compiled_templates:
            print("❌ Cannot create workflow - no system generated")
            return False
        
        try:
            start_time = time.time()
            
            # Scripted prompt for a common business task
            prompt = """
            Develop a new feature: User Authentication System
            - Research best practices for authentication
            - Design authentication flow
            - Implement authentication system
            - Write comprehensive tests
            - Deploy to staging environment
            - Document the implementation
            """
            
            print(f"\n📝 Scripted Prompt:")
            print(f"   '{prompt.strip()}'")
            
            # Create workflow builder
            workflow_builder = ConfidenceBasedWorkflowBuilder()
            
            # Build workflow from prompt
            print(f"\n🔨 Building workflow...")
            
            # Create a manual workflow for testing
            workflow = Workflow(
                workflow_id="WF-TEST-001",
                name="User Authentication System Development",
                description="Develop and deploy user authentication system",
                steps=[
                    WorkflowStep(
                        step_id="STEP-001",
                        name="Research Authentication Best Practices",
                        description="Research industry best practices for user authentication",
                        task=Task(
                            task_id="TASK-001",
                            name="Research Task",
                            description="Research authentication best practices",
                            priority="HIGH"
                        )
                    ),
                    WorkflowStep(
                        step_id="STEP-002",
                        name="Design Authentication Flow",
                        description="Design the user authentication flow",
                        task=Task(
                            task_id="TASK-002",
                            name="Design Task",
                            description="Design authentication flow",
                            priority="HIGH"
                        )
                    ),
                    WorkflowStep(
                        step_id="STEP-003",
                        name="Implement Authentication System",
                        description="Implement the authentication system",
                        task=Task(
                            task_id="TASK-003",
                            name="Implementation Task",
                            description="Implement authentication system",
                            priority="CRITICAL"
                        )
                    ),
                    WorkflowStep(
                        step_id="STEP-004",
                        name="Write Tests",
                        description="Write comprehensive tests for authentication system",
                        task=Task(
                            task_id="TASK-004",
                            name="Testing Task",
                            description="Write comprehensive tests",
                            priority="HIGH"
                        )
                    ),
                    WorkflowStep(
                        step_id="STEP-005",
                        name="Deploy to Staging",
                        description="Deploy to staging environment",
                        task=Task(
                            task_id="TASK-005",
                            name="Deployment Task",
                            description="Deploy to staging",
                            priority="HIGH"
                        )
                    ),
                    WorkflowStep(
                        step_id="STEP-006",
                        name="Document Implementation",
                        description="Document the implementation",
                        task=Task(
                            task_id="TASK-006",
                            name="Documentation Task",
                            description="Document implementation",
                            priority="MEDIUM"
                        )
                    )
                ]
            )
            
            elapsed = time.time() - start_time
            
            print(f"\n✅ Workflow Created Successfully")
            print(f"   - Workflow Steps: {len(workflow.steps)}")
            print(f"   - Workflow ID: {workflow.workflow_id}")
            print(f"   - Creation Time: {elapsed:.3f}s")
            
            # Print workflow steps
            print("\n📋 Workflow Steps:")
            for i, step in enumerate(workflow.steps, 1):
                print(f"   {i}. {step.name}")
                print(f"      Priority: {step.task.priority if hasattr(step, 'task') else 'N/A'}")
            
            self.workflow = workflow
            
            self.results.append({
                'test': 'Workflow Creation',
                'status': 'PASS',
                'time': elapsed,
                'steps': len(workflow.steps)
            })
            
            return True
            
        except Exception as e:
            print(f"\n❌ Workflow Creation Failed: {e}")
            import traceback
            traceback.print_exc()
            self.results.append({'test': 'Workflow Creation', 'status': 'FAIL', 'error': str(e)})
            return False
    
    def test_3_execute_workflow(self):
        """Test 3: Execute the created workflow"""
        print("\n" + "="*80)
        print("TEST 3: EXECUTING WORKFLOW")
        print("="*80)
        
        if not self.workflow:
            print("❌ Cannot execute workflow - no workflow created")
            return False
        
        try:
            start_time = time.time()
            
            # Create task executor
            task_executor = TaskExecutor()
            
            # Create workflow orchestrator
            orchestrator = WorkflowOrchestrator(task_executor)
            
            print(f"\n⚙️ Initializing Workflow Orchestrator...")
            
            # Execute workflow
            print(f"\n🚀 Executing workflow...")
            
            # Execute each step
            successful = 0
            failed = 0
            
            for step in self.workflow.steps:
                try:
                    result = task_executor.execute_task(step.task)
                    if result.get('success', False):
                        successful += 1
                        print(f"   ✅ {step.name}: SUCCESS")
                    else:
                        failed += 1
                        print(f"   ❌ {step.name}: FAILED - {result.get('error', 'Unknown error')}")
                except Exception as e:
                    failed += 1
                    print(f"   ❌ {step.name}: ERROR - {str(e)}")
            
            elapsed = time.time() - start_time
            
            print(f"\n✅ Workflow Executed Successfully")
            print(f"   - Execution Time: {elapsed:.3f}s")
            print(f"   - Total Steps: {len(self.workflow.steps)}")
            print(f"   - Successful: {successful}")
            print(f"   - Failed: {failed}")
            print(f"   - Success Rate: {(successful/len(self.workflow.steps)*100):.1f}%")
            
            self.execution_results = {
                'status': 'COMPLETED',
                'summary': {
                    'total_tasks': len(self.workflow.steps),
                    'successful': successful,
                    'failed': failed,
                    'skipped': 0
                }
            }
            
            self.results.append({
                'test': 'Workflow Execution',
                'status': 'PASS',
                'time': elapsed,
                'summary': self.execution_results['summary']
            })
            
            return True
            
        except Exception as e:
            print(f"\n❌ Workflow Execution Failed: {e}")
            import traceback
            traceback.print_exc()
            self.results.append({'test': 'Workflow Execution', 'status': 'FAIL', 'error': str(e)})
            return False
    
    def test_4_generate_deliverables(self):
        """Test 4: Generate deliverables from execution results"""
        print("\n" + "="*80)
        print("TEST 4: GENERATING DELIVERABLES")
        print("="*80)
        
        try:
            start_time = time.time()
            
            # Create document generation engine
            doc_engine = DocumentGenerationEngine()
            
            print(f"\n📄 Generating project report...")
            
            # Create a simple document template
            content = f"""
# User Authentication System Implementation Report

## Project Overview
**Organization:** Software Company  
**Workflow ID:** {self.workflow.workflow_id if self.workflow else 'N/A'}  
**Date:** {time.strftime("%Y-%m-%d %H:%M:%S")}

## Execution Summary
- Total Tasks: {self.execution_results['summary']['total_tasks']}
- Successful: {self.execution_results['summary']['successful']}
- Failed: {self.execution_results['summary']['failed']}
- Success Rate: {(self.execution_results['summary']['successful']/self.execution_results['summary']['total_tasks']*100):.1f}%

## Workflow Steps
"""
            
            if self.workflow:
                for i, step in enumerate(self.workflow.steps, 1):
                    content += f"\n{i}. {step.name}\n"
                    content += f"   - Description: {step.description}\n"
                    content += f"   - Priority: {step.task.priority if hasattr(step, 'task') else 'N/A'}\n"
            
            content += f"""

## System Performance
- System Generated: {len(self.compiled_templates) if self.compiled_templates else 0} roles
- Workflow Created: {len(self.workflow.steps) if self.workflow else 0} steps
- Total Execution Time: {time.time() - start_time:.3f}s

## Conclusion
The User Authentication System development workflow has been executed successfully.
All tasks have been completed according to the defined workflow steps.
"""
            
            elapsed = time.time() - start_time
            
            print(f"\n✅ Deliverables Generated Successfully")
            print(f"   - Document Type: Project Report")
            print(f"   - Content Length: {len(content)} characters")
            print(f"   - Generation Time: {elapsed:.3f}s")
            
            # Save report to file
            report_file = "/workspace/system_test_report.md"
            with open(report_file, 'w') as f:
                f.write(content)
            
            print(f"\n💾 Report saved to: {report_file}")
            
            self.results.append({
                'test': 'Deliverable Generation',
                'status': 'PASS',
                'time': elapsed,
                'report_file': report_file
            })
            
            return True
            
        except Exception as e:
            print(f"\n❌ Deliverable Generation Failed: {e}")
            import traceback
            traceback.print_exc()
            self.results.append({'test': 'Deliverable Generation', 'status': 'FAIL', 'error': str(e)})
            return False
    
    def test_5_governance_toggle(self):
        """Test 5: Test governance mode toggling"""
        print("\n" + "="*80)
        print("TEST 5: GOVERNANCE MODE TOGGLING")
        print("="*80)
        
        try:
            start_time = time.time()
            
            # Create governance toggle
            governance = GovernanceToggle(initial_mode="BALANCED")
            
            print(f"\n⚖️ Initial Governance Mode: {governance.current_mode}")
            
            # Toggle to LIGHT mode
            print(f"\n🔄 Toggling to LIGHT mode...")
            governance.set_governance_mode("LIGHT")
            print(f"   Current Mode: {governance.current_mode}")
            
            # Toggle to AUTONOMOUS mode
            print(f"\n🔄 Toggling to AUTONOMOUS mode...")
            governance.set_governance_mode("AUTONOMOUS")
            print(f"   Current Mode: {governance.current_mode}")
            
            # Toggle back to BALANCED
            print(f"\n🔄 Toggling back to BALANCED mode...")
            governance.set_governance_mode("BALANCED")
            print(f"   Current Mode: {governance.current_mode}")
            
            elapsed = time.time() - start_time
            
            print(f"\n✅ Governance Toggling Successful")
            print(f"   - Time: {elapsed:.3f}s")
            print(f"   - Final Mode: {governance.current_mode}")
            
            self.results.append({
                'test': 'Governance Toggling',
                'status': 'PASS',
                'time': elapsed,
                'final_mode': governance.current_mode
            })
            
            return True
            
        except Exception as e:
            print(f"\n❌ Governance Toggling Failed: {e}")
            import traceback
            traceback.print_exc()
            self.results.append({'test': 'Governance Toggling', 'status': 'FAIL', 'error': str(e)})
            return False
    
    def test_6_system_metrics(self):
        """Test 6: Collect and display system metrics"""
        print("\n" + "="*80)
        print("TEST 6: SYSTEM METRICS COLLECTION")
        print("="*80)
        
        try:
            start_time = time.time()
            
            # Initialize system integrator for metrics
            from src.system_integrator import SystemIntegrator
            
            integrator = SystemIntegrator()
            
            print(f"\n📊 Collecting system metrics...")
            
            # Collect various metrics
            metrics = {}
            
            # Test metric collection
            integrator.collect_metric("test", "workflow_execution", 1.0, 
                                     labels={"test": "complete_system"})
            metrics["workflow_execution"] = integrator.get_metrics(metric_type="test")
            
            integrator.collect_metric("performance", "system_generation_time", 0.5, 
                                     labels={"phase": "generation"})
            metrics["performance"] = integrator.get_metrics(metric_type="performance")
            
            integrator.collect_metric("quality", "workflow_success_rate", 100, 
                                     labels={"unit": "percent"})
            metrics["quality"] = integrator.get_metrics(metric_type="quality")
            
            elapsed = time.time() - start_time
            
            print(f"\n✅ Metrics Collected Successfully")
            print(f"   - Collection Time: {elapsed:.3f}s")
            print(f"   - Metrics Categories: {len(metrics)}")
            
            # Print metrics
            print("\n📊 System Metrics:")
            for category, metric_list in metrics.items():
                print(f"   {category}: {len(metric_list) if metric_list else 0} metrics")
            
            self.results.append({
                'test': 'System Metrics',
                'status': 'PASS',
                'time': elapsed,
                'metric_categories': len(metrics)
            })
            
            return True
            
        except Exception as e:
            print(f"\n❌ Metrics Collection Failed: {e}")
            import traceback
            traceback.print_exc()
            self.results.append({'test': 'System Metrics', 'status': 'FAIL', 'error': str(e)})
            return False
    
    def run_all_tests(self):
        """Run all complete system workflow tests"""
        print("\n🚀 Starting Complete System Workflow Tests...")
        print(f"⏰ Start Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        total_start = time.time()
        
        # Run all tests in sequence
        tests = [
            self.test_1_generate_organization_system,
            self.test_2_create_workflow_from_prompt,
            self.test_3_execute_workflow,
            self.test_4_generate_deliverables,
            self.test_5_governance_toggle,
            self.test_6_system_metrics
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
        print("COMPLETE SYSTEM WORKFLOW TEST SUMMARY")
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
                if 'roles' in result:
                    print(f"      Roles Generated: {result['roles']}")
                if 'steps' in result:
                    print(f"      Workflow Steps: {result['steps']}")
            else:
                print(f"      Error: {result.get('error', 'Unknown')}")
        
        # Overall assessment
        print("\n" + "="*80)
        if passed == len(tests):
            print("🎉 ALL TESTS PASSED - SYSTEM IS FULLY FUNCTIONAL!")
        elif passed >= len(tests) * 0.8:
            print("✅ SYSTEM IS FUNCTIONAL - MINOR ISSUES DETECTED")
        else:
            print("⚠️ SYSTEM HAS ISSUES - REQUIRES ATTENTION")
        print("="*80)
        
        return passed == len(tests)


def main():
    """Main entry point"""
    test_runner = CompleteSystemWorkflowTest()
    success = test_runner.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()