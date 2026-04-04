"""
Load Testing Suite for Murphy System Runtime
Tests system behavior under high load and stress conditions
"""

import unittest
import time
import threading
import queue
import statistics
from typing import List, Dict
from datetime import datetime

# Import system components
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.system_integrator import SystemIntegrator


class TestLoad(unittest.TestCase):
    """Load tests for system components"""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures"""
        cls.integrator = SystemIntegrator()
        cls.load_results: Dict[str, Dict] = {}

    def test_high_metric_throughput(self):
        """Test system with high metric collection throughput"""
        num_metrics = 5000
        batch_size = 100

        print(f"\n{'='*60}")
        print("High Metric Throughput Test")
        print(f"{'='*60}")
        print(f"Total metrics: {num_metrics}")
        print(f"Batch size: {batch_size}")

        start_time = time.time()
        errors = 0

        for batch_start in range(0, num_metrics, batch_size):
            batch_end = min(batch_start + batch_size, num_metrics)

            for i in range(batch_start, batch_end):
                try:
                    if self.integrator.telemetry_enabled:
                        self.integrator.collect_metric(
                            metric_type="load_test",
                            metric_name=f"metric_{i}",
                            value=float(i),
                            labels={"batch": str(i // batch_size)}
                        )
                except Exception as e:
                    errors += 1

            # Small pause between batches to simulate realistic load
            time.sleep(0.001)

        end_time = time.time()
        total_time = end_time - start_time
        throughput = num_metrics / total_time

        self.load_results['high_throughput'] = {
            'total_metrics': num_metrics,
            'total_time': total_time,
            'throughput': throughput,
            'errors': errors,
            'error_rate': errors / num_metrics
        }

        print(f"Total time: {total_time:.2f}s")
        print(f"Throughput: {throughput:.2f} metrics/second")
        print(f"Errors: {errors}")
        print(f"Error rate: {(errors/num_metrics)*100:.4f}%")

        # Load assertions
        self.assertGreater(throughput, 100, "Should handle at least 100 metrics/second")
        self.assertLess(errors, num_metrics * 0.01, "Error rate should be less than 1%")

    def test_concurrent_user_simulation(self):
        """Test system with simulated concurrent users"""
        num_users = 20
        operations_per_user = 30
        results_queue = queue.Queue()

        print(f"\n{'='*60}")
        print("Concurrent User Simulation")
        print(f"{'='*60}")
        print(f"Simulated users: {num_users}")
        print(f"Operations per user: {operations_per_user}")
        print(f"Total operations: {num_users * operations_per_user}")

        def simulate_user(user_id: int):
            """Simulate a user performing operations"""
            user_errors = 0
            start_time = time.time()

            for i in range(operations_per_user):
                try:
                    # Mix of different operations
                    operation_type = i % 4

                    if operation_type == 0 and self.integrator.telemetry_enabled:
                        self.integrator.collect_metric(
                            metric_type="user_simulation",
                            metric_name=f"user_{user_id}_op_{i}",
                            value=float(i),
                            labels={"user_id": str(user_id)}
                        )

                    elif operation_type == 1 and self.integrator.neuro_symbolic_enabled:
                        self.integrator.neuro_symbolic.perform_inference(
                            query=f"user {user_id} query {i}",
                            reasoning_mode="hybrid"
                        )

                    elif operation_type == 2 and self.integrator.librarian_adapter_enabled:
                        self.integrator.librarian_adapter.search_knowledge(
                            query=f"search {i}",
                            limit=5
                        )

                    # Small delay to simulate realistic user behavior
                    time.sleep(0.01)

                except Exception as e:
                    user_errors += 1

            end_time = time.time()
            results_queue.put({
                'user_id': user_id,
                'errors': user_errors,
                'duration': end_time - start_time
            })

        start_time = time.time()
        threads = [threading.Thread(target=simulate_user, args=(i,)) for i in range(num_users)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        total_time = time.time() - start_time

        # Collect results
        all_results = []
        total_errors = 0
        while not results_queue.empty():
            result = results_queue.get()
            all_results.append(result)
            total_errors += result['errors']

        avg_user_time = sum(r['duration'] for r in all_results) / len(all_results)

        self.load_results['concurrent_users'] = {
            'num_users': num_users,
            'operations_per_user': operations_per_user,
            'total_time': total_time,
            'total_errors': total_errors,
            'error_rate': total_errors / (num_users * operations_per_user),
            'avg_user_time': avg_user_time
        }

        print(f"Total time: {total_time:.2f}s")
        print(f"Total errors: {total_errors}")
        print(f"Error rate: {(total_errors/(num_users * operations_per_user))*100:.4f}%")
        print(f"Average user time: {avg_user_time:.2f}s")

        # Load assertions
        self.assertLess(total_errors, num_users * operations_per_user * 0.30,
                       "Error rate should be less than 30%")
        self.assertLess(total_time, 60, "All operations should complete within 60 seconds")

    def test_sustained_load(self):
        """Test system under sustained load over time"""
        duration_seconds = 10
        operations_per_second = 50

        print(f"\n{'='*60}")
        print("Sustained Load Test")
        print(f"{'='*60}")
        print(f"Duration: {duration_seconds}s")
        print(f"Target rate: {operations_per_second} ops/sec")

        operations_performed = 0
        errors = 0
        start_time = time.time()

        while time.time() - start_time < duration_seconds:
            batch_start = time.time()

            for i in range(operations_per_second):
                try:
                    if self.integrator.telemetry_enabled:
                        self.integrator.collect_metric(
                            metric_type="sustained_load",
                            metric_name=f"metric_{operations_performed}",
                            value=float(operations_performed),
                            labels={"time": str(time.time())}
                        )
                    operations_performed += 1
                except Exception as e:
                    errors += 1

            # Adjust timing to maintain target rate
            batch_time = time.time() - batch_start
            if batch_time < 1.0:
                time.sleep(1.0 - batch_time)

        total_time = time.time() - start_time
        actual_rate = operations_performed / total_time

        self.load_results['sustained_load'] = {
            'duration': total_time,
            'target_rate': operations_per_second,
            'actual_rate': actual_rate,
            'operations_performed': operations_performed,
            'errors': errors,
            'error_rate': errors / operations_performed if operations_performed > 0 else 0
        }

        print(f"Total time: {total_time:.2f}s")
        print(f"Operations performed: {operations_performed}")
        print(f"Actual rate: {actual_rate:.2f} ops/sec")
        print(f"Errors: {errors}")
        print(f"Error rate: {(errors/operations_performed)*100:.4f}%")

        # Load assertions
        self.assertGreater(actual_rate, operations_per_second * 0.8,
                          "Should maintain at least 80% of target rate")
        self.assertLess(errors, operations_performed * 0.02,
                       "Error rate should be less than 2%")

    def test_burst_load(self):
        """Test system handling of burst traffic"""
        burst_size = 500
        num_bursts = 5
        time_between_bursts = 2

        print(f"\n{'='*60}")
        print("Burst Load Test")
        print(f"{'='*60}")
        print(f"Burst size: {burst_size}")
        print(f"Number of bursts: {num_bursts}")
        print(f"Time between bursts: {time_between_bursts}s")

        all_burst_times = []
        total_errors = 0

        for burst_num in range(num_bursts):
            print(f"Burst {burst_num + 1}/{num_bursts}...")

            burst_start = time.time()
            burst_errors = 0

            for i in range(burst_size):
                try:
                    if self.integrator.telemetry_enabled:
                        self.integrator.collect_metric(
                            metric_type="burst",
                            metric_name=f"burst_{burst_num}_metric_{i}",
                            value=float(i),
                            labels={"burst": str(burst_num)}
                        )
                except Exception as e:
                    burst_errors += 1

            burst_time = time.time() - burst_start
            all_burst_times.append(burst_time)
            total_errors += burst_errors

            print(f"  Burst time: {burst_time:.3f}s ({burst_size/burst_time:.2f} ops/sec)")
            print(f"  Errors: {burst_errors}")

            if burst_num < num_bursts - 1:
                time.sleep(time_between_bursts)

        avg_burst_time = statistics.mean(all_burst_times)
        avg_burst_rate = burst_size / avg_burst_time

        self.load_results['burst_load'] = {
            'burst_size': burst_size,
            'num_bursts': num_bursts,
            'avg_burst_time': avg_burst_time,
            'avg_burst_rate': avg_burst_rate,
            'total_errors': total_errors,
            'error_rate': total_errors / (burst_size * num_bursts)
        }

        print(f"\nAverage burst time: {avg_burst_time:.3f}s")
        print(f"Average burst rate: {avg_burst_rate:.2f} ops/sec")
        print(f"Total errors: {total_errors}")
        print(f"Error rate: {(total_errors/(burst_size*num_bursts))*100:.4f}%")

        # Load assertions
        self.assertGreater(avg_burst_rate, 100, "Should handle bursts of at least 100 ops/sec")
        self.assertLess(total_errors, burst_size * num_bursts * 0.01,
                       "Error rate should be less than 1%")

    def test_resource_limits(self):
        """Test system behavior approaching resource limits"""
        large_dataset_size = 10000

        print(f"\n{'='*60}")
        print("Resource Limits Test")
        print(f"{'='*60}")
        print(f"Dataset size: {large_dataset_size}")

        start_time = time.time()
        memory_errors = 0

        # Add large amount of data
        if self.integrator.librarian_adapter_enabled:
            for i in range(large_dataset_size):
                try:
                    self.integrator.librarian_adapter.add_knowledge(
                        entry_id=f"large_entry_{i}",
                        content={
                            "data": "x" * 100,  # 100 bytes per entry
                            "index": i,
                            "timestamp": str(time.time())
                        },
                        metadata={"size": "large", "batch": str(i // 1000)}
                    )

                    # Perform occasional operations to mix load
                    if i % 100 == 0:
                        self.integrator.librarian_adapter.search_knowledge(
                            query=f"data {i}",
                            limit=10
                        )

                except MemoryError:
                    memory_errors += 1
                    break
                except Exception as e:
                    pass

        total_time = time.time() - start_time

        self.load_results['resource_limits'] = {
            'dataset_size': large_dataset_size,
            'time_elapsed': total_time,
            'memory_errors': memory_errors,
            'entries_per_second': large_dataset_size / total_time if total_time > 0 else 0
        }

        print(f"Time elapsed: {total_time:.2f}s")
        print(f"Entries per second: {large_dataset_size / total_time if total_time > 0 else 0:.2f}")
        print(f"Memory errors: {memory_errors}")

        # System should handle large datasets gracefully
        self.assertEqual(memory_errors, 0, "Should not encounter memory errors with reasonable dataset")
        self.assertLess(total_time, 30, "Should process large dataset within reasonable time")

    @classmethod
    def tearDownClass(cls):
        """Generate load test summary"""
        print(f"\n{'='*60}")
        print("LOAD TEST SUMMARY")
        print(f"{'='*60}")

        for test_name, results in cls.load_results.items():
            print(f"\n{test_name.replace('_', ' ').title()}:")
            for key, value in results.items():
                if isinstance(value, float):
                    print(f"  {key}: {value:.2f}")
                else:
                    print(f"  {key}: {value}")


if __name__ == '__main__':
    # Import statistics for tearDownClass
    import statistics
    unittest.main(verbosity=2)
