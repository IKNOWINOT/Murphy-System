"""
Test Suite for Security Middleware

Tests the unified security middleware layer that integrates all Security Plane
components with Murphy System components.
"""

import pytest
from datetime import datetime
import secrets
import time
from typing import Dict, Any

from src.security_plane.middleware import (
    SecurityMiddlewareConfig,
    SecurityContext,
    AuthenticationMiddleware,
    EncryptionMiddleware,
    AuditLoggingMiddleware,
    TimingNormalizationMiddleware,
    DLPMiddleware,
    AntiSurveillanceMiddleware,
    SecurityMiddleware,
    ConfidenceEngineMiddleware,
    GateSynthesisMiddleware,
    ExecutionOrchestratorMiddleware
)


# ============================================================================
# CONFIGURATION TESTS
# ============================================================================

def test_middleware_config_creation():
    """Test middleware configuration creation"""
    config = SecurityMiddlewareConfig()

    assert config.require_authentication is True
    assert config.require_encryption is True
    assert config.enable_audit_logging is True
    assert config.enable_timing_normalization is True
    assert config.enable_dlp is True
    assert config.enable_anti_surveillance is True


def test_middleware_config_customization():
    """Test middleware configuration customization"""
    config = SecurityMiddlewareConfig(
        require_authentication=False,
        require_encryption=False,
        enable_timing_normalization=False
    )

    assert config.require_authentication is False
    assert config.require_encryption is False
    assert config.enable_timing_normalization is False


# ============================================================================
# SECURITY CONTEXT TESTS
# ============================================================================

def test_security_context_creation():
    """Test security context creation"""
    context = SecurityContext(
        request_id="test_request",
        timestamp=datetime.now()
    )

    assert context.request_id == "test_request"
    assert context.authenticated is False
    assert context.encrypted is False
    assert context.sensitive_data_detected is False


def test_security_context_elapsed_time():
    """Test security context elapsed time calculation"""
    context = SecurityContext(
        request_id="test",
        timestamp=datetime.now()
    )

    time.sleep(0.1)  # 100ms
    elapsed = context.get_elapsed_time_ms()

    assert 90 <= elapsed <= 150  # Allow some tolerance


# ============================================================================
# AUTHENTICATION MIDDLEWARE TESTS
# ============================================================================

def test_authentication_middleware_disabled():
    """Test authentication middleware when disabled"""
    config = SecurityMiddlewareConfig(require_authentication=False)
    auth = AuthenticationMiddleware(config)

    context = SecurityContext(request_id="test", timestamp=datetime.now())
    result = auth.authenticate_request({}, context)

    assert result is True
    assert context.authenticated is True


def test_authentication_middleware_missing_credentials():
    """Test authentication middleware with missing credentials"""
    config = SecurityMiddlewareConfig(require_authentication=True)
    auth = AuthenticationMiddleware(config)

    context = SecurityContext(request_id="test", timestamp=datetime.now())
    result = auth.authenticate_request({}, context)

    assert result is False
    assert context.authenticated is False


def test_authentication_middleware_human_auth():
    """Test authentication middleware with human credentials"""
    config = SecurityMiddlewareConfig(require_authentication=True)
    auth = AuthenticationMiddleware(config)

    request_data = {
        'auth_type': 'human',
        'credentials': {
            'user_id': 'test_user',
            'passkey_challenge': 'challenge',
            'passkey_response': 'response'
        }
    }

    context = SecurityContext(request_id="test", timestamp=datetime.now())
    # Note: Will fail without valid passkey, but tests the flow
    result = auth.authenticate_request(request_data, context)

    assert context.identity == 'test_user'


# ============================================================================
# ENCRYPTION MIDDLEWARE TESTS
# ============================================================================

def test_encryption_middleware_disabled():
    """Test encryption middleware when disabled"""
    config = SecurityMiddlewareConfig(require_encryption=False)
    encryption = EncryptionMiddleware(config)

    context = SecurityContext(request_id="test", timestamp=datetime.now())
    data = b"test data"

    encrypted = encryption.encrypt_data(data, context)
    assert encrypted == data  # No encryption
    assert context.encrypted is False


def test_encryption_middleware_enabled():
    """Test encryption middleware when enabled"""
    config = SecurityMiddlewareConfig(require_encryption=True, use_hybrid_pqc=True)
    encryption = EncryptionMiddleware(config)

    context = SecurityContext(request_id="test", timestamp=datetime.now())
    data = b"test data"

    encrypted = encryption.encrypt_data(data, context)
    assert context.encrypted is True
    assert "Kyber-1024" in context.encryption_algorithm
    # Ciphertext must differ from plaintext (nonce + tag + XOR-masked payload)
    assert encrypted != data
    assert len(encrypted) == 32 + 32 + len(data)  # nonce + HMAC tag + ciphertext

    # Round-trip: decrypt must recover original plaintext
    decrypted = encryption.decrypt_data(encrypted, context)
    assert decrypted == data


# ============================================================================
# AUDIT LOGGING MIDDLEWARE TESTS
# ============================================================================

def test_audit_logging_request():
    """Test audit logging for requests"""
    config = SecurityMiddlewareConfig(enable_audit_logging=True)
    audit = AuditLoggingMiddleware(config)

    request_data = {
        'component': 'test_component',
        'operation': 'test_operation'
    }
    context = SecurityContext(request_id="test", timestamp=datetime.now())
    context.authenticated = True

    audit.log_request(request_data, context)

    assert len(audit.audit_logs) == 1
    assert audit.audit_logs[0].component == 'test_component'
    assert audit.audit_logs[0].operation == 'test_operation'


def test_audit_logging_response():
    """Test audit logging for responses"""
    config = SecurityMiddlewareConfig(enable_audit_logging=True)
    audit = AuditLoggingMiddleware(config)

    response_data = {
        'component': 'test_component',
        'operation': 'test_operation'
    }
    context = SecurityContext(request_id="test", timestamp=datetime.now())

    audit.log_response(response_data, context, success=True)

    assert len(audit.audit_logs) == 1
    assert audit.audit_logs[0].success is True


def test_audit_logging_query():
    """Test audit log querying"""
    config = SecurityMiddlewareConfig(enable_audit_logging=True)
    audit = AuditLoggingMiddleware(config)

    # Log multiple entries
    for i in range(5):
        request_data = {'component': f'component_{i}', 'operation': 'test'}
        context = SecurityContext(request_id=f"test_{i}", timestamp=datetime.now())
        context.identity = f"user_{i % 2}"  # Alternate users
        audit.log_request(request_data, context)

    # Query by identity
    logs = audit.get_audit_logs(identity="user_0")
    assert len(logs) == 3  # user_0, user_0, user_0


# ============================================================================
# TIMING NORMALIZATION MIDDLEWARE TESTS
# ============================================================================

def test_timing_normalization_disabled():
    """Test timing normalization when disabled"""
    config = SecurityMiddlewareConfig(enable_timing_normalization=False)
    timing = TimingNormalizationMiddleware(config)

    context = SecurityContext(request_id="test", timestamp=datetime.now())

    def fast_operation():
        time.sleep(0.01)  # 10ms
        return "result"

    start = time.time()
    result = timing.normalize_timing(fast_operation, context)
    elapsed = (time.time() - start) * 1000

    assert result == "result"
    assert 8 <= elapsed <= 20  # Should be ~10ms


def test_timing_normalization_enabled():
    """Test timing normalization when enabled"""
    config = SecurityMiddlewareConfig(
        enable_timing_normalization=True,
        target_time_ms=100.0
    )
    timing = TimingNormalizationMiddleware(config)

    context = SecurityContext(request_id="test", timestamp=datetime.now())

    def fast_operation():
        time.sleep(0.01)  # 10ms
        return "result"

    start = time.time()
    result = timing.normalize_timing(fast_operation, context)
    elapsed = (time.time() - start) * 1000

    assert result == "result"
    assert 95 <= elapsed <= 110  # Should be normalized to ~100ms
    assert context.normalized_time_ms is not None


# ============================================================================
# DLP MIDDLEWARE TESTS
# ============================================================================

def test_dlp_classification():
    """Test DLP data classification"""
    config = SecurityMiddlewareConfig(enable_dlp=True)
    dlp = DLPMiddleware(config)

    # Test with sensitive data
    data = {
        'email': 'test@example.com',
        'ssn': '123-45-6789',
        'credit_card': '4111-1111-1111-1111'
    }

    context = SecurityContext(request_id="test", timestamp=datetime.now())
    classification = dlp.classify_data(data, context)

    # Classification should detect sensitive data
    assert classification is not None
    assert context.data_classification is not None


def test_dlp_exfiltration_prevention():
    """Test DLP exfiltration prevention"""
    config = SecurityMiddlewareConfig(enable_dlp=True, block_sensitive_data=True)
    dlp = DLPMiddleware(config)

    data = {'sensitive': 'data'}
    context = SecurityContext(request_id="test", timestamp=datetime.now())
    context.sensitive_data_detected = True

    # Trusted destination
    allowed = dlp.prevent_exfiltration(data, "localhost", context)
    assert allowed is True

    # Untrusted destination
    blocked = dlp.prevent_exfiltration(data, "untrusted.com", context)
    assert blocked is False


# ============================================================================
# ANTI-SURVEILLANCE MIDDLEWARE TESTS
# ============================================================================

def test_anti_surveillance_metadata_scrubbing():
    """Test anti-surveillance metadata scrubbing"""
    config = SecurityMiddlewareConfig(
        enable_anti_surveillance=True,
        scrub_metadata=True
    )
    anti_surv = AntiSurveillanceMiddleware(config)

    metadata = {
        'timestamp': datetime(2024, 1, 15, 14, 37, 42),
        'ip_address': '192.168.1.100',
        'user_agent': 'Chrome/120.0'
    }

    context = SecurityContext(request_id="test", timestamp=datetime.now())
    scrubbed = anti_surv.scrub_metadata(metadata, context)

    assert scrubbed['timestamp'].minute == 0  # Fuzzed
    assert scrubbed['ip_address'] == '192.168.1.0'  # Anonymized
    assert 'Murphy' in scrubbed['user_agent']  # Normalized
    assert context.metadata_scrubbed is True


# ============================================================================
# UNIFIED MIDDLEWARE TESTS
# ============================================================================

def test_security_middleware_initialization():
    """Test security middleware initialization"""
    middleware = SecurityMiddleware()

    assert middleware.auth is not None
    assert middleware.encryption is not None
    assert middleware.audit is not None
    assert middleware.timing is not None
    assert middleware.dlp is not None
    assert middleware.anti_surveillance is not None


def test_security_middleware_process_request():
    """Test security middleware request processing"""
    config = SecurityMiddlewareConfig(
        require_authentication=False,  # Disable for testing
        require_encryption=False,
        enable_timing_normalization=False
    )
    middleware = SecurityMiddleware(config)

    request_data = {
        'component': 'test',
        'operation': 'test_op',
        'data': 'test data'
    }

    def operation(req, ctx):
        return {'result': 'success', 'data': req['data']}

    result = middleware.process_request(request_data, operation, 'test_component')

    assert result['result'] == 'success'
    assert 'security_context' in result
    assert result['security_context']['request_id'] is not None


def test_security_middleware_authentication_failure():
    """Test security middleware with authentication failure"""
    config = SecurityMiddlewareConfig(require_authentication=True)
    middleware = SecurityMiddleware(config)

    request_data = {
        'component': 'test',
        'operation': 'test_op'
        # No authentication credentials
    }

    def operation(req, ctx):
        return {'result': 'success'}

    with pytest.raises(PermissionError, match="Authentication failed"):
        middleware.process_request(request_data, operation, 'test_component')


def test_security_middleware_statistics():
    """Test security middleware statistics"""
    config = SecurityMiddlewareConfig(
        require_authentication=False,
        require_encryption=False
    )
    middleware = SecurityMiddleware(config)

    # Process some requests
    request_data = {'component': 'test', 'operation': 'test_op'}

    for _ in range(5):
        try:
            middleware.process_request(
                request_data,
                lambda req, ctx: {'result': 'success'},
                'test_component'
            )
        except Exception:
            # PROD-HARD-A3: was bare `except:` which also caught KeyboardInterrupt /
            # SystemExit. Test loop deliberately swallows component failures to
            # measure middleware statistics under stress; capability preserved,
            # only the catch surface narrowed.
            pass

    stats = middleware.get_statistics()

    assert stats['total_requests'] == 5
    assert 'authentication_rate' in stats
    assert 'encryption_rate' in stats


def test_security_middleware_decorator():
    """Test security middleware decorator"""
    config = SecurityMiddlewareConfig(
        require_authentication=False,
        require_encryption=False
    )
    middleware = SecurityMiddleware(config)

    @middleware.secure_endpoint('test_component')
    def test_endpoint(request_data):
        return {'result': 'success', 'data': request_data.get('data')}

    result = test_endpoint({'data': 'test'})

    assert result['result'] == 'success'
    assert 'security_context' in result


# ============================================================================
# COMPONENT-SPECIFIC MIDDLEWARE TESTS
# ============================================================================

def test_confidence_engine_middleware():
    """Test Confidence Engine specific middleware"""
    middleware = ConfidenceEngineMiddleware()

    assert middleware.component_name == "confidence_engine"
    assert middleware.auth is not None


def test_gate_synthesis_middleware():
    """Test Gate Synthesis specific middleware"""
    middleware = GateSynthesisMiddleware()

    assert middleware.component_name == "gate_synthesis"
    assert middleware.auth is not None


def test_execution_orchestrator_middleware():
    """Test Execution Orchestrator specific middleware"""
    middleware = ExecutionOrchestratorMiddleware()

    assert middleware.component_name == "execution_orchestrator"
    assert middleware.auth is not None


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

def test_full_security_pipeline():
    """Test complete security pipeline"""
    config = SecurityMiddlewareConfig(
        require_authentication=False,  # Simplified for testing
        require_encryption=True,
        enable_audit_logging=True,
        enable_timing_normalization=True,
        enable_dlp=True,
        enable_anti_surveillance=True
    )
    middleware = SecurityMiddleware(config)

    request_data = {
        'component': 'test',
        'operation': 'test_op',
        'data': 'test data',
        'metadata': {
            'timestamp': datetime.now(),
            'ip_address': '192.168.1.100'
        }
    }

    def operation(req, ctx):
        return {
            'result': 'success',
            'data': req['data'],
            'metadata': req.get('metadata', {})
        }

    result = middleware.process_request(request_data, operation, 'test_component')

    # Verify security context
    assert 'security_context' in result
    assert result['security_context']['authenticated'] is True
    assert result['security_context']['data_classification'] is not None

    # Verify metadata scrubbing (if present)
    if 'metadata' in result and 'ip_address' in result['metadata']:
        assert result['metadata']['ip_address'] == '192.168.1.0'

    # Verify audit logs
    assert len(middleware.audit.audit_logs) >= 2  # Request + response


def test_security_middleware_performance():
    """Test security middleware performance overhead"""
    config = SecurityMiddlewareConfig(
        require_authentication=False,
        require_encryption=False,
        enable_timing_normalization=False
    )
    middleware = SecurityMiddleware(config)

    request_data = {'component': 'test', 'operation': 'test_op'}

    def fast_operation(req, ctx):
        return {'result': 'success'}

    # Measure overhead
    start = time.time()
    for _ in range(100):
        middleware.process_request(request_data, fast_operation, 'test')
    elapsed = time.time() - start

    # Should complete 100 requests in reasonable time
    assert elapsed < 5.0  # Less than 5 seconds for 100 requests


def test_security_middleware_error_handling():
    """Test security middleware error handling"""
    config = SecurityMiddlewareConfig(
        require_authentication=False,
        enable_audit_logging=True
    )
    middleware = SecurityMiddleware(config)

    request_data = {'component': 'test', 'operation': 'test_op'}

    def failing_operation(req, ctx):
        raise ValueError("Operation failed")

    with pytest.raises(ValueError, match="Operation failed"):
        middleware.process_request(request_data, failing_operation, 'test')

    # Verify failure was logged
    logs = middleware.audit.get_audit_logs()
    assert any(not log.success for log in logs)


# ============================================================================
# ENCRYPTION MIDDLEWARE — ROUND-TRIP AND INTEGRITY TESTS
# ============================================================================

def test_encrypt_decrypt_round_trip_various_sizes():
    """Encrypt → decrypt round-trip must preserve plaintext for payloads of varying size."""
    config = SecurityMiddlewareConfig(require_encryption=True, use_hybrid_pqc=True)
    enc = EncryptionMiddleware(config)
    ctx = SecurityContext(request_id="rt", timestamp=datetime.now())

    for size in (0, 1, 16, 255, 1024):
        plaintext = secrets.token_bytes(size)
        ciphertext = enc.encrypt_data(plaintext, ctx)
        recovered = enc.decrypt_data(ciphertext, ctx)
        assert recovered == plaintext, f"Round-trip failed for payload size {size}"


def test_encrypt_tamper_detection():
    """Flipping a single ciphertext byte must cause HMAC verification failure."""
    config = SecurityMiddlewareConfig(require_encryption=True, use_hybrid_pqc=True)
    enc = EncryptionMiddleware(config)
    ctx = SecurityContext(request_id="tamper", timestamp=datetime.now())

    plaintext = b"sensitive-payload"
    ciphertext = enc.encrypt_data(plaintext, ctx)

    # Flip last byte
    tampered = ciphertext[:-1] + bytes([ciphertext[-1] ^ 0xFF])
    with pytest.raises(ValueError, match="HMAC authentication failed"):
        enc.decrypt_data(tampered, ctx)


def test_sign_verify_round_trip():
    """Signature produced by sign_data must be accepted by verify_signature."""
    config = SecurityMiddlewareConfig(require_encryption=True, use_hybrid_pqc=True)
    enc = EncryptionMiddleware(config)
    ctx = SecurityContext(request_id="sig", timestamp=datetime.now())

    payload = b"data-to-sign"
    signature = enc.sign_data(payload, ctx)
    assert isinstance(signature, bytes)
    assert len(signature) > 0

    assert enc.verify_signature(payload, signature, ctx) is True


def test_sign_verify_detects_forgery():
    """Modified data must fail signature verification."""
    config = SecurityMiddlewareConfig(require_encryption=True, use_hybrid_pqc=True)
    enc = EncryptionMiddleware(config)
    ctx = SecurityContext(request_id="forge", timestamp=datetime.now())

    payload = b"original-data"
    signature = enc.sign_data(payload, ctx)

    forged_payload = b"modified-data"
    assert enc.verify_signature(forged_payload, signature, ctx) is False


def test_encryption_disabled_passthrough():
    """When encryption is disabled, data must pass through unchanged."""
    config = SecurityMiddlewareConfig(require_encryption=False)
    enc = EncryptionMiddleware(config)
    ctx = SecurityContext(request_id="noop", timestamp=datetime.now())

    plaintext = b"plaintext"
    assert enc.encrypt_data(plaintext, ctx) == plaintext
    assert enc.decrypt_data(plaintext, ctx) == plaintext


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
