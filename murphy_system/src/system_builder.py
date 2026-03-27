"""
System Builder - Translates non-technical requests into technical architectures
Reading level: High school student
"""
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("system_builder")

class SystemBuilder:
    """
    Builds system architecture from natural language descriptions
    Converts non-technical input into technical specifications
    """

    def __init__(self):
        # Technical terms translation dictionary
        self.term_translations = {
            # Non-technical → Technical
            "store data": "database",
            "save information": "persistent storage",
            "show website": "web frontend",
            "make it work": "implementation",
            "keep it safe": "security layer",
            "make it fast": "performance optimization",
            "connect things": "API integration",
            "talk to other systems": "system integration",
            "show pictures": "image handling",
            "handle users": "user management",
            "login": "authentication",
            "remember": "session management",
            "check if it's right": "validation",
            "stop bad stuff": "security gates",
            "keep track": "logging and monitoring",
            "make decisions": "decision engine",
            "learn from data": "machine learning",
            "think": "AI reasoning",
            "understand": "natural language processing",
            "talk like a person": "conversational interface",
            "organize": "data structuring",
            "search": "query engine",
            "filter": "data filtering",
            "sort": "data sorting",
            "count": "aggregation",
            "add new things": "CRUD operations",
            "change things": "update operations",
            "remove things": "delete operations",
            "see everything": "dashboard",
            "control it": "control panel",
            "watch it": "monitoring system",
            "fix it when it breaks": "error handling",
            "make sure it works": "testing",
            "keep it running": "uptime management",
            "make it grow": "scalability",
            "handle lots of people": "load balancing",
            "work on phones": "mobile compatibility",
            "work on computers": "desktop compatibility"
        }

        # Common system patterns
        self.system_patterns = {
            "web_app": {
                "name": "Web Application",
                "description": "A system accessible through a web browser",
                "components": [
                    "Frontend (user interface)",
                    "Backend (server logic)",
                    "Database (data storage)",
                    "API (communication layer)"
                ],
                "layers": ["presentation", "application", "data"]
            },
            "data_system": {
                "name": "Data Management System",
                "description": "A system for storing and managing information",
                "components": [
                    "Data collector",
                    "Data processor",
                    "Data storage",
                    "Data retriever"
                ],
                "layers": ["collection", "processing", "storage", "retrieval"]
            },
            "ai_system": {
                "name": "AI-Powered System",
                "description": "A system that uses artificial intelligence",
                "components": [
                    "Input processor",
                    "AI model",
                    "Decision engine",
                    "Output generator"
                ],
                "layers": ["input", "processing", "reasoning", "output"]
            },
            "control_system": {
                "name": "Control System",
                "description": "A system that manages and controls processes",
                "components": [
                    "Controller",
                    "Actuator",
                    "Sensor",
                    "Feedback loop"
                ],
                "layers": ["sensing", "control", "actuation", "feedback"]
            }
        }

    def build_architecture(self, analysis: Dict[str, Any],
                          selected_modules: List[str]) -> Dict[str, Any]:
        """
        Build technical architecture from non-technical analysis

        Args:
            analysis: Request analysis (intent, domain, complexity)
            selected_modules: Modules to use for building

        Returns:
            Technical architecture specification
        """
        # Determine system pattern based on domain
        pattern_key = self._determine_pattern(analysis['domain'])
        pattern = self.system_patterns.get(pattern_key, self.system_patterns['web_app'])

        # Build components
        components = self._build_components(pattern, analysis['complexity'])

        # Build layers
        layers = self._build_layers(pattern['layers'])

        # Add technical specifications
        specs = self._generate_specs(components, analysis['complexity'])

        # Add module integration points
        integration = self._add_integration_points(components, selected_modules)

        return {
            "system_type": pattern['name'],
            "description": pattern['description'],
            "components": components,
            "layers": layers,
            "specifications": specs,
            "integration": integration,
            "complexity": analysis['complexity']
        }

    def _determine_pattern(self, domain: str) -> str:
        """Determine which system pattern to use"""
        pattern_map = {
            "web": "web_app",
            "data": "data_system",
            "ai": "ai_system",
            "system": "control_system"
        }
        return pattern_map.get(domain, "web_app")

    def _build_components(self, pattern: Dict, complexity: str) -> List[Dict[str, Any]]:
        """Build components based on pattern and complexity"""
        base_components = pattern['components']

        # Expand based on complexity
        if complexity == "simple":
            # Keep minimal components
            components = [
                {
                    "name": comp,
                    "type": self._classify_component(comp),
                    "complexity": "low"
                }
                for comp in base_components[:2]
            ]
        elif complexity == "complex":
            # Add advanced components
            components = [
                {
                    "name": comp,
                    "type": self._classify_component(comp),
                    "complexity": "high",
                    "features": self._get_advanced_features(comp)
                }
                for comp in base_components
            ]
        else:  # medium
            components = [
                {
                    "name": comp,
                    "type": self._classify_component(comp),
                    "complexity": "medium"
                }
                for comp in base_components
            ]

        return components

    def _classify_component(self, component_name: str) -> str:
        """Classify component type"""
        component_lower = component_name.lower()

        if any(word in component_lower for word in ["frontend", "interface", "ui", "user"]):
            return "presentation"
        elif any(word in component_lower for word in ["backend", "server", "logic", "engine"]):
            return "application"
        elif any(word in component_lower for word in ["database", "storage", "data"]):
            return "data"
        elif any(word in component_lower for word in ["api", "communication", "connection"]):
            return "integration"
        else:
            return "utility"

    def _get_advanced_features(self, component_name: str) -> List[str]:
        """Get advanced features for complex components"""
        features_map = {
            "Frontend (user interface)": [
                "Responsive design",
                "Real-time updates",
                "User authentication",
                "Access control"
            ],
            "Backend (server logic)": [
                "API endpoints",
                "Business logic",
                "Error handling",
                "Logging"
            ],
            "Database (data storage)": [
                "Data modeling",
                "Query optimization",
                "Backup system",
                "Data validation"
            ],
            "API (communication layer)": [
                "RESTful design",
                "Rate limiting",
                "Authentication",
                "Documentation"
            ]
        }
        return features_map.get(component_name, [])

    def _build_layers(self, layer_names: List[str]) -> List[Dict[str, Any]]:
        """Build system layers"""
        layers = []
        for i, layer_name in enumerate(layer_names):
            layers.append({
                "order": i + 1,
                "name": layer_name,
                "responsibility": self._describe_layer(layer_name),
                "components": self._get_layer_components(layer_name)
            })
        return layers

    def _describe_layer(self, layer_name: str) -> str:
        """Describe what a layer does in simple terms"""
        descriptions = {
            "presentation": "Shows information to users and gets their input",
            "application": "Makes decisions and processes information",
            "data": "Stores and retrieves information safely",
            "collection": "Gathers information from sources",
            "processing": "Transforms and analyzes information",
            "storage": "Keeps information organized and safe",
            "retrieval": "Finds and returns information when needed",
            "input": "Receives information from users or systems",
            "reasoning": "Thinks about information and makes decisions",
            "output": "Presents results to users",
            "sensing": "Detects what's happening in the system",
            "control": "Makes decisions about what to do",
            "actuation": "Takes action based on decisions",
            "feedback": "Checks if actions worked correctly"
        }
        return descriptions.get(layer_name, "Performs system functions")

    def _get_layer_components(self, layer_name: str) -> List[str]:
        """Get components that belong to a layer"""
        component_map = {
            "presentation": ["User interface", "Input forms", "Display system"],
            "application": ["Business logic", "Decision engine", "Processing units"],
            "data": ["Database", "Cache", "Data validator"],
            "collection": ["Data collectors", "Input processors"],
            "processing": ["Data transformers", "Analyzers"],
            "storage": ["Database systems", "File storage"],
            "retrieval": ["Query engine", "Search system"],
            "input": ["Input receivers", "Parsers"],
            "reasoning": ["AI models", "Decision trees"],
            "output": ["Response generators", "Formatters"],
            "sensing": ["Sensors", "Monitors"],
            "control": ["Controllers", "Decision makers"],
            "actuation": ["Actuators", "Executors"],
            "feedback": ["Feedback collectors", "Analyzers"]
        }
        return component_map.get(layer_name, ["System components"])

    def _generate_specs(self, components: List[Dict],
                       complexity: str) -> Dict[str, Any]:
        """Generate technical specifications"""
        specs = {
            "performance": self._get_performance_specs(complexity),
            "security": self._get_security_specs(complexity),
            "scalability": self._get_scalability_specs(complexity),
            "reliability": self._get_reliability_specs(complexity)
        }
        return specs

    def _get_performance_specs(self, complexity: str) -> Dict[str, str]:
        """Get performance specifications"""
        if complexity == "simple":
            return {
                "response_time": "< 1 second",
                "throughput": "10-100 requests/minute",
                "capacity": "Small datasets"
            }
        elif complexity == "complex":
            return {
                "response_time": "< 100ms",
                "throughput": "10,000+ requests/minute",
                "capacity": "Large datasets, high load"
            }
        else:  # medium
            return {
                "response_time": "< 500ms",
                "throughput": "100-1000 requests/minute",
                "capacity": "Medium datasets"
            }

    def _get_security_specs(self, complexity: str) -> Dict[str, str]:
        """Get security specifications"""
        if complexity == "simple":
            return {
                "authentication": "Basic authentication",
                "authorization": "Role-based access",
                "encryption": "Data at rest"
            }
        elif complexity == "complex":
            return {
                "authentication": "Multi-factor authentication",
                "authorization": "Attribute-based access",
                "encryption": "End-to-end encryption",
                "compliance": "Industry standards"
            }
        else:  # medium
            return {
                "authentication": "Standard authentication",
                "authorization": "Role-based access",
                "encryption": "Data in transit and at rest"
            }

    def _get_scalability_specs(self, complexity: str) -> Dict[str, str]:
        """Get scalability specifications"""
        if complexity == "simple":
            return {
                "horizontal_scaling": "Not required",
                "vertical_scaling": "Basic optimization",
                "load_balancing": "Not needed"
            }
        elif complexity == "complex":
            return {
                "horizontal_scaling": "Auto-scaling",
                "vertical_scaling": "Optimized",
                "load_balancing": "Advanced load distribution"
            }
        else:  # medium
            return {
                "horizontal_scaling": "Manual scaling",
                "vertical_scaling": "Standard optimization",
                "load_balancing": "Basic load distribution"
            }

    def _get_reliability_specs(self, complexity: str) -> Dict[str, str]:
        """Get reliability specifications"""
        if complexity == "simple":
            return {
                "uptime": "99% availability",
                "backup": "Manual backups",
                "disaster_recovery": "Basic recovery plan"
            }
        elif complexity == "complex":
            return {
                "uptime": "99.99% availability",
                "backup": "Automated backups",
                "disaster_recovery": "Multi-region failover"
            }
        else:  # medium
            return {
                "uptime": "99.9% availability",
                "backup": "Scheduled backups",
                "disaster_recovery": "Recovery plan in place"
            }

    def _add_integration_points(self, components: List[Dict],
                               modules: List[str]) -> Dict[str, List[str]]:
        """Add module integration points to components"""
        integration = {}

        for component in components:
            comp_name = component['name']
            integration[comp_name] = self._determine_integrations(comp_name, modules)

        return integration

    def _determine_integrations(self, component_name: str,
                               modules: List[str]) -> List[str]:
        """Determine which modules integrate with a component"""
        integrations = []

        # SystemBuilder integrates with most things
        if "SystemBuilder" in modules:
            integrations.append("Architecture definition")
            integrations.append("Component configuration")

        # GateBuilder integrates with control components
        if "GateBuilder" in modules:
            if any(word in component_name.lower()
                   for word in ["control", "logic", "decision", "engine"]):
                integrations.append("Gate injection")
                integrations.append("Safety constraints")

        # TaskExecutor integrates with action components
        if "TaskExecutor" in modules:
            if any(word in component_name.lower()
                   for word in ["backend", "processor", "executor", "actuation"]):
                integrations.append("Task execution")
                integrations.append("Operation handling")

        return integrations

# Initialize for easy import
system_builder = SystemBuilder()

# Convenience methods added to SystemBuilder for test compatibility
def _build_system(self, user_request: str = "", domain: str = "", **kwargs):
    """Convenience method: build system architecture from a request."""
    analysis = {"domain": domain or "web_app", "name": user_request, "request": user_request, "complexity": "medium"}
    architecture = self.build_architecture(analysis, selected_modules=[])
    return {"architecture": architecture, "success": True, "domain": domain}

def _get_system_patterns(self):
    """Convenience method: get available system patterns."""
    return dict(self.system_patterns)

SystemBuilder.build_system = _build_system
SystemBuilder.get_system_patterns = _get_system_patterns

if __name__ == "__main__":
    logger.info("System Builder Module")
    logger.info("Translates non-technical requests into technical architectures")
