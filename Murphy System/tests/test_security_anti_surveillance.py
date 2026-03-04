"""
Test Suite for Anti-Surveillance & Anti-Tracking System

Tests all components of the anti-surveillance system including:
- Traffic analysis resistance
- Timing attack prevention
- Side-channel mitigation
- Metadata minimization
- Anonymization techniques
"""

import pytest
from datetime import datetime, timedelta
import time
import secrets
from typing import List

from src.security_plane.anti_surveillance import (
    # Enums
    TrafficPatternType,
    TimingAttackType,
    SideChannelType,
    MetadataType,
    AnonymizationTechnique,

    # Data Models
    AntiSurveillanceConfig,
    TrafficPattern,
    TimingProfile,
    SideChannelSignature,
    MetadataPolicy,
    AnonymitySet,

    # Components
    TrafficPaddingEngine,
    PacketNormalizer,
    BurstObfuscator,
    ConstantTimeOperations,
    ExecutionTimeNormalizer,
    RandomDelayInjector,
    MetadataScrubber,
    KAnonymityEngine,
    DifferentialPrivacyEngine,
    AntiSurveillanceSystem
)


# ============================================================================
# CONFIGURATION TESTS
# ============================================================================

def test_config_creation():
    """Test anti-surveillance configuration creation"""
    config = AntiSurveillanceConfig()

    assert config.enable_traffic_padding is True
    assert config.constant_rate_mbps == 1.0
    assert config.packet_size_bucket == 512
    assert config.dummy_traffic_ratio == 0.3
    assert config.enable_timing_normalization is True
    assert config.execution_time_bucket_ms == 100
    assert config.enable_metadata_minimization is True
    assert config.k_anonymity_k == 5


def test_config_validation():
    """Test configuration validation"""
    # Invalid constant rate
    with pytest.raises(ValueError, match="constant_rate_mbps must be positive"):
        AntiSurveillanceConfig(constant_rate_mbps=-1.0)

    # Invalid dummy traffic ratio
    with pytest.raises(ValueError, match="dummy_traffic_ratio must be in"):
        AntiSurveillanceConfig(dummy_traffic_ratio=1.5)

    # Invalid k-anonymity
    with pytest.raises(ValueError, match="k_anonymity_k must be at least 2"):
        AntiSurveillanceConfig(k_anonymity_k=1)

    # Invalid epsilon
    with pytest.raises(ValueError, match="differential_privacy_epsilon must be positive"):
        AntiSurveillanceConfig(differential_privacy_epsilon=-1.0)


# ============================================================================
# DATA MODEL TESTS
# ============================================================================

def test_traffic_pattern_creation():
    """Test traffic pattern creation"""
    pattern = TrafficPattern(
        pattern_id="test_pattern",
        pattern_type=TrafficPatternType.CONSTANT_RATE,
        timestamp=datetime.now(),
        packet_count=100,
        total_bytes=51200,
        duration_seconds=1.0,
        rate_mbps=0.4,
        burst_detected=False,
        flow_correlation_risk=0.1,
        padding_applied=True,
        normalization_applied=True,
        obfuscation_applied=False,
        source_component="test"
    )

    assert pattern.pattern_id == "test_pattern"
    assert pattern.packet_count == 100
    assert pattern.padding_applied is True


def test_timing_profile_creation():
    """Test timing profile creation"""
    profile = TimingProfile(
        profile_id="test_profile",
        operation_name="test_operation",
        timestamp=datetime.now(),
        execution_time_ms=50.0,
        normalized_time_ms=100.0,
        added_delay_ms=50.0,
        timing_variance_ms=5.0,
        cache_timing_risk=0.1,
        branch_prediction_risk=0.1,
        constant_time_enforced=True,
        normalization_applied=True,
        random_delay_applied=False,
        component="test",
        sensitive_operation=True
    )

    assert profile.operation_name == "test_operation"
    assert profile.execution_time_ms == 50.0
    assert profile.normalized_time_ms == 100.0


def test_side_channel_signature_creation():
    """Test side-channel signature creation"""
    signature = SideChannelSignature(
        signature_id="test_sig",
        channel_type=SideChannelType.POWER_ANALYSIS,
        timestamp=datetime.now(),
        power_consumption_watts=10.5,
        normalized_power=10.0,
        noise_injected=True,
        blinding_applied=True,
        leakage_risk=0.2,
        component="test",
        operation="encrypt"
    )

    assert signature.channel_type == SideChannelType.POWER_ANALYSIS
    assert signature.power_consumption_watts == 10.5
    assert signature.noise_injected is True


def test_metadata_policy_creation():
    """Test metadata policy creation"""
    policy = MetadataPolicy(
        policy_id="test_policy",
        metadata_type=MetadataType.TIMESTAMP,
        scrubbing_enabled=True,
        fuzzing_enabled=True,
        anonymization_enabled=True,
        timestamp_precision_hours=1,
        ip_last_octets_removed=1,
        minimal_logging=True
    )

    assert policy.metadata_type == MetadataType.TIMESTAMP
    assert policy.scrubbing_enabled is True
    assert policy.timestamp_precision_hours == 1


def test_anonymity_set_creation():
    """Test anonymity set creation"""
    member_ids = [f"user_{i}" for i in range(10)]

    anon_set = AnonymitySet(
        set_id="test_set",
        technique=AnonymizationTechnique.K_ANONYMITY,
        timestamp=datetime.now(),
        k_value=5,
        member_ids=member_ids,
        unlinkability_guaranteed=True,
        plausible_deniability=True
    )

    assert anon_set.k_value == 5
    assert len(anon_set.member_ids) == 10
    assert anon_set.unlinkability_guaranteed is True


def test_anonymity_set_validation():
    """Test anonymity set validation"""
    # Not enough members
    with pytest.raises(ValueError, match="member_ids must have at least"):
        AnonymitySet(
            set_id="test",
            technique=AnonymizationTechnique.K_ANONYMITY,
            timestamp=datetime.now(),
            k_value=5,
            member_ids=["user_1", "user_2"]  # Only 2 members, need 5
        )


# ============================================================================
# TRAFFIC ANALYSIS RESISTANCE TESTS
# ============================================================================

def test_traffic_padding_calculation():
    """Test traffic padding calculation"""
    config = AntiSurveillanceConfig(constant_rate_mbps=1.0)
    engine = TrafficPaddingEngine(config)

    # Current rate is 0.5 Mbps, target is 1.0 Mbps
    padding_bytes = engine.calculate_padding_needed(
        current_rate_mbps=0.5,
        duration_seconds=1.0
    )

    # Should need 0.5 Mbps * 1 second = 62,500 bytes
    assert padding_bytes == 62_500


def test_traffic_padding_application():
    """Test traffic padding application"""
    config = AntiSurveillanceConfig(
        constant_rate_mbps=1.0,
        packet_size_bucket=512
    )
    engine = TrafficPaddingEngine(config)

    # Create some real packets
    real_packets = [b"x" * 100 for _ in range(10)]

    # Apply padding
    padded_packets, pattern = engine.apply_padding(real_packets, 1.0)

    # Should have more packets after padding
    assert len(padded_packets) > len(real_packets)
    assert pattern.padding_applied is True
    assert pattern.rate_mbps == 1.0


def test_packet_normalization():
    """Test packet size normalization"""
    config = AntiSurveillanceConfig(packet_size_bucket=512)
    normalizer = PacketNormalizer(config)

    # Test various packet sizes
    test_cases = [
        (b"x" * 100, 512),   # Should pad to 512
        (b"x" * 512, 512),   # Already 512
        (b"x" * 600, 1024),  # Should pad to 1024
    ]

    for packet, expected_size in test_cases:
        normalized = normalizer.normalize_packet(packet)
        assert len(normalized) == expected_size


def test_burst_detection():
    """Test burst detection"""
    config = AntiSurveillanceConfig()
    obfuscator = BurstObfuscator(config)

    # Create burst: 15 packets in 50ms
    packets = [b"x" * 100 for _ in range(15)]
    timestamps = [0.0 + i * 0.003 for i in range(15)]  # 3ms apart

    is_burst = obfuscator.detect_burst(packets, timestamps)
    assert is_burst is True


def test_burst_obfuscation():
    """Test burst obfuscation"""
    config = AntiSurveillanceConfig()
    obfuscator = BurstObfuscator(config)

    # Create burst
    packets = [b"x" * 100 for _ in range(15)]
    timestamps = [0.0 + i * 0.003 for i in range(15)]

    # Obfuscate
    obf_packets, obf_timestamps = obfuscator.obfuscate_burst(packets, timestamps)

    # Timestamps should be evenly spread
    original_span = timestamps[-1] - timestamps[0]
    obfuscated_span = obf_timestamps[-1] - obf_timestamps[0]

    # Obfuscated span should be approximately equal to original span
    # (packets are spread evenly over the same duration)
    assert abs(obfuscated_span - original_span) < 0.01


# ============================================================================
# TIMING ATTACK PREVENTION TESTS
# ============================================================================

def test_constant_time_execution():
    """Test constant-time operation execution"""
    config = AntiSurveillanceConfig(constant_time_operations=True)
    ct_ops = ConstantTimeOperations(config)

    # Define a fast operation
    def fast_operation():
        return 42

    # Execute with 100ms target
    result, profile = ct_ops.execute_constant_time(
        operation=fast_operation,
        target_time_ms=100.0,
        operation_name="test_op",
        component="test"
    )

    assert result == 42
    assert profile.constant_time_enforced is True
    assert profile.added_delay_ms > 0  # Should have added delay


def test_execution_time_normalization():
    """Test execution time normalization"""
    config = AntiSurveillanceConfig(execution_time_bucket_ms=100)
    normalizer = ExecutionTimeNormalizer(config)

    test_cases = [
        (50.0, 100.0),   # Should round up to 100
        (100.0, 100.0),  # Already 100
        (150.0, 200.0),  # Should round up to 200
    ]

    for execution_time, expected_normalized in test_cases:
        normalized = normalizer.normalize_execution_time(execution_time)
        assert normalized == expected_normalized


def test_normalization_delay_calculation():
    """Test normalization delay calculation"""
    config = AntiSurveillanceConfig(execution_time_bucket_ms=100)
    normalizer = ExecutionTimeNormalizer(config)

    # 50ms execution should need 50ms delay to reach 100ms
    delay = normalizer.add_normalization_delay(50.0)
    assert delay == 50.0

    # 100ms execution should need 0ms delay
    delay = normalizer.add_normalization_delay(100.0)
    assert delay == 0.0


def test_random_delay_generation():
    """Test random delay generation"""
    config = AntiSurveillanceConfig(random_delay_max_ms=50)
    injector = RandomDelayInjector(config)

    # Generate multiple delays and check they're in range
    delays = [injector.generate_random_delay() for _ in range(100)]

    assert all(0 <= d <= 50 for d in delays)
    assert len(set(delays)) > 1  # Should have variety


def test_random_delay_injection():
    """Test random delay injection"""
    config = AntiSurveillanceConfig(random_delay_max_ms=10)
    injector = RandomDelayInjector(config)

    start = time.time()
    injector.inject_delay(10.0)
    elapsed = (time.time() - start) * 1000

    # Should have delayed approximately 10ms
    assert 8 <= elapsed <= 15  # Allow some tolerance


# ============================================================================
# METADATA MINIMIZATION TESTS
# ============================================================================

def test_timestamp_scrubbing():
    """Test timestamp scrubbing"""
    config = AntiSurveillanceConfig(timestamp_precision_hours=1)
    scrubber = MetadataScrubber(config)

    # Test timestamp at 14:37:42
    timestamp = datetime(2024, 1, 15, 14, 37, 42)
    scrubbed = scrubber.scrub_timestamp(timestamp)

    # Should be rounded to 14:00:00
    assert scrubbed.hour == 14
    assert scrubbed.minute == 0
    assert scrubbed.second == 0


def test_ip_address_scrubbing():
    """Test IP address scrubbing"""
    config = AntiSurveillanceConfig(ip_anonymization=True)
    scrubber = MetadataScrubber(config)

    # Test IPv4
    ip = "192.168.1.100"
    scrubbed = scrubber.scrub_ip_address(ip)
    assert scrubbed == "192.168.1.0"

    # Test IPv6
    ipv6 = "2001:0db8:85a3:0000:0000:8a2e:0370:7334"
    scrubbed_v6 = scrubber.scrub_ip_address(ipv6)
    assert scrubbed_v6.endswith("::0")


def test_user_agent_scrubbing():
    """Test user agent scrubbing"""
    config = AntiSurveillanceConfig(user_agent_normalization=True)
    scrubber = MetadataScrubber(config)

    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"
    scrubbed = scrubber.scrub_user_agent(ua)

    assert scrubbed == "Mozilla/5.0 (Generic) Murphy/1.0"


def test_metadata_scrubbing():
    """Test complete metadata scrubbing"""
    config = AntiSurveillanceConfig()
    scrubber = MetadataScrubber(config)

    metadata = {
        'timestamp': datetime(2024, 1, 15, 14, 37, 42),
        'ip_address': '192.168.1.100',
        'user_agent': 'Mozilla/5.0 Chrome/120.0',
        'other_field': 'preserved'
    }

    scrubbed = scrubber.scrub_metadata(metadata)

    assert scrubbed['timestamp'].minute == 0
    assert scrubbed['ip_address'] == '192.168.1.0'
    assert scrubbed['user_agent'] == 'Mozilla/5.0 (Generic) Murphy/1.0'
    assert scrubbed['other_field'] == 'preserved'


# ============================================================================
# ANONYMIZATION TESTS
# ============================================================================

def test_k_anonymity_set_creation():
    """Test k-anonymity set creation"""
    config = AntiSurveillanceConfig(k_anonymity_k=5)
    engine = KAnonymityEngine(config)

    # Create set with enough members
    member_ids = [f"user_{i}" for i in range(10)]
    anon_set = engine.create_anonymity_set(member_ids)

    assert anon_set is not None
    assert anon_set.k_value == 5
    assert len(anon_set.member_ids) == 10


def test_k_anonymity_insufficient_members():
    """Test k-anonymity with insufficient members"""
    config = AntiSurveillanceConfig(k_anonymity_k=5)
    engine = KAnonymityEngine(config)

    # Try to create set with too few members
    member_ids = ["user_1", "user_2", "user_3"]
    anon_set = engine.create_anonymity_set(member_ids)

    assert anon_set is None  # Should fail


def test_k_anonymity_check():
    """Test k-anonymity checking"""
    config = AntiSurveillanceConfig(k_anonymity_k=5)
    engine = KAnonymityEngine(config)

    # Query result with 10 rows
    query_result = [{'id': i, 'value': i * 10} for i in range(10)]

    satisfies = engine.check_k_anonymity(query_result)
    assert satisfies is True

    # Query result with only 3 rows
    query_result_small = [{'id': i, 'value': i * 10} for i in range(3)]
    satisfies_small = engine.check_k_anonymity(query_result_small)
    assert satisfies_small is False


def test_differential_privacy_laplace_noise():
    """Test Laplace noise addition"""
    config = AntiSurveillanceConfig(differential_privacy_epsilon=1.0)
    engine = DifferentialPrivacyEngine(config)

    # Add noise to value
    original_value = 100.0
    sensitivity = 1.0

    noisy_values = [
        engine.add_laplace_noise(original_value, sensitivity)
        for _ in range(100)
    ]

    # Check that noise was added (values should vary)
    assert len(set(noisy_values)) > 1

    # Check that mean is approximately original value
    mean_noisy = sum(noisy_values) / len(noisy_values)
    assert abs(mean_noisy - original_value) < 10  # Within reasonable range


def test_differential_privacy_gaussian_noise():
    """Test Gaussian noise addition"""
    config = AntiSurveillanceConfig(differential_privacy_epsilon=1.0)
    engine = DifferentialPrivacyEngine(config)

    # Add noise to value
    original_value = 100.0
    sensitivity = 1.0

    noisy_values = [
        engine.add_gaussian_noise(original_value, sensitivity)
        for _ in range(100)
    ]

    # Check that noise was added
    assert len(set(noisy_values)) > 1

    # Check that mean is approximately original value
    mean_noisy = sum(noisy_values) / len(noisy_values)
    assert abs(mean_noisy - original_value) < 10


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

def test_anti_surveillance_system_initialization():
    """Test anti-surveillance system initialization"""
    system = AntiSurveillanceSystem()

    assert system.config is not None
    assert system.traffic_padding is not None
    assert system.packet_normalizer is not None
    assert system.metadata_scrubber is not None


def test_traffic_protection():
    """Test complete traffic protection"""
    system = AntiSurveillanceSystem()

    # Create test packets
    packets = [b"x" * 100 for _ in range(10)]

    # Protect traffic
    protected_packets, pattern = system.protect_traffic(packets, 1.0)

    assert len(protected_packets) >= len(packets)
    assert pattern.padding_applied is True
    assert system.total_packets_processed > 0


def test_timing_protection():
    """Test complete timing protection"""
    system = AntiSurveillanceSystem()

    def test_operation():
        time.sleep(0.01)  # 10ms operation
        return "result"

    # Protect timing
    result, profile = system.protect_timing(
        operation=test_operation,
        target_time_ms=100.0,
        operation_name="test",
        component="test"
    )

    assert result == "result"
    assert profile.constant_time_enforced is True
    assert system.total_operations_normalized > 0


def test_metadata_protection():
    """Test complete metadata protection"""
    system = AntiSurveillanceSystem()

    metadata = {
        'timestamp': datetime.now(),
        'ip_address': '192.168.1.100',
        'user_agent': 'Chrome/120.0'
    }

    # Protect metadata
    protected = system.protect_metadata(metadata)

    assert protected['ip_address'] == '192.168.1.0'
    assert system.total_metadata_scrubbed > 0


def test_statistics_collection():
    """Test statistics collection"""
    system = AntiSurveillanceSystem()

    # Perform some operations
    packets = [b"x" * 100 for _ in range(5)]
    system.protect_traffic(packets, 1.0)

    metadata = {'timestamp': datetime.now()}
    system.protect_metadata(metadata)

    # Get statistics
    stats = system.get_statistics()

    assert stats['total_packets_processed'] > 0
    assert stats['total_metadata_scrubbed'] > 0
    assert 'config' in stats


def test_disabled_features():
    """Test system with features disabled"""
    config = AntiSurveillanceConfig(
        enable_traffic_padding=False,
        enable_timing_normalization=False,
        enable_metadata_minimization=False
    )
    system = AntiSurveillanceSystem(config)

    # Traffic protection should not add padding
    packets = [b"x" * 100 for _ in range(10)]
    protected_packets, pattern = system.protect_traffic(packets, 1.0)

    # Should have same number of packets (no padding)
    assert len(protected_packets) == len(packets)


def test_performance_overhead():
    """Test that performance overhead is acceptable"""
    system = AntiSurveillanceSystem()

    # Measure overhead for traffic protection
    packets = [b"x" * 100 for _ in range(100)]

    start = time.time()
    protected_packets, _ = system.protect_traffic(packets, 1.0)
    elapsed = time.time() - start

    # Should complete in reasonable time (< 1 second)
    assert elapsed < 1.0


# ============================================================================
# SECURITY TESTS
# ============================================================================

def test_traffic_pattern_consistency():
    """Test that traffic patterns are consistent"""
    config = AntiSurveillanceConfig(constant_rate_mbps=1.0)
    engine = TrafficPaddingEngine(config)

    # Apply padding multiple times with same input
    packets = [b"x" * 100 for _ in range(10)]

    results = []
    for _ in range(5):
        padded, pattern = engine.apply_padding(packets, 1.0)
        results.append(pattern.rate_mbps)

    # All should target same rate
    assert all(r == 1.0 for r in results)


def test_timing_normalization_consistency():
    """Test that timing normalization is consistent"""
    config = AntiSurveillanceConfig(execution_time_bucket_ms=100)
    normalizer = ExecutionTimeNormalizer(config)

    # Normalize same time multiple times
    execution_time = 75.0

    results = [normalizer.normalize_execution_time(execution_time) for _ in range(10)]

    # All should normalize to same bucket
    assert all(r == 100.0 for r in results)


def test_metadata_scrubbing_consistency():
    """Test that metadata scrubbing is consistent"""
    config = AntiSurveillanceConfig()
    scrubber = MetadataScrubber(config)

    # Scrub same metadata multiple times
    metadata = {
        'timestamp': datetime(2024, 1, 15, 14, 37, 42),
        'ip_address': '192.168.1.100'
    }

    results = [scrubber.scrub_metadata(metadata) for _ in range(5)]

    # All should produce same result
    assert all(r['ip_address'] == '192.168.1.0' for r in results)
    assert all(r['timestamp'].minute == 0 for r in results)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
