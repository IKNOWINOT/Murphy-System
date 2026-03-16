"""
Integration tests for MFGC system
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import unittest
import pytest

try:
    from enhanced_chatbot_mfgc import EnhancedChatbotMFGC, ComplexityAnalyzer
except ImportError:
    pytest.skip("enhanced_chatbot_mfgc module not available", allow_module_level=True)
from domain_swarms import DomainDetector
from mfgc_metrics import MFGCMetricsCollector


class TestComplexityAnalyzer(unittest.TestCase):
    """Test complexity analysis"""

    def setUp(self):
        self.analyzer = ComplexityAnalyzer()

    def test_low_complexity(self):
        """Test low complexity detection"""
        complexity, conf = self.analyzer.analyze("Hello, how are you?", {})
        self.assertEqual(complexity, 'low')

    def test_high_complexity(self):
        """Test high complexity detection"""
        complexity, conf = self.analyzer.analyze(
            "Design a comprehensive enterprise architecture with microservices",
            {}
        )
        self.assertEqual(complexity, 'high')

    def test_medium_complexity(self):
        """Test medium complexity detection"""
        complexity, conf = self.analyzer.analyze(
            "Implement a function to sort an array",
            {}
        )
        self.assertIn(complexity, ['medium', 'low'])


class TestDomainDetector(unittest.TestCase):
    """Test domain detection"""

    def setUp(self):
        self.detector = DomainDetector()

    def test_software_engineering_detection(self):
        """Test software engineering domain detection"""
        domain = self.detector.detect_domain(
            "Build a REST API with database backend",
            {}
        )
        self.assertEqual(domain, 'software_engineering')

    def test_business_strategy_detection(self):
        """Test business strategy domain detection"""
        domain = self.detector.detect_domain(
            "Develop a market expansion strategy with ROI analysis",
            {}
        )
        self.assertEqual(domain, 'business_strategy')

    def test_scientific_research_detection(self):
        """Test scientific research domain detection"""
        domain = self.detector.detect_domain(
            "Design an experiment to test the hypothesis",
            {}
        )
        self.assertEqual(domain, 'scientific_research')

    def test_no_domain_match(self):
        """Test when no domain matches"""
        domain = self.detector.detect_domain("Hello world", {})
        self.assertIsNone(domain)

    def test_get_swarm(self):
        """Test swarm retrieval"""
        swarm = self.detector.get_swarm('software_engineering')
        self.assertIsNotNone(swarm)


class TestEnhancedChatbotMFGC(unittest.TestCase):
    """Test enhanced chatbot with MFGC"""

    def setUp(self):
        self.chatbot = EnhancedChatbotMFGC()

    def test_simple_greeting(self):
        """Test simple greeting routing"""
        response = self.chatbot.process_message("Hello!")
        self.assertIn('marker', response)
        self.assertIn('content', response)
        self.assertEqual(response['marker'], 'B')

    def test_code_request(self):
        """Test code generation routing"""
        response = self.chatbot.process_message("Write a Python function to calculate factorial")
        self.assertIn('marker', response)
        self.assertIn('content', response)
        self.assertIn(response['marker'], ['V', 'G'])

    def test_research_request(self):
        """Test research routing"""
        response = self.chatbot.process_message("Research information about machine learning")
        self.assertIn('marker', response)
        self.assertIn('content', response)

    def test_complex_task_routing(self):
        """Test complex task routes to MFGC"""
        response = self.chatbot.process_message(
            "Design a comprehensive enterprise system architecture with microservices, "
            "database design, API specifications, and deployment strategy"
        )
        self.assertIn('marker', response)
        self.assertEqual(response['marker'], 'V')
        self.assertEqual(response['metadata']['intent'], 'mfgc')

    def test_marker_system(self):
        """Test marker system is working"""
        response = self.chatbot.process_message("Hello")
        self.assertIn('marker_class', response)
        self.assertTrue(response['marker_class'].startswith('marker-'))

    def test_get_capabilities(self):
        """Test capabilities retrieval"""
        caps = self.chatbot.get_capabilities()
        self.assertIn('standard_flow', caps)
        self.assertIn('mfgc_flow', caps)
        self.assertIn('markers', caps)


class TestMFGCMetricsCollector(unittest.TestCase):
    """Test metrics collection"""

    def setUp(self):
        self.collector = MFGCMetricsCollector()

    def test_collect_from_state(self):
        """Test metrics collection from state"""
        from mfgc_core import MFGCController

        controller = MFGCController()
        state = controller.execute("Test task")

        metrics = self.collector.collect_from_state(state)

        self.assertIsNotNone(metrics)
        self.assertGreater(metrics.total_duration, 0)
        self.assertGreater(len(metrics.phase_metrics), 0)

    def test_aggregate_stats(self):
        """Test aggregate statistics"""
        from mfgc_core import MFGCController

        controller = MFGCController()

        # Collect metrics from multiple executions
        for i in range(3):
            state = controller.execute(f"Test task {i}")
            self.collector.collect_from_state(state)

        stats = self.collector.get_aggregate_stats()

        self.assertEqual(stats['total_executions'], 3)
        self.assertIn('average_duration', stats)
        self.assertIn('average_confidence_gain', stats)

    def test_phase_analysis(self):
        """Test phase-specific analysis"""
        from mfgc_core import MFGCController

        controller = MFGCController()
        state = controller.execute("Test task")
        self.collector.collect_from_state(state)

        analysis = self.collector.get_phase_analysis('expand')

        if 'error' not in analysis:
            self.assertIn('average_duration', analysis)
            self.assertIn('average_confidence_delta', analysis)

    def test_confidence_trajectory_analysis(self):
        """Test confidence trajectory analysis"""
        from mfgc_core import MFGCController

        controller = MFGCController()
        state = controller.execute("Test task")
        self.collector.collect_from_state(state)

        analysis = self.collector.get_confidence_trajectory_analysis()

        if 'error' not in analysis:
            self.assertIn('average_trajectory', analysis)
            self.assertIn('total_gain', analysis)

    def test_murphy_index_analysis(self):
        """Test Murphy index analysis"""
        from mfgc_core import MFGCController

        controller = MFGCController()
        state = controller.execute("Test task")
        self.collector.collect_from_state(state)

        analysis = self.collector.get_murphy_index_analysis()

        if 'error' not in analysis:
            self.assertIn('average_peak', analysis)
            self.assertIn('violation_rate', analysis)

    def test_gate_synthesis_analysis(self):
        """Test gate synthesis analysis"""
        from mfgc_core import MFGCController

        controller = MFGCController()
        state = controller.execute("Test task")
        self.collector.collect_from_state(state)

        analysis = self.collector.get_gate_synthesis_analysis()

        if 'error' not in analysis:
            self.assertIn('average_gates_per_execution', analysis)
            self.assertIn('gates_by_phase', analysis)


class TestEndToEnd(unittest.TestCase):
    """End-to-end integration tests"""

    def test_simple_conversation_flow(self):
        """Test simple conversation end-to-end"""
        chatbot = EnhancedChatbotMFGC()

        # Greeting
        response1 = chatbot.process_message("Hello!")
        self.assertIn('content', response1)

        # Question
        response2 = chatbot.process_message("What can you do?")
        self.assertIn('content', response2)

        # Code request
        response3 = chatbot.process_message("Write a Python function for fibonacci")
        self.assertIn('content', response3)

    def test_complex_task_flow(self):
        """Test complex task end-to-end"""
        chatbot = EnhancedChatbotMFGC()
        collector = MFGCMetricsCollector()

        # Complex task
        response = chatbot.process_message(
            "Design a scalable microservices architecture for an e-commerce platform"
        )

        self.assertEqual(response['metadata']['intent'], 'mfgc')
        self.assertIn('phases_completed', response['metadata'])
        self.assertIn('final_confidence', response['metadata'])
        self.assertIn('murphy_index', response['metadata'])

    def test_domain_specific_flow(self):
        """Test domain-specific routing"""
        chatbot = EnhancedChatbotMFGC()

        # Software engineering task
        response1 = chatbot.process_message(
            "Design a REST API with authentication and database integration"
        )
        if response1['metadata']['intent'] == 'mfgc':
            self.assertEqual(response1['metadata']['domain'], 'software_engineering')

        # Business strategy task
        response2 = chatbot.process_message(
            "Develop a market expansion strategy with competitive analysis"
        )
        if response2['metadata']['intent'] == 'mfgc':
            self.assertEqual(response2['metadata']['domain'], 'business_strategy')


if __name__ == '__main__':
    unittest.main()
