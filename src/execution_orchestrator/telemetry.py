"""
Telemetry Streaming
===================

Real-time telemetry event emission and streaming during execution.

Features:
- Event emission (execution lifecycle events)
- Real-time streaming (WebSocket/SSE support)
- Telemetry aggregation (metrics calculation)
- Confidence delta tracking (confidence changes over time)

Design Principle: Complete observability of execution state
"""

import json
import logging
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

logger = logging.getLogger("execution_orchestrator.telemetry")

from .models import StepResult, TelemetryEvent, TelemetryEventType, TelemetryStream


class TelemetryStreamer:
    """
    Streams telemetry events during execution

    Provides:
    - Event emission
    - Real-time streaming
    - Metric aggregation
    - Confidence tracking
    """

    def __init__(self):
        self.streams: Dict[str, TelemetryStream] = {}
        self.subscribers: Dict[str, List[Callable]] = {}

    def create_stream(self, packet_id: str) -> TelemetryStream:
        """Create new telemetry stream for packet execution"""
        stream = TelemetryStream(packet_id=packet_id)
        self.streams[packet_id] = stream
        self.subscribers[packet_id] = []
        return stream

    def emit_event(
        self,
        packet_id: str,
        event_type: TelemetryEventType,
        step_id: Optional[str],
        data: Dict,
        risk_score: float,
        confidence_score: float
    ):
        """
        Emit telemetry event

        Args:
            packet_id: Packet being executed
            event_type: Type of event
            step_id: Step ID (if applicable)
            data: Event data
            risk_score: Current risk score
            confidence_score: Current confidence score
        """
        # Create event
        event = TelemetryEvent(
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            packet_id=packet_id,
            step_id=step_id,
            data=data,
            risk_score=risk_score,
            confidence_score=confidence_score
        )

        # Add to stream
        if packet_id in self.streams:
            self.streams[packet_id].add_event(event)

        # Notify subscribers
        self._notify_subscribers(packet_id, event)

    def emit_execution_start(
        self,
        packet_id: str,
        total_steps: int,
        risk_score: float,
        confidence_score: float
    ):
        """Emit execution start event"""
        self.emit_event(
            packet_id=packet_id,
            event_type=TelemetryEventType.EXECUTION_START,
            step_id=None,
            data={
                'total_steps': total_steps,
                'start_time': datetime.now(timezone.utc).isoformat()
            },
            risk_score=risk_score,
            confidence_score=confidence_score
        )

    def emit_step_start(
        self,
        packet_id: str,
        step_id: str,
        step_index: int,
        step_type: str,
        risk_score: float,
        confidence_score: float
    ):
        """Emit step start event"""
        self.emit_event(
            packet_id=packet_id,
            event_type=TelemetryEventType.STEP_START,
            step_id=step_id,
            data={
                'step_index': step_index,
                'step_type': step_type,
                'start_time': datetime.now(timezone.utc).isoformat()
            },
            risk_score=risk_score,
            confidence_score=confidence_score
        )

    def emit_step_complete(
        self,
        packet_id: str,
        step_result: StepResult,
        risk_score: float,
        confidence_score: float
    ):
        """Emit step complete event"""
        self.emit_event(
            packet_id=packet_id,
            event_type=TelemetryEventType.STEP_COMPLETE,
            step_id=step_result.step_id,
            data={
                'success': step_result.success,
                'duration_ms': step_result.duration_ms,
                'risk_delta': step_result.risk_delta,
                'confidence_delta': step_result.confidence_delta
            },
            risk_score=risk_score,
            confidence_score=confidence_score
        )

    def emit_step_failed(
        self,
        packet_id: str,
        step_result: StepResult,
        risk_score: float,
        confidence_score: float
    ):
        """Emit step failed event"""
        self.emit_event(
            packet_id=packet_id,
            event_type=TelemetryEventType.STEP_FAILED,
            step_id=step_result.step_id,
            data={
                'error': step_result.error,
                'duration_ms': step_result.duration_ms
            },
            risk_score=risk_score,
            confidence_score=confidence_score
        )

    def emit_risk_threshold_breach(
        self,
        packet_id: str,
        current_risk: float,
        threshold: float,
        confidence_score: float
    ):
        """Emit risk threshold breach event"""
        self.emit_event(
            packet_id=packet_id,
            event_type=TelemetryEventType.RISK_THRESHOLD_BREACH,
            step_id=None,
            data={
                'current_risk': current_risk,
                'threshold': threshold,
                'breach_amount': current_risk - threshold
            },
            risk_score=current_risk,
            confidence_score=confidence_score
        )

    def emit_confidence_drop(
        self,
        packet_id: str,
        old_confidence: float,
        new_confidence: float,
        risk_score: float
    ):
        """Emit confidence drop event"""
        self.emit_event(
            packet_id=packet_id,
            event_type=TelemetryEventType.CONFIDENCE_DROP,
            step_id=None,
            data={
                'old_confidence': old_confidence,
                'new_confidence': new_confidence,
                'drop_amount': old_confidence - new_confidence
            },
            risk_score=risk_score,
            confidence_score=new_confidence
        )

    def emit_interface_failure(
        self,
        packet_id: str,
        interface_id: str,
        error: str,
        risk_score: float,
        confidence_score: float
    ):
        """Emit interface failure event"""
        self.emit_event(
            packet_id=packet_id,
            event_type=TelemetryEventType.INTERFACE_FAILURE,
            step_id=None,
            data={
                'interface_id': interface_id,
                'error': error
            },
            risk_score=risk_score,
            confidence_score=confidence_score
        )

    def emit_rollback_start(
        self,
        packet_id: str,
        reason: str,
        risk_score: float,
        confidence_score: float
    ):
        """Emit rollback start event"""
        self.emit_event(
            packet_id=packet_id,
            event_type=TelemetryEventType.ROLLBACK_START,
            step_id=None,
            data={
                'reason': reason,
                'start_time': datetime.now(timezone.utc).isoformat()
            },
            risk_score=risk_score,
            confidence_score=confidence_score
        )

    def emit_rollback_complete(
        self,
        packet_id: str,
        success: bool,
        risk_score: float,
        confidence_score: float
    ):
        """Emit rollback complete event"""
        self.emit_event(
            packet_id=packet_id,
            event_type=TelemetryEventType.ROLLBACK_COMPLETE,
            step_id=None,
            data={
                'success': success,
                'end_time': datetime.now(timezone.utc).isoformat()
            },
            risk_score=risk_score,
            confidence_score=confidence_score
        )

    def emit_execution_paused(
        self,
        packet_id: str,
        reason: str,
        risk_score: float,
        confidence_score: float
    ):
        """Emit execution paused event"""
        self.emit_event(
            packet_id=packet_id,
            event_type=TelemetryEventType.EXECUTION_PAUSED,
            step_id=None,
            data={
                'reason': reason,
                'pause_time': datetime.now(timezone.utc).isoformat()
            },
            risk_score=risk_score,
            confidence_score=confidence_score
        )

    def emit_execution_resumed(
        self,
        packet_id: str,
        risk_score: float,
        confidence_score: float
    ):
        """Emit execution resumed event"""
        self.emit_event(
            packet_id=packet_id,
            event_type=TelemetryEventType.EXECUTION_RESUMED,
            step_id=None,
            data={
                'resume_time': datetime.now(timezone.utc).isoformat()
            },
            risk_score=risk_score,
            confidence_score=confidence_score
        )

    def emit_execution_complete(
        self,
        packet_id: str,
        total_steps: int,
        successful_steps: int,
        risk_score: float,
        confidence_score: float
    ):
        """Emit execution complete event"""
        self.emit_event(
            packet_id=packet_id,
            event_type=TelemetryEventType.EXECUTION_COMPLETE,
            step_id=None,
            data={
                'total_steps': total_steps,
                'successful_steps': successful_steps,
                'end_time': datetime.now(timezone.utc).isoformat()
            },
            risk_score=risk_score,
            confidence_score=confidence_score
        )

    def emit_execution_failed(
        self,
        packet_id: str,
        error: str,
        risk_score: float,
        confidence_score: float
    ):
        """Emit execution failed event"""
        self.emit_event(
            packet_id=packet_id,
            event_type=TelemetryEventType.EXECUTION_FAILED,
            step_id=None,
            data={
                'error': error,
                'end_time': datetime.now(timezone.utc).isoformat()
            },
            risk_score=risk_score,
            confidence_score=confidence_score
        )

    def subscribe(self, packet_id: str, callback: Callable[[TelemetryEvent], None]):
        """
        Subscribe to telemetry events for a packet

        Args:
            packet_id: Packet to subscribe to
            callback: Function to call with each event
        """
        if packet_id not in self.subscribers:
            self.subscribers[packet_id] = []

        self.subscribers[packet_id].append(callback)

    def unsubscribe(self, packet_id: str, callback: Callable[[TelemetryEvent], None]):
        """Unsubscribe from telemetry events"""
        if packet_id in self.subscribers:
            self.subscribers[packet_id].remove(callback)

    def get_stream(self, packet_id: str) -> Optional[TelemetryStream]:
        """Get telemetry stream for packet"""
        return self.streams.get(packet_id)

    def get_aggregated_metrics(self, packet_id: str) -> Dict:
        """
        Get aggregated metrics for packet execution

        Returns:
            Dictionary with aggregated metrics
        """
        stream = self.streams.get(packet_id)
        if not stream:
            return {}

        events = stream.events

        # Calculate metrics
        total_events = len(events)
        step_starts = len(stream.get_events_by_type(TelemetryEventType.STEP_START))
        step_completes = len(stream.get_events_by_type(TelemetryEventType.STEP_COMPLETE))
        step_failures = len(stream.get_events_by_type(TelemetryEventType.STEP_FAILED))

        # Risk and confidence tracking
        risk_scores = [e.risk_score for e in events]
        confidence_scores = [e.confidence_score for e in events]

        return {
            'packet_id': packet_id,
            'total_events': total_events,
            'step_starts': step_starts,
            'step_completes': step_completes,
            'step_failures': step_failures,
            'success_rate': step_completes / step_starts if step_starts > 0 else 0,
            'risk_scores': {
                'min': min(risk_scores) if risk_scores else 0,
                'max': max(risk_scores) if risk_scores else 0,
                'avg': sum(risk_scores) / len(risk_scores) if risk_scores else 0,
                'current': risk_scores[-1] if risk_scores else 0
            },
            'confidence_scores': {
                'min': min(confidence_scores) if confidence_scores else 0,
                'max': max(confidence_scores) if confidence_scores else 0,
                'avg': sum(confidence_scores) / (len(confidence_scores) or 1) if confidence_scores else 0,
                'current': confidence_scores[-1] if confidence_scores else 0
            }
        }

    def _notify_subscribers(self, packet_id: str, event: TelemetryEvent):
        """Notify all subscribers of new event"""
        if packet_id in self.subscribers:
            for callback in self.subscribers[packet_id]:
                try:
                    callback(event)
                except Exception as exc:
                    logger.info(f"Error notifying subscriber: {exc}")

    def export_stream(self, packet_id: str, output_format: str = 'json') -> str:
        """
        Export telemetry stream to file output_format

        Args:
            packet_id: Packet ID
            output_format: Export format ('json', 'csv')

        Returns:
            Exported data as string
        """
        stream = self.streams.get(packet_id)
        if not stream:
            return ""

        if output_format == 'json':
            return json.dumps(stream.to_dict(), indent=2)
        elif output_format == 'csv':
            # CSV export
            lines = ['timestamp,event_type,step_id,risk_score,confidence_score']
            for event in stream.events:
                lines.append(
                    f"{event.timestamp.isoformat()},"
                    f"{event.event_type.value},"
                    f"{event.step_id or ''},"
                    f"{event.risk_score},"
                    f"{event.confidence_score}"
                )
            return '\n'.join(lines)
        else:
            raise ValueError(f"Unsupported export output_format: {output_format}")
