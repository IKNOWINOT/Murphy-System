"""
Post-Compilation Enforcer
Enforces rules after packet compilation
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from .models import ExecutionPacket, PacketState

logger = logging.getLogger(__name__)


class PostCompilationEnforcer:
    """
    Enforces post-compilation rules

    After packet creation:
    - Generation disabled
    - No new gates accepted
    - No new artifacts accepted
    - Only execution or abort allowed
    """

    def __init__(self):
        self.compilation_locks: Dict[str, Dict[str, Any]] = {}

    def lock_compilation(
        self,
        packet: ExecutionPacket
    ) -> str:
        """
        Lock compilation for packet

        After locking:
        - No modifications allowed
        - Only execution or abort

        Args:
            packet: Sealed packet

        Returns:
            Lock ID
        """
        if packet.state != PacketState.SEALED:
            raise ValueError("Can only lock sealed packets")

        lock_id = f"lock_{packet.packet_id}_{datetime.now(timezone.utc).timestamp()}"

        self.compilation_locks[packet.packet_id] = {
            'lock_id': lock_id,
            'packet_id': packet.packet_id,
            'locked_at': datetime.now(timezone.utc).isoformat(),
            'generation_disabled': True,
            'gates_frozen': True,
            'artifacts_frozen': True
        }

        return lock_id

    def is_locked(self, packet_id: str) -> bool:
        """Check if packet is locked"""
        return packet_id in self.compilation_locks

    def check_generation_allowed(
        self,
        packet_id: str
    ) -> Tuple[bool, str]:
        """
        Check if generation is allowed

        Args:
            packet_id: Packet ID

        Returns:
            (allowed, reason)
        """
        if not self.is_locked(packet_id):
            return True, "Packet not locked"

        lock = self.compilation_locks[packet_id]

        if lock['generation_disabled']:
            return False, "Generation disabled after packet compilation"

        return True, "Generation allowed"

    def check_gate_acceptance(
        self,
        packet_id: str
    ) -> Tuple[bool, str]:
        """
        Check if new gates can be accepted

        Args:
            packet_id: Packet ID

        Returns:
            (allowed, reason)
        """
        if not self.is_locked(packet_id):
            return True, "Packet not locked"

        lock = self.compilation_locks[packet_id]

        if lock['gates_frozen']:
            return False, "Gates frozen after packet compilation"

        return True, "Gates can be accepted"

    def check_artifact_acceptance(
        self,
        packet_id: str
    ) -> Tuple[bool, str]:
        """
        Check if new artifacts can be accepted

        Args:
            packet_id: Packet ID

        Returns:
            (allowed, reason)
        """
        if not self.is_locked(packet_id):
            return True, "Packet not locked"

        lock = self.compilation_locks[packet_id]

        if lock['artifacts_frozen']:
            return False, "Artifacts frozen after packet compilation"

        return True, "Artifacts can be accepted"

    def validate_post_compilation_state(
        self,
        packet: ExecutionPacket
    ) -> Tuple[bool, List[str]]:
        """
        Validate that post-compilation rules are enforced

        Args:
            packet: Packet to validate

        Returns:
            (valid, violations)
        """
        violations = []

        if not self.is_locked(packet.packet_id):
            violations.append("Packet not locked")
            return False, violations

        lock = self.compilation_locks[packet.packet_id]

        # Check generation disabled
        if not lock['generation_disabled']:
            violations.append("Generation not disabled")

        # Check gates frozen
        if not lock['gates_frozen']:
            violations.append("Gates not frozen")

        # Check artifacts frozen
        if not lock['artifacts_frozen']:
            violations.append("Artifacts not frozen")

        return len(violations) == 0, violations

    def allow_execution(
        self,
        packet: ExecutionPacket
    ) -> Tuple[bool, List[str]]:
        """
        Check if execution is allowed

        Args:
            packet: Packet to execute

        Returns:
            (allowed, blockers)
        """
        blockers = []

        # Check packet state
        if packet.state != PacketState.SEALED:
            blockers.append(f"Packet not sealed (state: {packet.state.value})")

        # Check if locked
        if not self.is_locked(packet.packet_id):
            blockers.append("Packet not locked")

        # Check packet can execute
        can_execute, exec_blockers = packet.can_execute()
        if not can_execute:
            blockers.extend(exec_blockers)

        return len(blockers) == 0, blockers

    def allow_abort(
        self,
        packet: ExecutionPacket
    ) -> Tuple[bool, str]:
        """
        Check if abort is allowed

        Abort is always allowed for locked packets

        Args:
            packet: Packet to abort

        Returns:
            (allowed, reason)
        """
        if not self.is_locked(packet.packet_id):
            return False, "Packet not locked"

        return True, "Abort allowed"

    def unlock_compilation(
        self,
        packet_id: str,
        reason: str
    ) -> bool:
        """
        Unlock compilation (after execution or abort)

        Args:
            packet_id: Packet ID
            reason: Reason for unlocking

        Returns:
            Success
        """
        if packet_id not in self.compilation_locks:
            return False

        lock = self.compilation_locks[packet_id]
        lock['unlocked_at'] = datetime.now(timezone.utc).isoformat()
        lock['unlock_reason'] = reason

        # Remove lock
        del self.compilation_locks[packet_id]

        return True

    def get_lock_status(
        self,
        packet_id: str
    ) -> Dict[str, Any]:
        """
        Get lock status for packet

        Args:
            packet_id: Packet ID

        Returns:
            Lock status
        """
        if packet_id not in self.compilation_locks:
            return {
                'locked': False,
                'packet_id': packet_id
            }

        lock = self.compilation_locks[packet_id]

        return {
            'locked': True,
            'packet_id': packet_id,
            'lock_id': lock['lock_id'],
            'locked_at': lock['locked_at'],
            'generation_disabled': lock['generation_disabled'],
            'gates_frozen': lock['gates_frozen'],
            'artifacts_frozen': lock['artifacts_frozen']
        }
