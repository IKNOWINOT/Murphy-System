"""
Resource Availability Checker System
Checks resource availability to improve UR (Uncertainty in Resources) calculations.
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
from pydantic import BaseModel, Field
import asyncio


class ResourceType(str, Enum):
    """Types of resources."""
    COMPUTE = "compute"
    MEMORY = "memory"
    STORAGE = "storage"
    NETWORK = "network"
    API_QUOTA = "api_quota"
    DATABASE_CONNECTION = "database_connection"
    HUMAN_EXPERT = "human_expert"
    FINANCIAL = "financial"
    TIME = "time"
    EXTERNAL_SERVICE = "external_service"


class ResourceStatus(str, Enum):
    """Status of a resource."""
    AVAILABLE = "available"
    LIMITED = "limited"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class ResourceUnit(str, Enum):
    """Units for measuring resources."""
    PERCENTAGE = "percentage"
    GIGABYTES = "gigabytes"
    MEGABYTES = "megabytes"
    CORES = "cores"
    REQUESTS_PER_MINUTE = "requests_per_minute"
    CONNECTIONS = "connections"
    HOURS = "hours"
    DOLLARS = "dollars"
    COUNT = "count"


class Resource(BaseModel):
    """Represents a resource."""
    id: str
    name: str
    resource_type: ResourceType
    total_capacity: float
    available_capacity: float
    unit: ResourceUnit
    status: ResourceStatus = ResourceStatus.AVAILABLE
    last_checked: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def utilization_percentage(self) -> float:
        """Calculate utilization percentage."""
        if self.total_capacity == 0:
            return 0.0
        return ((self.total_capacity - self.available_capacity) / self.total_capacity) * 100
    
    def availability_percentage(self) -> float:
        """Calculate availability percentage."""
        if self.total_capacity == 0:
            return 0.0
        return (self.available_capacity / self.total_capacity) * 100
    
    def is_sufficient(self, required_amount: float) -> bool:
        """Check if resource has sufficient capacity."""
        return self.available_capacity >= required_amount


class ResourceRequirement(BaseModel):
    """Represents a resource requirement."""
    resource_type: ResourceType
    required_amount: float
    unit: ResourceUnit
    priority: int = Field(ge=1, le=5, default=3)  # 1=low, 5=critical
    duration_hours: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ResourceAvailabilityCheck(BaseModel):
    """Result of a resource availability check."""
    resource_id: str
    resource_type: ResourceType
    is_available: bool
    available_amount: float
    required_amount: float
    sufficiency_score: float = Field(ge=0.0, le=1.0)
    status: ResourceStatus
    checked_at: datetime = Field(default_factory=datetime.utcnow)
    issues: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class ResourceAllocationPlan(BaseModel):
    """Plan for allocating resources."""
    plan_id: str
    requirements: List[ResourceRequirement]
    allocations: Dict[str, float] = Field(default_factory=dict)
    feasible: bool
    confidence: float = Field(ge=0.0, le=1.0)
    estimated_cost: Optional[float] = None
    estimated_duration: Optional[float] = None
    constraints: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ResourceMonitor:
    """
    Monitors resource availability and usage.
    """
    
    def __init__(self):
        self.resources: Dict[str, Resource] = {}
        self.usage_history: Dict[str, List[Tuple[datetime, float]]] = {}
    
    def register_resource(self, resource: Resource) -> str:
        """Register a resource for monitoring."""
        self.resources[resource.id] = resource
        self.usage_history[resource.id] = []
        return resource.id
    
    def update_resource(
        self,
        resource_id: str,
        available_capacity: float,
        status: Optional[ResourceStatus] = None
    ):
        """Update resource availability."""
        resource = self.resources.get(resource_id)
        if not resource:
            return
        
        resource.available_capacity = available_capacity
        resource.last_checked = datetime.utcnow()
        
        if status:
            resource.status = status
        else:
            # Auto-determine status based on availability
            availability_pct = resource.availability_percentage()
            if availability_pct > 80:
                resource.status = ResourceStatus.AVAILABLE
            elif availability_pct > 50:
                resource.status = ResourceStatus.LIMITED
            elif availability_pct > 20:
                resource.status = ResourceStatus.DEGRADED
            else:
                resource.status = ResourceStatus.UNAVAILABLE
        
        # Record usage history
        utilization = resource.utilization_percentage()
        self.usage_history[resource_id].append((datetime.utcnow(), utilization))
        
        # Keep only last 1000 entries
        if len(self.usage_history[resource_id]) > 1000:
            self.usage_history[resource_id] = self.usage_history[resource_id][-1000:]
    
    def get_resource(self, resource_id: str) -> Optional[Resource]:
        """Get resource by ID."""
        return self.resources.get(resource_id)
    
    def get_resources_by_type(self, resource_type: ResourceType) -> List[Resource]:
        """Get all resources of a specific type."""
        return [r for r in self.resources.values() if r.resource_type == resource_type]
    
    def get_usage_trend(
        self,
        resource_id: str,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Get usage trend for a resource."""
        history = self.usage_history.get(resource_id, [])
        if not history:
            return {"trend": "unknown", "average_utilization": 0.0}
        
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent_history = [(ts, util) for ts, util in history if ts >= cutoff]
        
        if not recent_history:
            return {"trend": "no_data", "average_utilization": 0.0}
        
        utilizations = [util for _, util in recent_history]
        avg_utilization = sum(utilizations) / len(utilizations)
        
        # Determine trend
        if len(utilizations) > 1:
            mid = len(utilizations) // 2
            first_half_avg = sum(utilizations[:mid]) / mid
            second_half_avg = sum(utilizations[mid:]) / (len(utilizations) - mid)
            
            if second_half_avg > first_half_avg * 1.2:
                trend = "increasing"
            elif second_half_avg < first_half_avg * 0.8:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "stable"
        
        return {
            "trend": trend,
            "average_utilization": avg_utilization,
            "current_utilization": utilizations[-1] if utilizations else 0.0,
            "peak_utilization": max(utilizations) if utilizations else 0.0
        }


class ResourceAvailabilityChecker:
    """
    Checks resource availability against requirements.
    """
    
    def __init__(self, monitor: ResourceMonitor):
        self.monitor = monitor
    
    async def check_resource_availability(
        self,
        resource_id: str,
        required_amount: float
    ) -> ResourceAvailabilityCheck:
        """
        Check if a resource has sufficient availability.
        
        Args:
            resource_id: ID of the resource to check
            required_amount: Amount of resource required
            
        Returns:
            ResourceAvailabilityCheck with availability status
        """
        resource = self.monitor.get_resource(resource_id)
        
        if not resource:
            return ResourceAvailabilityCheck(
                resource_id=resource_id,
                resource_type=ResourceType.COMPUTE,
                is_available=False,
                available_amount=0.0,
                required_amount=required_amount,
                sufficiency_score=0.0,
                status=ResourceStatus.UNKNOWN,
                issues=["Resource not found"],
                recommendations=["Register resource before checking availability"]
            )
        
        # Check availability
        is_available = resource.is_sufficient(required_amount)
        
        # Calculate sufficiency score
        if required_amount == 0:
            sufficiency_score = 1.0
        else:
            sufficiency_score = min(resource.available_capacity / required_amount, 1.0)
        
        # Identify issues
        issues = []
        recommendations = []
        
        if not is_available:
            issues.append(f"Insufficient {resource.resource_type}: need {required_amount}, have {resource.available_capacity}")
            recommendations.append(f"Free up {required_amount - resource.available_capacity} {resource.unit}")
        
        if resource.status == ResourceStatus.DEGRADED:
            issues.append("Resource is in degraded state")
            recommendations.append("Investigate resource health")
        
        if resource.status == ResourceStatus.UNAVAILABLE:
            issues.append("Resource is unavailable")
            recommendations.append("Wait for resource to become available or use alternative")
        
        # Check usage trend
        trend = self.monitor.get_usage_trend(resource_id)
        if trend["trend"] == "increasing" and trend["average_utilization"] > 70:
            issues.append("Resource utilization is increasing")
            recommendations.append("Consider scaling up resource capacity")
        
        return ResourceAvailabilityCheck(
            resource_id=resource_id,
            resource_type=resource.resource_type,
            is_available=is_available,
            available_amount=resource.available_capacity,
            required_amount=required_amount,
            sufficiency_score=sufficiency_score,
            status=resource.status,
            issues=issues,
            recommendations=recommendations
        )
    
    async def check_multiple_resources(
        self,
        requirements: List[Tuple[str, float]]
    ) -> List[ResourceAvailabilityCheck]:
        """
        Check multiple resources in parallel.
        
        Args:
            requirements: List of (resource_id, required_amount) tuples
            
        Returns:
            List of ResourceAvailabilityCheck results
        """
        tasks = [
            self.check_resource_availability(resource_id, amount)
            for resource_id, amount in requirements
        ]
        return await asyncio.gather(*tasks)
    
    def check_resource_by_type(
        self,
        resource_type: ResourceType,
        required_amount: float
    ) -> Optional[ResourceAvailabilityCheck]:
        """
        Check availability for any resource of a given type.
        
        Args:
            resource_type: Type of resource needed
            required_amount: Amount required
            
        Returns:
            ResourceAvailabilityCheck for best available resource, or None
        """
        resources = self.monitor.get_resources_by_type(resource_type)
        
        if not resources:
            return None
        
        # Find resource with most available capacity
        best_resource = max(resources, key=lambda r: r.available_capacity)
        
        # Use asyncio.run for synchronous context
        return asyncio.run(
            self.check_resource_availability(best_resource.id, required_amount)
        )


class ResourceAllocator:
    """
    Allocates resources based on requirements and availability.
    """
    
    def __init__(self, checker: ResourceAvailabilityChecker):
        self.checker = checker
    
    async def create_allocation_plan(
        self,
        requirements: List[ResourceRequirement]
    ) -> ResourceAllocationPlan:
        """
        Create a resource allocation plan.
        
        Args:
            requirements: List of resource requirements
            
        Returns:
            ResourceAllocationPlan with allocations and feasibility
        """
        plan_id = f"plan_{datetime.utcnow().timestamp()}"
        allocations = {}
        feasible = True
        confidence_scores = []
        constraints = []
        estimated_cost = 0.0
        
        for req in requirements:
            # Find available resource of this type
            check = self.checker.check_resource_by_type(
                req.resource_type,
                req.required_amount
            )
            
            if not check:
                feasible = False
                constraints.append(f"No {req.resource_type} resources registered")
                confidence_scores.append(0.0)
                continue
            
            if not check.is_available:
                if req.priority >= 4:  # Critical priority
                    feasible = False
                constraints.append(f"Insufficient {req.resource_type}")
            
            allocations[check.resource_id] = req.required_amount
            confidence_scores.append(check.sufficiency_score)
            
            # Estimate cost (placeholder - would use actual pricing)
            if req.resource_type == ResourceType.COMPUTE:
                estimated_cost += req.required_amount * 0.10  # $0.10 per core-hour
            elif req.resource_type == ResourceType.STORAGE:
                estimated_cost += req.required_amount * 0.02  # $0.02 per GB
        
        # Calculate overall confidence
        overall_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        
        return ResourceAllocationPlan(
            plan_id=plan_id,
            requirements=requirements,
            allocations=allocations,
            feasible=feasible,
            confidence=overall_confidence,
            estimated_cost=estimated_cost,
            constraints=constraints
        )


class URCalculator:
    """
    Calculates UR (Uncertainty in Resources) using availability checks.
    Integrates with Murphy's uncertainty framework.
    """
    
    def __init__(self, allocator: ResourceAllocator):
        self.allocator = allocator
    
    async def calculate_ur(
        self,
        requirements: List[ResourceRequirement]
    ) -> float:
        """
        Calculate UR score for resource requirements.
        
        Args:
            requirements: List of resource requirements
            
        Returns:
            UR score (0.0 to 1.0, where 0 = certain, 1 = highly uncertain)
        """
        plan = await self.allocator.create_allocation_plan(requirements)
        
        # UR is inverse of confidence
        ur_score = 1.0 - plan.confidence
        
        # Increase uncertainty if not feasible
        if not plan.feasible:
            ur_score = max(ur_score, 0.8)
        
        return ur_score
    
    async def calculate_ur_detailed(
        self,
        requirements: List[ResourceRequirement],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calculate UR with detailed breakdown.
        
        Args:
            requirements: List of resource requirements
            context: Additional context
            
        Returns:
            Dictionary with UR score and detailed breakdown
        """
        plan = await self.allocator.create_allocation_plan(requirements)
        ur_score = 1.0 - plan.confidence
        
        if not plan.feasible:
            ur_score = max(ur_score, 0.8)
        
        return {
            "ur_score": ur_score,
            "confidence": plan.confidence,
            "feasible": plan.feasible,
            "allocations": plan.allocations,
            "constraints": plan.constraints,
            "estimated_cost": plan.estimated_cost,
            "requirements_count": len(requirements),
            "critical_requirements": sum(1 for r in requirements if r.priority >= 4)
        }


class ResourceAvailabilitySystem:
    """
    Complete resource availability checking system.
    Provides unified interface for resource monitoring and UR calculation.
    """
    
    def __init__(self):
        self.monitor = ResourceMonitor()
        self.checker = ResourceAvailabilityChecker(self.monitor)
        self.allocator = ResourceAllocator(self.checker)
        self.ur_calculator = URCalculator(self.allocator)
    
    def register_resource(
        self,
        name: str,
        resource_type: ResourceType,
        total_capacity: float,
        available_capacity: float,
        unit: ResourceUnit,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Register a new resource."""
        resource = Resource(
            id=f"{resource_type}_{datetime.utcnow().timestamp()}",
            name=name,
            resource_type=resource_type,
            total_capacity=total_capacity,
            available_capacity=available_capacity,
            unit=unit,
            metadata=metadata or {}
        )
        return self.monitor.register_resource(resource)
    
    def update_resource(
        self,
        resource_id: str,
        available_capacity: float,
        status: Optional[ResourceStatus] = None
    ):
        """Update resource availability."""
        self.monitor.update_resource(resource_id, available_capacity, status)
    
    async def check_availability(
        self,
        resource_id: str,
        required_amount: float
    ) -> ResourceAvailabilityCheck:
        """Check resource availability."""
        return await self.checker.check_resource_availability(resource_id, required_amount)
    
    async def calculate_ur(
        self,
        requirements: List[ResourceRequirement]
    ) -> float:
        """Calculate UR score."""
        return await self.ur_calculator.calculate_ur(requirements)
    
    async def calculate_ur_detailed(
        self,
        requirements: List[ResourceRequirement],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Calculate UR with detailed breakdown."""
        return await self.ur_calculator.calculate_ur_detailed(requirements, context)
    
    def get_resource_status(self, resource_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a resource."""
        resource = self.monitor.get_resource(resource_id)
        if not resource:
            return None
        
        trend = self.monitor.get_usage_trend(resource_id)
        
        return {
            "resource_id": resource.id,
            "name": resource.name,
            "type": resource.resource_type,
            "status": resource.status,
            "total_capacity": resource.total_capacity,
            "available_capacity": resource.available_capacity,
            "utilization_percentage": resource.utilization_percentage(),
            "availability_percentage": resource.availability_percentage(),
            "unit": resource.unit,
            "last_checked": resource.last_checked.isoformat(),
            "usage_trend": trend
        }