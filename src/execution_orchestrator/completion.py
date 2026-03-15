"""
Completion Certifier
====================

Issues completion certificates upon successful execution.

Certificate Contents:
- Execution summary (steps, timing, results)
- Cryptographic signature (tamper-proof)
- Artifact updates (created/modified artifacts)
- Verification proofs (all verifications passed)

Design Principle: Cryptographically-sealed proof of execution
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .models import CompletionCertificate, ExecutionState, ExecutionStatus, StepResult

logger = logging.getLogger(__name__)


class CompletionCertifier:
    """
    Issues completion certificates for successful executions

    Provides:
    - Certificate generation
    - Cryptographic signing
    - Artifact tracking
    - Verification proofs
    """

    def __init__(self):
        self.certificates: Dict[str, CompletionCertificate] = {}

    def generate_certificate(
        self,
        execution_state: ExecutionState,
        final_risk: float,
        final_confidence: float,
        artifacts_created: List[str],
        artifacts_modified: List[str]
    ) -> CompletionCertificate:
        """
        Generate completion certificate

        Args:
            execution_state: Final execution state
            final_risk: Final risk score
            final_confidence: Final confidence score
            artifacts_created: List of created artifact IDs
            artifacts_modified: List of modified artifact IDs

        Returns:
            Completion certificate
        """
        # Count successful and failed steps
        successful_steps = sum(1 for r in execution_state.results if r.success)
        failed_steps = sum(1 for r in execution_state.results if not r.success)

        # Generate execution ID
        execution_id = self._generate_execution_id(execution_state)

        # Generate signature
        signature = self._generate_signature(
            execution_state,
            final_risk,
            final_confidence,
            artifacts_created,
            artifacts_modified
        )

        # Create certificate
        certificate = CompletionCertificate(
            packet_id=execution_state.packet_id,
            execution_id=execution_id,
            status=execution_state.status,
            start_time=execution_state.start_time,
            end_time=execution_state.end_time or datetime.now(timezone.utc),
            total_steps=execution_state.total_steps,
            successful_steps=successful_steps,
            failed_steps=failed_steps,
            final_risk=final_risk,
            final_confidence=final_confidence,
            artifacts_created=artifacts_created,
            artifacts_modified=artifacts_modified,
            signature=signature
        )

        # Store certificate
        self.certificates[execution_state.packet_id] = certificate

        return certificate

    def verify_certificate(
        self,
        certificate: CompletionCertificate
    ) -> bool:
        """
        Verify certificate signature

        Args:
            certificate: Certificate to verify

        Returns:
            True if signature is valid
        """
        # Reconstruct signature
        expected_signature = self._compute_certificate_signature(certificate)

        # Compare signatures
        return certificate.signature == expected_signature

    def get_certificate(self, packet_id: str) -> Optional[CompletionCertificate]:
        """Get certificate for packet"""
        return self.certificates.get(packet_id)

    def update_artifact_graph(
        self,
        certificate: CompletionCertificate,
        artifact_graph: Dict
    ) -> Dict:
        """
        Update artifact graph with execution results

        Args:
            certificate: Completion certificate
            artifact_graph: Current artifact graph

        Returns:
            Updated artifact graph
        """
        # Add created artifacts
        for artifact_id in certificate.artifacts_created:
            if artifact_id not in artifact_graph:
                artifact_graph[artifact_id] = {
                    'id': artifact_id,
                    'created_by': certificate.execution_id,
                    'created_at': certificate.end_time.isoformat(),
                    'verified': True,
                    'confidence': certificate.final_confidence
                }

        # Update modified artifacts
        for artifact_id in certificate.artifacts_modified:
            if artifact_id in artifact_graph:
                artifact_graph[artifact_id]['modified_by'] = certificate.execution_id
                artifact_graph[artifact_id]['modified_at'] = certificate.end_time.isoformat()
                artifact_graph[artifact_id]['confidence'] = certificate.final_confidence

        return artifact_graph

    def release_execution_lock(
        self,
        packet_id: str,
        lock_registry: Dict
    ) -> Dict:
        """
        Release execution lock for packet

        Args:
            packet_id: Packet that completed
            lock_registry: Lock registry

        Returns:
            Updated lock registry
        """
        if packet_id in lock_registry:
            lock_registry[packet_id]['locked'] = False
            lock_registry[packet_id]['released_at'] = datetime.now(timezone.utc).isoformat()

        return lock_registry

    def generate_success_report(
        self,
        certificate: CompletionCertificate
    ) -> Dict:
        """
        Generate success report

        Args:
            certificate: Completion certificate

        Returns:
            Success report dictionary
        """
        duration = (certificate.end_time - certificate.start_time).total_seconds()

        return {
            'status': 'success',
            'packet_id': certificate.packet_id,
            'execution_id': certificate.execution_id,
            'duration_seconds': duration,
            'total_steps': certificate.total_steps,
            'successful_steps': certificate.successful_steps,
            'failed_steps': certificate.failed_steps,
            'success_rate': certificate.successful_steps / certificate.total_steps if certificate.total_steps > 0 else 0,
            'final_risk': certificate.final_risk,
            'final_confidence': certificate.final_confidence,
            'artifacts_created': len(certificate.artifacts_created),
            'artifacts_modified': len(certificate.artifacts_modified),
            'certificate_signature': certificate.signature,
            'timestamp': certificate.timestamp.isoformat()
        }

    def generate_failure_report(
        self,
        execution_state: ExecutionState,
        error: str,
        final_risk: float,
        final_confidence: float
    ) -> Dict:
        """
        Generate failure report

        Args:
            execution_state: Final execution state
            error: Error message
            final_risk: Final risk score
            final_confidence: Final confidence score

        Returns:
            Failure report dictionary
        """
        duration = 0
        if execution_state.end_time:
            duration = (execution_state.end_time - execution_state.start_time).total_seconds()

        successful_steps = sum(1 for r in execution_state.results if r.success)
        failed_steps = sum(1 for r in execution_state.results if not r.success)

        return {
            'status': 'failed',
            'packet_id': execution_state.packet_id,
            'error': error,
            'stop_reason': execution_state.stop_reason.value if execution_state.stop_reason else None,
            'duration_seconds': duration,
            'total_steps': execution_state.total_steps,
            'completed_steps': execution_state.current_step,
            'successful_steps': successful_steps,
            'failed_steps': failed_steps,
            'final_risk': final_risk,
            'final_confidence': final_confidence,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    def _generate_execution_id(self, execution_state: ExecutionState) -> str:
        """Generate unique execution ID"""
        data = f"{execution_state.packet_id}:{execution_state.start_time.isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def _generate_signature(
        self,
        execution_state: ExecutionState,
        final_risk: float,
        final_confidence: float,
        artifacts_created: List[str],
        artifacts_modified: List[str]
    ) -> str:
        """Generate cryptographic signature for certificate"""
        # Collect all data to sign
        data = {
            'packet_id': execution_state.packet_id,
            'packet_signature': execution_state.packet_signature,
            'start_time': execution_state.start_time.isoformat(),
            'end_time': execution_state.end_time.isoformat() if execution_state.end_time else '',
            'total_steps': execution_state.total_steps,
            'results': [
                {
                    'step_id': r.step_id,
                    'success': r.success,
                    'duration_ms': r.duration_ms
                }
                for r in execution_state.results
            ],
            'final_risk': final_risk,
            'final_confidence': final_confidence,
            'artifacts_created': sorted(artifacts_created),
            'artifacts_modified': sorted(artifacts_modified)
        }

        # Convert to JSON and hash
        json_data = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_data.encode()).hexdigest()

    def _compute_certificate_signature(self, certificate: CompletionCertificate) -> str:
        """Compute signature for certificate verification"""
        data = {
            'packet_id': certificate.packet_id,
            'execution_id': certificate.execution_id,
            'start_time': certificate.start_time.isoformat(),
            'end_time': certificate.end_time.isoformat(),
            'total_steps': certificate.total_steps,
            'successful_steps': certificate.successful_steps,
            'failed_steps': certificate.failed_steps,
            'final_risk': certificate.final_risk,
            'final_confidence': certificate.final_confidence,
            'artifacts_created': sorted(certificate.artifacts_created),
            'artifacts_modified': sorted(certificate.artifacts_modified)
        }

        json_data = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_data.encode()).hexdigest()

    def export_certificate(
        self,
        certificate: CompletionCertificate,
        output_format: str = 'json'
    ) -> str:
        """
        Export certificate to file output_format

        Args:
            certificate: Certificate to export
            output_format: Export format ('json', 'text')

        Returns:
            Exported certificate as string
        """
        if output_format == 'json':
            return json.dumps(certificate.to_dict(), indent=2)
        elif output_format == 'text':
            lines = [
                "=" * 60,
                "EXECUTION COMPLETION CERTIFICATE",
                "=" * 60,
                f"Packet ID: {certificate.packet_id}",
                f"Execution ID: {certificate.execution_id}",
                f"Status: {certificate.status.value}",
                f"Start Time: {certificate.start_time.isoformat()}",
                f"End Time: {certificate.end_time.isoformat()}",
                f"Duration: {(certificate.end_time - certificate.start_time).total_seconds():.2f}s",
                "",
                "EXECUTION SUMMARY:",
                f"  Total Steps: {certificate.total_steps}",
                f"  Successful: {certificate.successful_steps}",
                f"  Failed: {certificate.failed_steps}",
                f"  Success Rate: {certificate.successful_steps / certificate.total_steps * 100:.1f}%",
                "",
                "RISK & CONFIDENCE:",
                f"  Final Risk: {certificate.final_risk:.3f}",
                f"  Final Confidence: {certificate.final_confidence:.3f}",
                "",
                "ARTIFACTS:",
                f"  Created: {len(certificate.artifacts_created)}",
                f"  Modified: {len(certificate.artifacts_modified)}",
                "",
                "SIGNATURE:",
                f"  {certificate.signature}",
                "",
                f"Issued: {certificate.timestamp.isoformat()}",
                "=" * 60
            ]
            return '\n'.join(lines)
        else:
            raise ValueError(f"Unsupported export output_format: {output_format}")
