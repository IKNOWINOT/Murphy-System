"""
Gate Builder - Creates safety gates for any system
Reading level: High school student
"""
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("gate_builder")

class GateBuilder:
    """
    Creates safety gates (protections) for systems
    Gates stop bad things from happening
    """

    def __init__(self):
        # Common safety concerns and their gates
        self.safety_concerns = {
            "data_loss": {
                "name": "Data Loss Prevention Gate",
                "description": "Makes sure important information isn't lost",
                "trigger": "Before any delete or remove operation",
                "check": "Verify backup exists and data can be recovered"
            },
            "security_breach": {
                "name": "Security Gate",
                "description": "Stops unauthorized people from accessing the system",
                "trigger": "Before any access request",
                "check": "Verify user has permission and is who they say they are"
            },
            "invalid_input": {
                "name": "Input Validation Gate",
                "description": "Makes sure information entered is correct and safe",
                "trigger": "Before processing any user input",
                "check": "Check format, type, and content of input"
            },
            "system_overload": {
                "name": "Load Balancing Gate",
                "description": "Prevents the system from getting too busy",
                "trigger": "Before accepting new requests",
                "check": "Check if system has capacity to handle more work"
            },
            "data_corruption": {
                "name": "Data Integrity Gate",
                "description": "Makes sure information stays accurate",
                "trigger": "Before saving any data",
                "check": "Verify data is valid and consistent"
            },
            "unauthorized_action": {
                "name": "Authorization Gate",
                "description": "Makes sure users can only do what they're allowed to",
                "trigger": "Before any action that changes data",
                "check": "Verify user has permission for this specific action"
            },
            "performance_degradation": {
                "name": "Performance Gate",
                "description": "Keeps the system running fast",
                "trigger": "Before any heavy operation",
                "check": "Check if operation will slow down the system"
            },
            "compliance_violation": {
                "name": "Compliance Gate",
                "description": "Makes sure the system follows rules and laws",
                "trigger": "Before any operation involving sensitive data",
                "check": "Verify operation complies with regulations"
            },
            "resource_exhaustion": {
                "name": "Resource Gate",
                "description": "Prevents running out of memory, storage, or other resources",
                "trigger": "Before any resource-intensive operation",
                "check": "Verify enough resources are available"
            },
            "dependency_failure": {
                "name": "Dependency Gate",
                "description": "Makes sure needed services are available",
                "trigger": "Before any operation that depends on other services",
                "check": "Verify all dependencies are working"
            }
        }

        # System-specific gate templates
        self.system_gate_templates = {
            "web_app": [
                "security_breach",
                "invalid_input",
                "system_overload",
                "unauthorized_action"
            ],
            "data_system": [
                "data_loss",
                "data_corruption",
                "compliance_violation",
                "resource_exhaustion"
            ],
            "ai_system": [
                "invalid_input",
                "performance_degradation",
                "resource_exhaustion",
                "compliance_violation"
            ],
            "control_system": [
                "dependency_failure",
                "security_breach",
                "resource_exhaustion",
                "performance_degradation"
            ]
        }

    def build_gates(self, analysis: Dict[str, Any],
                   architecture: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Build safety gates for a system

        Args:
            analysis: Request analysis (intent, domain, complexity)
            architecture: System architecture specification

        Returns:
            List of gates to implement
        """
        gates = []

        # Determine which gate template to use
        system_type = self._determine_system_type(analysis['domain'])
        gate_keys = self.system_gate_templates.get(
            system_type,
            self.system_gate_templates['web_app']
        )

        # Add gates based on template
        for gate_key in gate_keys:
            gate = self.safety_concerns[gate_key].copy()
            gate["gate_id"] = f"GATE-{len(gates):03d}"
            gate["severity"] = self._get_gate_severity(gate_key, analysis['complexity'])
            gate["risk_reduction"] = self._calculate_risk_reduction(gate_key)
            gates.append(gate)

        # Add custom gates based on complexity
        if analysis['complexity'] == "complex":
            custom_gates = self._generate_complex_gates(architecture)
            gates.extend(custom_gates)

        return gates

    def _determine_system_type(self, domain: str) -> str:
        """Determine which gate template to use"""
        type_map = {
            "web": "web_app",
            "data": "data_system",
            "ai": "ai_system",
            "system": "control_system"
        }
        return type_map.get(domain, "web_app")

    def _get_gate_severity(self, gate_key: str, complexity: str) -> str:
        """Get the severity level of a gate"""
        # High severity gates
        high_severity = ["security_breach", "data_loss", "data_corruption"]

        if gate_key in high_severity:
            return "critical"
        elif complexity == "complex":
            return "high"
        else:
            return "medium"

    def _calculate_risk_reduction(self, gate_key: str) -> float:
        """Calculate how much risk this gate reduces (0.0 to 1.0)"""
        risk_reduction_map = {
            "security_breach": 0.9,
            "data_loss": 0.95,
            "invalid_input": 0.7,
            "system_overload": 0.6,
            "data_corruption": 0.85,
            "unauthorized_action": 0.8,
            "performance_degradation": 0.5,
            "compliance_violation": 0.9,
            "resource_exhaustion": 0.75,
            "dependency_failure": 0.7
        }
        return risk_reduction_map.get(gate_key, 0.5)

    def _generate_complex_gates(self, architecture: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate additional gates for complex systems"""
        gates = []

        # Add monitoring gate
        gates.append({
            "gate_id": "GATE-MON",
            "name": "Monitoring Gate",
            "description": "Keeps track of how the system is doing",
            "trigger": "Continuously",
            "check": "Collect metrics and check for problems",
            "severity": "medium",
            "risk_reduction": 0.4
        })

        # Add rollback gate
        gates.append({
            "gate_id": "GATE-RBK",
            "name": "Rollback Gate",
            "description": "Can undo changes if something goes wrong",
            "trigger": "Before any major change",
            "check": "Prepare backup and rollback plan",
            "severity": "high",
            "risk_reduction": 0.85
        })

        # Add notification gate
        gates.append({
            "gate_id": "GATE-NTF",
            "name": "Notification Gate",
            "description": "Tells the right people when something happens",
            "trigger": "When important events occur",
            "check": "Verify recipients and message content",
            "severity": "low",
            "risk_reduction": 0.3
        })

        return gates

    def get_gate_implementation_guide(self, gate: Dict[str, Any]) -> str:
        """
        Generate implementation guide for a gate
        Reading level: High school student
        """
        guide = f"""
## {gate['name']} ({gate['gate_id']})

**What it does:** {gate['description']}

**When it activates:** {gate['trigger']}

**What it checks:** {gate['check']}

**How important is it:** {gate['severity'].upper()}

**How much risk it removes:** {gate['risk_reduction'] * 100:.0f}%

### How to implement it:

1. **Set up the trigger**
   - Determine when this gate should activate
   - Add code to detect the trigger condition

2. **Implement the check**
   - Write code that performs the check
   - Make sure it returns true/false (pass/fail)

3. **Handle failures**
   - Decide what happens when the gate fails
   - Common options: Block, Warn, Log, Retry

4. **Test it**
   - Test with both passing and failing conditions
   - Make sure it doesn't slow down the system too much

### Example:

```
# Pseudocode example
if gate_check_fails():
    log_error("Gate {{gate_id}} failed")
    return error_response
else:
    continue_with_operation()
```
"""
        return guide

# Initialize for easy import
gate_builder = GateBuilder()

if __name__ == "__main__":
    logger.info("Gate Builder Module")
    logger.info("Creates safety gates for any system")
