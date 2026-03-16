"""
Performance Testing Suite for Murphy System Runtime
Tests system performance under various conditions and workloads
"""

import unittest
import time
import statistics
import threading
from typing import List, Dict
from datetime import datetime

# Import system components
import os

from src.system_integrator import SystemIntegrator


class TestPerformance(unittest.TestCase):
    """Performance tests for system components"""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures"""
        cls.integrator = SystemIntegrator()
        cls.performance_results: Dict[str, List[float]] = {}

    def test_adapter_initialization_performance(self):
        """Test adapter initialization speed"""
        iterations = 10
        times: List[float] = []

        for _ in range(iterations):
            start_time = time.time()
            integrator = SystemIntegrator()
            end_time = time.time()
            times.append((end_time - start_time) * 1000)  # Convert to milliseconds

        avg_time = statistics.mean(times)
        max_time = max(times)

        self.performance_results['initialization'] = times

        # Log results
        print(f"\n{'='*60}")
        print("Adapter Initialization Performance")
        print(f"{'='*60}")
        print(f"Iterations: {iterations}")
        print(f"Average time: {avg_time:.2f}ms")
        print(f"Max time: {max_time:.2f}ms")
        print(f"Min time: {min(times):.2f}ms")
        print(f"Std dev: {statistics.stdev(times):.2f}ms")

        # Performance assertion - should initialize in under 2 seconds
        self.assertLess(max_time, 2000, "Initialization should complete within 2 seconds")
        self.assertLess(avg_time, 1000, "Average initialization should be under 1 second")

    def test_metric_collection_performance(self):
        """Test metric collection speed"""
        num_metrics = 1000
        start_time = time.time()

        for i in range(num_metrics):
            if self.integrator.telemetry_enabled:
                self.integrator.collect_metric(
                    metric_type="performance",
                    metric_name=f"test_metric_{i}",
                    value=float(i),
                    labels={"test": "performance"}
                )

        end_time = time.time()
        total_time = (end_time - start_time) * 1000
        avg_time = total_time / num_metrics

        self.performance_results['metric_collection'] = [avg_time]

        print(f"\n{'='*60}")
        print("Metric Collection Performance")
        print(f"{'='*60}")
        print(f"Metrics collected: {num_metrics}")
        print(f"Total time: {total_time:.2f}ms")
        print(f"Average time per metric: {avg_time:.4f}ms")
        print(f"Metrics per second: {1000/avg_time:.2f}")

        # Performance assertion - should collect at least 100 metrics/second
        self.assertLess(avg_time, 10, "Each metric collection should take less than 10ms")
        self.assertGreater(1000/avg_time, 100, "Should collect at least 100 metrics/second")

    def test_inference_performance(self):
        """Test inference speed for neuro-symbolic reasoning"""
        num_inferences = 100
        times: List[float] = []

        if self.integrator.neuro_symbolic_enabled:
            for i in range(num_inferences):
                start_time = time.time()

                result = self.integrator.neuro_symbolic.perform_inference(
                    query=f"test query {i}",
                    reasoning_mode="hybrid"
                )

                end_time = time.time()
                times.append((end_time - start_time) * 1000)

            avg_time = statistics.mean(times)
            max_time = max(times)
            min_time = min(times)

            self.performance_results['inference'] = times

            print(f"\n{'='*60}")
            print("Neuro-Symbolic Inference Performance")
            print(f"{'='*60}")
            print(f"Inferences: {num_inferences}")
            print(f"Average time: {avg_time:.2f}ms")
            print(f"Max time: {max_time:.2f}ms")
            print(f"Min time: {min_time:.2f}ms")
            print(f"Std dev: {statistics.stdev(times):.2f}ms")

            # Performance assertions
            self.assertLess(avg_time, 100, "Average inference should be under 100ms")
            self.assertLess(max_time, 500, "Max inference time should be under 500ms")
        else:
            print("\nSkipping inference performance test - neuro-symbolic not enabled")

    def test_search_performance(self):
        """Test semantic search performance"""
        num_searches = 50
        times: List[float] = []

        # Add some test data first
        if self.integrator.librarian_adapter_enabled:
            for i in range(20):
                self.integrator.librarian_adapter.search_knowledge_base(
                    query=f"Test content for entry {i} with various keywords"
                )

            for i in range(num_searches):
                start_time = time.time()

                results = self.integrator.librarian_adapter.search_knowledge_base(
                    query=f"test query {i % 10}"
                )

                end_time = time.time()
                times.append((end_time - start_time) * 1000)

            avg_time = statistics.mean(times)
            max_time = max(times)

            self.performance_results['search'] = times

            print(f"\n{'='*60}")
            print("Semantic Search Performance")
            print(f"{'='*60}")
            print(f"Searches: {num_searches}")
            print(f"Average time: {avg_time:.2f}ms")
            print(f"Max time: {max_time:.2f}ms")
            print(f"Min time: {min(times):.2f}ms")

            # Performance assertions
            self.assertLess(avg_time, 50, "Average search should be under 50ms")
            self.assertLess(max_time, 200, "Max search time should be under 200ms")
        else:
            print("\nSkipping search performance test - librarian not enabled")

    def test_memory_usage(self):
        """Test memory usage under load"""
        import gc

        # Get initial memory usage
        gc.collect()
        initial_objects = len(gc.get_objects())

        # Perform operations that create objects
        for i in range(100):
            if self.integrator.telemetry_enabled:
                self.integrator.collect_metric(
                    metric_type="performance",
                    metric_name=f"memory_test_{i}",
                    value=float(i),
                    labels={"test": "memory"}
                )

        # Get final memory usage
        gc.collect()
        final_objects = len(gc.get_objects())
        objects_created = final_objects - initial_objects

        print(f"\n{'='*60}")
        print("Memory Usage Analysis")
        print(f"{'='*60}")
        print(f"Initial objects: {initial_objects}")
        print(f"Final objects: {final_objects}")
        print(f"Objects created: {objects_created}")
        print(f"Objects per operation: {objects_created/100:.2f}")

        # Memory should not grow excessively
        self.assertLess(objects_created, 10000, "Memory usage should be reasonable")

    def test_concurrent_operations_performance(self):
        """Test performance under concurrent operations"""
        num_threads = 10
        operations_per_thread = 50
        results: List[float] = []

        def worker():
            start = time.time()
            for i in range(operations_per_thread):
                if self.integrator.telemetry_enabled:
                    self.integrator.collect_metric(
                        metric_type="concurrent",
                        metric_name=f"concurrent_test_{threading.get_ident()}_{i}",
                        value=float(i),
                        labels={"thread": str(threading.get_ident())}
                    )
            end = time.time()
            results.append((end - start) * 1000)

        print(f"\n{'='*60}")
        print("Concurrent Operations Performance")
        print(f"{'='*60}")
        print(f"Threads: {num_threads}")
        print(f"Operations per thread: {operations_per_thread}")
        print(f"Total operations: {num_threads * operations_per_thread}")

        start_time = time.time()
        threads = [threading.Thread(target=worker) for _ in range(num_threads)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        total_time = (time.time() - start_time) * 1000
        avg_thread_time = statistics.mean(results)

        print(f"Total time: {total_time:.2f}ms")
        print(f"Average thread time: {avg_thread_time:.2f}ms")
        print(f"Operations per second: {(num_threads * operations_per_thread) / (total_time/1000):.2f}")

        self.performance_results['concurrent'] = results

        # Performance assertions
        self.assertLess(total_time, 5000, "Concurrent operations should complete within 5 seconds")

    def test_error_handling_performance(self):
        """Test performance of error handling"""
        num_errors = 100
        times: List[float] = []

        for i in range(num_errors):
            start_time = time.time()

            # Trigger error conditions
            if self.integrator.neuro_symbolic_enabled:
                result = self.integrator.neuro_symbolic.perform_inference(
                    query="",  # Empty query
                    reasoning_mode="invalid"
                )

            end_time = time.time()
            times.append((end_time - start_time) * 1000)

        avg_time = statistics.mean(times)

        self.performance_results['error_handling'] = times

        print(f"\n{'='*60}")
        print("Error Handling Performance")
        print(f"{'='*60}")
        print(f"Error cases: {num_errors}")
        print(f"Average handling time: {avg_time:.2f}ms")

        # Error handling should still be fast
        self.assertLess(avg_time, 50, "Error handling should be fast")

    @classmethod
    def tearDownClass(cls):
        """Generate performance summary"""
        print(f"\n{'='*60}")
        print("PERFORMANCE TEST SUMMARY")
        print(f"{'='*60}")

        for test_name, times in cls.performance_results.items():
            if times:
                print(f"\n{test_name.replace('_', ' ').title()}:")
                print(f"  Average: {statistics.mean(times):.2f}ms")
                print(f"  Min: {min(times):.2f}ms")
                print(f"  Max: {max(times):.2f}ms")
                if len(times) > 1:
                    print(f"  Std Dev: {statistics.stdev(times):.2f}ms")


if __name__ == '__main__':
    unittest.main(verbosity=2)
