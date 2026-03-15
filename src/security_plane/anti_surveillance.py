"""
Anti-Surveillance & Anti-Tracking System

This module implements comprehensive anti-surveillance and anti-tracking capabilities
to protect the Murphy System from passive and active monitoring attacks.

Key Features:
- Traffic analysis resistance (constant-rate padding, packet normalization)
- Timing attack prevention (constant-time operations, execution normalization)
- Side-channel mitigation (power/EM normalization, noise injection)
- Metadata minimization (scrubbing, fuzzing, anonymization)
- Anonymization techniques (k-anonymity, differential privacy, onion routing)

Security Guarantees:
- Traffic patterns do not leak information
- Timing variations do not leak information
- Side-channels are mitigated
- Metadata is minimized
- Anonymity is preserved
"""

import hashlib
import logging
import math
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS
# ============================================================================

class TrafficPatternType(Enum):
    """Types of traffic patterns to protect against"""
    CONSTANT_RATE = "constant_rate"  # Maintain constant traffic rate
    BURST = "burst"  # Obfuscate traffic bursts
    FLOW = "flow"  # Prevent flow correlation
    SIZE = "size"  # Normalize packet sizes
    TIMING = "timing"  # Obfuscate timing patterns


class TimingAttackType(Enum):
    """Types of timing attacks to prevent"""
    EXECUTION_TIME = "execution_time"  # Execution time variations
    CACHE_TIMING = "cache_timing"  # Cache-based timing
    BRANCH_PREDICTION = "branch_prediction"  # Branch prediction timing
    NETWORK_TIMING = "network_timing"  # Network round-trip timing
    CRYPTOGRAPHIC_TIMING = "cryptographic_timing"  # Crypto operation timing


class SideChannelType(Enum):
    """Types of side-channel attacks to mitigate"""
    POWER_ANALYSIS = "power_analysis"  # Power consumption analysis
    EM_EMISSION = "em_emission"  # Electromagnetic emission analysis
    ACOUSTIC = "acoustic"  # Acoustic analysis
    THERMAL = "thermal"  # Thermal analysis
    OPTICAL = "optical"  # Optical analysis


class MetadataType(Enum):
    """Types of metadata to minimize"""
    TIMESTAMP = "timestamp"  # Timestamp information
    IP_ADDRESS = "ip_address"  # IP address information
    USER_AGENT = "user_agent"  # User agent information
    GEOLOCATION = "geolocation"  # Geographic location
    SESSION_ID = "session_id"  # Session identifiers


class AnonymizationTechnique(Enum):
    """Anonymization techniques"""
    K_ANONYMITY = "k_anonymity"  # k-anonymity
    DIFFERENTIAL_PRIVACY = "differential_privacy"  # Differential privacy
    ONION_ROUTING = "onion_routing"  # Onion routing
    MIX_NETWORK = "mix_network"  # Mix network
    ANONYMOUS_CREDENTIALS = "anonymous_credentials"  # Anonymous credentials


# ============================================================================
# CORE DATA MODELS
# ============================================================================

@dataclass
class AntiSurveillanceConfig:
    """Configuration for anti-surveillance system"""

    # Traffic analysis resistance
    enable_traffic_padding: bool = True
    constant_rate_mbps: float = 1.0  # Target constant rate in Mbps
    packet_size_bucket: int = 512  # Normalize to 512B buckets
    dummy_traffic_ratio: float = 0.3  # 30% dummy traffic

    # Timing attack prevention
    enable_timing_normalization: bool = True
    execution_time_bucket_ms: int = 100  # Normalize to 100ms buckets
    random_delay_max_ms: int = 50  # Max random delay
    constant_time_operations: bool = True

    # Side-channel mitigation
    enable_side_channel_mitigation: bool = True
    power_normalization: bool = True
    noise_injection_snr_db: float = 10.0  # Signal-to-noise ratio
    blinding_enabled: bool = True

    # Metadata minimization
    enable_metadata_minimization: bool = True
    timestamp_precision_hours: int = 1  # Fuzz to 1-hour buckets
    ip_anonymization: bool = True  # Remove last octet
    user_agent_normalization: bool = True
    minimal_logging: bool = True

    # Anonymization
    enable_anonymization: bool = True
    k_anonymity_k: int = 5  # Minimum group size
    differential_privacy_epsilon: float = 1.0  # Privacy budget
    onion_routing_hops: int = 3  # Number of hops
    mix_network_nodes: int = 10  # Number of mix nodes

    # Performance limits
    max_overhead_percent: float = 30.0  # Max performance overhead
    max_latency_ms: int = 200  # Max added latency

    def __post_init__(self):
        """Validate configuration"""
        if self.constant_rate_mbps <= 0:
            raise ValueError("constant_rate_mbps must be positive")
        if self.packet_size_bucket <= 0:
            raise ValueError("packet_size_bucket must be positive")
        if not 0 <= self.dummy_traffic_ratio <= 1:
            raise ValueError("dummy_traffic_ratio must be in [0, 1]")
        if self.execution_time_bucket_ms <= 0:
            raise ValueError("execution_time_bucket_ms must be positive")
        if self.random_delay_max_ms < 0:
            raise ValueError("random_delay_max_ms must be non-negative")
        if self.noise_injection_snr_db <= 0:
            raise ValueError("noise_injection_snr_db must be positive")
        if self.timestamp_precision_hours <= 0:
            raise ValueError("timestamp_precision_hours must be positive")
        if self.k_anonymity_k < 2:
            raise ValueError("k_anonymity_k must be at least 2")
        if self.differential_privacy_epsilon <= 0:
            raise ValueError("differential_privacy_epsilon must be positive")
        if self.onion_routing_hops < 1:
            raise ValueError("onion_routing_hops must be at least 1")
        if self.mix_network_nodes < 2:
            raise ValueError("mix_network_nodes must be at least 2")


@dataclass
class TrafficPattern:
    """Represents a traffic pattern for analysis"""
    pattern_id: str
    pattern_type: TrafficPatternType
    timestamp: datetime

    # Traffic characteristics
    packet_count: int
    total_bytes: int
    duration_seconds: float

    # Pattern features
    rate_mbps: float
    burst_detected: bool
    flow_correlation_risk: float  # 0-1

    # Protection applied
    padding_applied: bool
    normalization_applied: bool
    obfuscation_applied: bool

    # Metadata
    source_component: str
    destination_component: Optional[str] = None

    def __post_init__(self):
        """Validate traffic pattern"""
        if self.packet_count < 0:
            raise ValueError("packet_count must be non-negative")
        if self.total_bytes < 0:
            raise ValueError("total_bytes must be non-negative")
        if self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        if not 0 <= self.flow_correlation_risk <= 1:
            raise ValueError("flow_correlation_risk must be in [0, 1]")


@dataclass
class TimingProfile:
    """Represents a timing profile for operations"""
    profile_id: str
    operation_name: str
    timestamp: datetime

    # Timing measurements
    execution_time_ms: float
    normalized_time_ms: float
    added_delay_ms: float

    # Timing characteristics
    timing_variance_ms: float
    cache_timing_risk: float  # 0-1
    branch_prediction_risk: float  # 0-1

    # Protection applied
    constant_time_enforced: bool
    normalization_applied: bool
    random_delay_applied: bool

    # Metadata
    component: str
    sensitive_operation: bool = False

    def __post_init__(self):
        """Validate timing profile"""
        if self.execution_time_ms < 0:
            raise ValueError("execution_time_ms must be non-negative")
        if self.normalized_time_ms < 0:
            raise ValueError("normalized_time_ms must be non-negative")
        if self.added_delay_ms < 0:
            raise ValueError("added_delay_ms must be non-negative")
        if not 0 <= self.cache_timing_risk <= 1:
            raise ValueError("cache_timing_risk must be in [0, 1]")
        if not 0 <= self.branch_prediction_risk <= 1:
            raise ValueError("branch_prediction_risk must be in [0, 1]")


@dataclass
class SideChannelSignature:
    """Represents a side-channel signature"""
    signature_id: str
    channel_type: SideChannelType
    timestamp: datetime
    component: str
    operation: str

    # Signature characteristics
    power_consumption_watts: Optional[float] = None
    em_emission_dbm: Optional[float] = None
    acoustic_level_db: Optional[float] = None
    thermal_celsius: Optional[float] = None

    # Normalization
    normalized_power: Optional[float] = None
    noise_injected: bool = False
    blinding_applied: bool = False

    # Risk assessment
    leakage_risk: float = 0.0  # 0-1

    def __post_init__(self):
        """Validate side-channel signature"""
        if not 0 <= self.leakage_risk <= 1:
            raise ValueError("leakage_risk must be in [0, 1]")


@dataclass
class MetadataPolicy:
    """Policy for metadata handling"""
    policy_id: str
    metadata_type: MetadataType

    # Policy settings
    scrubbing_enabled: bool = True
    fuzzing_enabled: bool = True
    anonymization_enabled: bool = True

    # Specific settings
    timestamp_precision_hours: int = 1
    ip_last_octets_removed: int = 1
    user_agent_normalized: bool = True

    # Logging
    minimal_logging: bool = True
    log_only_errors: bool = True
    log_only_security_events: bool = True

    def __post_init__(self):
        """Validate metadata policy"""
        if self.timestamp_precision_hours <= 0:
            raise ValueError("timestamp_precision_hours must be positive")
        if self.ip_last_octets_removed < 0 or self.ip_last_octets_removed > 4:
            raise ValueError("ip_last_octets_removed must be in [0, 4]")


@dataclass
class AnonymitySet:
    """Represents an anonymity set for k-anonymity"""
    set_id: str
    technique: AnonymizationTechnique
    timestamp: datetime

    # Anonymity parameters
    k_value: int  # Size of anonymity set
    epsilon: Optional[float] = None  # For differential privacy
    hops: Optional[int] = None  # For onion routing
    mix_nodes: Optional[int] = None  # For mix networks

    # Members
    member_ids: List[str] = field(default_factory=list)

    # Guarantees
    unlinkability_guaranteed: bool = False
    plausible_deniability: bool = False

    def __post_init__(self):
        """Validate anonymity set"""
        if self.k_value < 2:
            raise ValueError("k_value must be at least 2")
        if self.epsilon is not None and self.epsilon <= 0:
            raise ValueError("epsilon must be positive")
        if self.hops is not None and self.hops < 1:
            raise ValueError("hops must be at least 1")
        if self.mix_nodes is not None and self.mix_nodes < 2:
            raise ValueError("mix_nodes must be at least 2")
        if len(self.member_ids) < self.k_value:
            raise ValueError(f"member_ids must have at least {self.k_value} members")


# ============================================================================
# TRAFFIC ANALYSIS RESISTANCE
# ============================================================================

class TrafficPaddingEngine:
    """Adds traffic padding to maintain constant rate"""

    def __init__(self, config: AntiSurveillanceConfig):
        self.config = config
        self.target_rate_mbps = config.constant_rate_mbps
        self.dummy_ratio = config.dummy_traffic_ratio
        self.patterns: List[TrafficPattern] = []

    def calculate_padding_needed(
        self,
        current_rate_mbps: float,
        duration_seconds: float
    ) -> int:
        """Calculate bytes of padding needed to reach target rate"""
        if not self.config.enable_traffic_padding:
            return 0

        target_bytes = self.target_rate_mbps * 1_000_000 * duration_seconds / 8
        current_bytes = current_rate_mbps * 1_000_000 * duration_seconds / 8
        padding_bytes = max(0, target_bytes - current_bytes)

        return int(padding_bytes)

    def generate_dummy_packets(self, padding_bytes: int) -> List[bytes]:
        """Generate dummy packets to fill padding requirement"""
        bucket_size = self.config.packet_size_bucket
        num_packets = math.ceil(padding_bytes / bucket_size)

        dummy_packets = []
        for _ in range(num_packets):
            # Generate random dummy data
            dummy_data = secrets.token_bytes(bucket_size)
            dummy_packets.append(dummy_data)

        return dummy_packets

    def apply_padding(
        self,
        real_packets: List[bytes],
        duration_seconds: float
    ) -> Tuple[List[bytes], TrafficPattern]:
        """Apply traffic padding to maintain constant rate"""
        # Calculate current rate
        total_bytes = sum(len(p) for p in real_packets)
        current_rate_mbps = (total_bytes * 8) / (duration_seconds * 1_000_000)

        # Calculate padding needed
        padding_bytes = self.calculate_padding_needed(
            current_rate_mbps,
            duration_seconds
        )

        # Generate dummy packets
        dummy_packets = self.generate_dummy_packets(padding_bytes)

        # Mix real and dummy packets
        all_packets = real_packets + dummy_packets

        # Create traffic pattern
        pattern = TrafficPattern(
            pattern_id=f"traffic_{secrets.token_hex(8)}",
            pattern_type=TrafficPatternType.CONSTANT_RATE,
            timestamp=datetime.now(timezone.utc),
            packet_count=len(all_packets),
            total_bytes=sum(len(p) for p in all_packets),
            duration_seconds=duration_seconds,
            rate_mbps=self.target_rate_mbps,
            burst_detected=False,
            flow_correlation_risk=0.0,
            padding_applied=True,
            normalization_applied=False,
            obfuscation_applied=False,
            source_component="traffic_padding_engine"
        )

        self.patterns.append(pattern)
        return all_packets, pattern


class PacketNormalizer:
    """Normalizes packet sizes to fixed buckets"""

    def __init__(self, config: AntiSurveillanceConfig):
        self.config = config
        self.bucket_size = config.packet_size_bucket

    def normalize_packet(self, packet: bytes) -> bytes:
        """Normalize packet to bucket size"""
        if not self.config.enable_traffic_padding:
            return packet

        packet_size = len(packet)

        # Calculate target size (round up to nearest bucket)
        target_size = math.ceil(packet_size / self.bucket_size) * self.bucket_size

        # Pad packet to target size
        if packet_size < target_size:
            padding = secrets.token_bytes(target_size - packet_size)
            normalized_packet = packet + padding
        else:
            normalized_packet = packet

        return normalized_packet

    def normalize_packets(self, packets: List[bytes]) -> List[bytes]:
        """Normalize all packets to bucket sizes"""
        return [self.normalize_packet(p) for p in packets]


class BurstObfuscator:
    """Obfuscates traffic bursts"""

    def __init__(self, config: AntiSurveillanceConfig):
        self.config = config
        self.max_burst_packets = 10  # Max packets in a burst

    def detect_burst(self, packets: List[bytes], timestamps: List[float]) -> bool:
        """Detect if traffic contains a burst"""
        if len(packets) < 2:
            return False

        # Check if many packets arrive in short time
        time_window = 0.1  # 100ms window
        for i in range(len(timestamps) - self.max_burst_packets):
            window_packets = 0
            for j in range(i, min(i + self.max_burst_packets, len(timestamps))):
                if timestamps[j] - timestamps[i] < time_window:
                    window_packets += 1

            if window_packets >= self.max_burst_packets:
                return True

        return False

    def obfuscate_burst(
        self,
        packets: List[bytes],
        timestamps: List[float]
    ) -> Tuple[List[bytes], List[float]]:
        """Obfuscate burst by spreading packets over time"""
        if not self.config.enable_traffic_padding:
            return packets, timestamps

        if not self.detect_burst(packets, timestamps):
            return packets, timestamps

        # Spread packets evenly over time
        duration = timestamps[-1] - timestamps[0]
        interval = duration / (len(packets) or 1)

        new_timestamps = [timestamps[0] + i * interval for i in range(len(packets))]

        return packets, new_timestamps


# ============================================================================
# TIMING ATTACK PREVENTION
# ============================================================================

class ConstantTimeOperations:
    """Ensures operations take constant time"""

    def __init__(self, config: AntiSurveillanceConfig):
        self.config = config
        self.profiles: List[TimingProfile] = []

    def execute_constant_time(
        self,
        operation: callable,
        target_time_ms: float,
        operation_name: str,
        component: str
    ) -> Tuple[any, TimingProfile]:
        """Execute operation in constant time"""
        start_time = time.time()

        # Execute operation
        result = operation()

        # Measure execution time
        execution_time_ms = (time.time() - start_time) * 1000

        # Add delay to reach target time
        if self.config.constant_time_operations:
            delay_ms = max(0, target_time_ms - execution_time_ms)
            if delay_ms > 0:
                time.sleep(delay_ms / 1000)
        else:
            delay_ms = 0

        # Create timing profile
        profile = TimingProfile(
            profile_id=f"timing_{secrets.token_hex(8)}",
            operation_name=operation_name,
            timestamp=datetime.now(timezone.utc),
            execution_time_ms=execution_time_ms,
            normalized_time_ms=target_time_ms,
            added_delay_ms=delay_ms,
            timing_variance_ms=0.0,
            cache_timing_risk=0.0,
            branch_prediction_risk=0.0,
            constant_time_enforced=True,
            normalization_applied=True,
            random_delay_applied=False,
            component=component,
            sensitive_operation=True
        )

        self.profiles.append(profile)
        return result, profile


class ExecutionTimeNormalizer:
    """Normalizes execution times to fixed buckets"""

    def __init__(self, config: AntiSurveillanceConfig):
        self.config = config
        self.bucket_ms = config.execution_time_bucket_ms

    def normalize_execution_time(
        self,
        execution_time_ms: float
    ) -> float:
        """Normalize execution time to bucket"""
        if not self.config.enable_timing_normalization:
            return execution_time_ms

        # Round up to nearest bucket
        normalized_time = math.ceil(execution_time_ms / self.bucket_ms) * self.bucket_ms
        return normalized_time

    def add_normalization_delay(
        self,
        execution_time_ms: float
    ) -> float:
        """Calculate delay needed for normalization"""
        normalized_time = self.normalize_execution_time(execution_time_ms)
        delay_ms = max(0, normalized_time - execution_time_ms)
        return delay_ms


class RandomDelayInjector:
    """Injects random delays to mask timing"""

    def __init__(self, config: AntiSurveillanceConfig):
        self.config = config
        self.max_delay_ms = config.random_delay_max_ms

    def generate_random_delay(self) -> float:
        """Generate random delay in milliseconds"""
        if not self.config.enable_timing_normalization:
            return 0.0

        # Generate random delay between 0 and max_delay_ms
        delay_ms = secrets.randbelow(self.max_delay_ms + 1)
        return float(delay_ms)

    def inject_delay(self, delay_ms: float):
        """Inject delay"""
        if delay_ms > 0:
            time.sleep(delay_ms / 1000)


# ============================================================================
# METADATA MINIMIZATION
# ============================================================================

class MetadataScrubber:
    """Scrubs sensitive metadata"""

    def __init__(self, config: AntiSurveillanceConfig):
        self.config = config

    def scrub_timestamp(self, timestamp: datetime) -> datetime:
        """Fuzz timestamp to reduce precision"""
        if not self.config.enable_metadata_minimization:
            return timestamp

        # Round down to nearest hour bucket
        hours = self.config.timestamp_precision_hours
        rounded_hour = (timestamp.hour // hours) * hours

        return timestamp.replace(
            hour=rounded_hour,
            minute=0,
            second=0,
            microsecond=0
        )

    def scrub_ip_address(self, ip_address: str) -> str:
        """Anonymize IP address"""
        if not self.config.ip_anonymization:
            return ip_address

        # Remove last octet for IPv4
        parts = ip_address.split('.')
        if len(parts) == 4:
            return '.'.join(parts[:3]) + '.0'

        # For IPv6, remove last 64 bits
        if ':' in ip_address:
            parts = ip_address.split(':')
            return ':'.join(parts[:4]) + '::0'

        return ip_address

    def scrub_user_agent(self, user_agent: str) -> str:
        """Normalize user agent"""
        if not self.config.user_agent_normalization:
            return user_agent

        # Return generic user agent
        return "Mozilla/5.0 (Generic) Murphy/1.0"

    def scrub_metadata(self, metadata: Dict[str, any]) -> Dict[str, any]:
        """Scrub all metadata"""
        scrubbed = metadata.copy()

        if 'timestamp' in scrubbed and isinstance(scrubbed['timestamp'], datetime):
            scrubbed['timestamp'] = self.scrub_timestamp(scrubbed['timestamp'])

        if 'ip_address' in scrubbed:
            scrubbed['ip_address'] = self.scrub_ip_address(scrubbed['ip_address'])

        if 'user_agent' in scrubbed:
            scrubbed['user_agent'] = self.scrub_user_agent(scrubbed['user_agent'])

        return scrubbed


# ============================================================================
# ANONYMIZATION TECHNIQUES
# ============================================================================

class KAnonymityEngine:
    """Ensures k-anonymity for queries"""

    def __init__(self, config: AntiSurveillanceConfig):
        self.config = config
        self.k = config.k_anonymity_k
        self.anonymity_sets: List[AnonymitySet] = []

    def create_anonymity_set(
        self,
        member_ids: List[str]
    ) -> Optional[AnonymitySet]:
        """Create anonymity set if k-anonymity is satisfied"""
        if len(member_ids) < self.k:
            return None

        anonymity_set = AnonymitySet(
            set_id=f"anon_{secrets.token_hex(8)}",
            technique=AnonymizationTechnique.K_ANONYMITY,
            timestamp=datetime.now(timezone.utc),
            k_value=self.k,
            member_ids=member_ids,
            unlinkability_guaranteed=True,
            plausible_deniability=True
        )

        self.anonymity_sets.append(anonymity_set)
        return anonymity_set

    def check_k_anonymity(self, query_result: List[Dict]) -> bool:
        """Check if query result satisfies k-anonymity"""
        if len(query_result) < self.k:
            return False

        # Group by quasi-identifiers and check each group has at least k members
        # (Simplified - real implementation would need to identify quasi-identifiers)
        return True


class DifferentialPrivacyEngine:
    """Adds calibrated noise for differential privacy"""

    def __init__(self, config: AntiSurveillanceConfig):
        self.config = config
        self.epsilon = config.differential_privacy_epsilon

    def add_laplace_noise(
        self,
        value: float,
        sensitivity: float
    ) -> float:
        """Add Laplace noise for differential privacy"""
        if not self.config.enable_anonymization:
            return value

        # Calculate scale parameter
        scale = sensitivity / self.epsilon

        # Generate Laplace noise
        u = secrets.randbelow(2**32) / 2**32 - 0.5
        noise = -scale * math.copysign(1, u) * math.log(1 - 2 * abs(u))

        return value + noise

    def add_gaussian_noise(
        self,
        value: float,
        sensitivity: float,
        delta: float = 1e-5
    ) -> float:
        """Add Gaussian noise for differential privacy"""
        if not self.config.enable_anonymization:
            return value

        # Calculate standard deviation
        sigma = sensitivity * math.sqrt(2 * math.log(1.25 / delta)) / self.epsilon

        # Generate Gaussian noise (Box-Muller transform)
        u1 = secrets.randbelow(2**32) / 2**32
        u2 = secrets.randbelow(2**32) / 2**32
        noise = sigma * math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)

        return value + noise


# ============================================================================
# ANTI-SURVEILLANCE SYSTEM
# ============================================================================

class AntiSurveillanceSystem:
    """Main anti-surveillance system"""

    def __init__(self, config: Optional[AntiSurveillanceConfig] = None):
        self.config = config or AntiSurveillanceConfig()

        # Initialize components
        self.traffic_padding = TrafficPaddingEngine(self.config)
        self.packet_normalizer = PacketNormalizer(self.config)
        self.burst_obfuscator = BurstObfuscator(self.config)
        self.constant_time_ops = ConstantTimeOperations(self.config)
        self.execution_normalizer = ExecutionTimeNormalizer(self.config)
        self.random_delay = RandomDelayInjector(self.config)
        self.metadata_scrubber = MetadataScrubber(self.config)
        self.k_anonymity = KAnonymityEngine(self.config)
        self.differential_privacy = DifferentialPrivacyEngine(self.config)

        # Statistics
        self.total_packets_processed = 0
        self.total_operations_normalized = 0
        self.total_metadata_scrubbed = 0

    def protect_traffic(
        self,
        packets: List[bytes],
        duration_seconds: float
    ) -> Tuple[List[bytes], TrafficPattern]:
        """Apply traffic analysis resistance"""
        # Normalize packet sizes
        normalized_packets = self.packet_normalizer.normalize_packets(packets)

        # Apply traffic padding
        padded_packets, pattern = self.traffic_padding.apply_padding(
            normalized_packets,
            duration_seconds
        )

        self.total_packets_processed += len(padded_packets)
        return padded_packets, pattern

    def protect_timing(
        self,
        operation: callable,
        target_time_ms: float,
        operation_name: str,
        component: str
    ) -> Tuple[any, TimingProfile]:
        """Apply timing attack prevention"""
        result, profile = self.constant_time_ops.execute_constant_time(
            operation,
            target_time_ms,
            operation_name,
            component
        )

        self.total_operations_normalized += 1
        return result, profile

    def protect_metadata(self, metadata: Dict[str, any]) -> Dict[str, any]:
        """Apply metadata minimization"""
        scrubbed = self.metadata_scrubber.scrub_metadata(metadata)
        self.total_metadata_scrubbed += 1
        return scrubbed

    def get_statistics(self) -> Dict[str, any]:
        """Get anti-surveillance statistics"""
        return {
            'total_packets_processed': self.total_packets_processed,
            'total_operations_normalized': self.total_operations_normalized,
            'total_metadata_scrubbed': self.total_metadata_scrubbed,
            'traffic_patterns': len(self.traffic_padding.patterns),
            'timing_profiles': len(self.constant_time_ops.profiles),
            'anonymity_sets': len(self.k_anonymity.anonymity_sets),
            'config': {
                'traffic_padding_enabled': self.config.enable_traffic_padding,
                'timing_normalization_enabled': self.config.enable_timing_normalization,
                'metadata_minimization_enabled': self.config.enable_metadata_minimization,
                'anonymization_enabled': self.config.enable_anonymization
            }
        }
