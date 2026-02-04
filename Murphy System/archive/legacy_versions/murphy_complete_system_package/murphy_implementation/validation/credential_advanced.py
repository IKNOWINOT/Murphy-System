"""
Advanced Credential Verification Features
API key validation, OAuth verification, expiry tracking, and refresh mechanisms.
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
from pydantic import BaseModel, Field
import re
import hashlib
import base64
import json

from murphy_implementation.validation.credential_verifier import (
    Credential, CredentialType, CredentialStatus
)


# ============================================================================
# TASK 3.2: API KEY VALIDATION
# ============================================================================

class APIKeyFormat(str, Enum):
    """Common API key formats."""
    ALPHANUMERIC = "alphanumeric"
    BASE64 = "base64"
    HEX = "hex"
    UUID = "uuid"
    CUSTOM = "custom"


class APIKeyValidationRule(BaseModel):
    """Validation rule for API keys."""
    name: str
    pattern: str  # Regex pattern
    min_length: int = 20
    max_length: int = 100
    format_type: APIKeyFormat = APIKeyFormat.ALPHANUMERIC
    prefix: Optional[str] = None
    checksum_required: bool = False


class APIKeyValidator:
    """
    Validates API keys using format rules and checksums.
    """
    
    # Common API key patterns
    PATTERNS = {
        "github": r"^gh[ps]_[a-zA-Z0-9]{36,}$",
        "stripe": r"^(sk|pk)_(test|live)_[a-zA-Z0-9]{24,}$",
        "openai": r"^sk-[a-zA-Z0-9]{48}$",
        "aws": r"^AKIA[0-9A-Z]{16}$",
        "google": r"^AIza[0-9A-Za-z\-_]{35}$",
        "sendgrid": r"^SG\.[a-zA-Z0-9_-]{22}\.[a-zA-Z0-9_-]{43}$"
    }
    
    def __init__(self):
        self.custom_rules: Dict[str, APIKeyValidationRule] = {}
    
    def register_rule(self, service_name: str, rule: APIKeyValidationRule):
        """Register a custom validation rule."""
        self.custom_rules[service_name] = rule
    
    def validate_format(
        self,
        api_key: str,
        service_name: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Validate API key format.
        
        Args:
            api_key: API key to validate
            service_name: Optional service name for specific validation
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not api_key:
            return False, "API key is empty"
        
        # Check length
        if len(api_key) < 10:
            return False, "API key too short (minimum 10 characters)"
        
        if len(api_key) > 200:
            return False, "API key too long (maximum 200 characters)"
        
        # Service-specific validation
        if service_name:
            # Check custom rules first
            if service_name in self.custom_rules:
                rule = self.custom_rules[service_name]
                return self._validate_with_rule(api_key, rule)
            
            # Check built-in patterns
            if service_name.lower() in self.PATTERNS:
                pattern = self.PATTERNS[service_name.lower()]
                if re.match(pattern, api_key):
                    return True, ""
                else:
                    return False, f"Does not match {service_name} API key format"
        
        # Generic validation
        return self._validate_generic(api_key)
    
    def _validate_with_rule(
        self,
        api_key: str,
        rule: APIKeyValidationRule
    ) -> Tuple[bool, str]:
        """Validate using a specific rule."""
        # Check length
        if len(api_key) < rule.min_length:
            return False, f"Too short (minimum {rule.min_length} characters)"
        
        if len(api_key) > rule.max_length:
            return False, f"Too long (maximum {rule.max_length} characters)"
        
        # Check prefix
        if rule.prefix and not api_key.startswith(rule.prefix):
            return False, f"Must start with '{rule.prefix}'"
        
        # Check pattern
        if not re.match(rule.pattern, api_key):
            return False, f"Does not match required pattern"
        
        # Check format type
        if rule.format_type == APIKeyFormat.BASE64:
            if not self._is_valid_base64(api_key):
                return False, "Invalid Base64 format"
        
        elif rule.format_type == APIKeyFormat.HEX:
            if not self._is_valid_hex(api_key):
                return False, "Invalid hexadecimal format"
        
        elif rule.format_type == APIKeyFormat.UUID:
            if not self._is_valid_uuid(api_key):
                return False, "Invalid UUID format"
        
        # Check checksum if required
        if rule.checksum_required:
            if not self._verify_checksum(api_key):
                return False, "Invalid checksum"
        
        return True, ""
    
    def _validate_generic(self, api_key: str) -> Tuple[bool, str]:
        """Generic API key validation."""
        # Check for common issues
        if api_key.isspace():
            return False, "Contains only whitespace"
        
        if ' ' in api_key:
            return False, "Contains spaces"
        
        # Check character set
        if not re.match(r'^[a-zA-Z0-9_\-\.]+$', api_key):
            return False, "Contains invalid characters"
        
        return True, ""
    
    def _is_valid_base64(self, value: str) -> bool:
        """Check if string is valid Base64."""
        try:
            base64.b64decode(value, validate=True)
            return True
        except:
            return False
    
    def _is_valid_hex(self, value: str) -> bool:
        """Check if string is valid hexadecimal."""
        try:
            int(value, 16)
            return True
        except:
            return False
    
    def _is_valid_uuid(self, value: str) -> bool:
        """Check if string is valid UUID."""
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        return bool(re.match(uuid_pattern, value.lower()))
    
    def _verify_checksum(self, api_key: str) -> bool:
        """Verify API key checksum (if present)."""
        # Placeholder - implement actual checksum verification
        # This would depend on the specific checksum algorithm used
        return True
    
    def generate_api_key(
        self,
        length: int = 32,
        prefix: Optional[str] = None,
        format_type: APIKeyFormat = APIKeyFormat.ALPHANUMERIC
    ) -> str:
        """
        Generate a secure API key.
        
        Args:
            length: Length of the key
            prefix: Optional prefix
            format_type: Format type for the key
            
        Returns:
            Generated API key
        """
        import secrets
        
        if format_type == APIKeyFormat.BASE64:
            key = base64.b64encode(secrets.token_bytes(length)).decode()[:length]
        elif format_type == APIKeyFormat.HEX:
            key = secrets.token_hex(length // 2)
        elif format_type == APIKeyFormat.UUID:
            import uuid
            key = str(uuid.uuid4())
        else:  # ALPHANUMERIC
            alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            key = ''.join(secrets.choice(alphabet) for _ in range(length))
        
        if prefix:
            key = f"{prefix}{key}"
        
        return key


# ============================================================================
# TASK 3.3: OAUTH TOKEN VERIFICATION
# ============================================================================

class OAuthTokenType(str, Enum):
    """Types of OAuth tokens."""
    ACCESS_TOKEN = "access_token"
    REFRESH_TOKEN = "refresh_token"
    ID_TOKEN = "id_token"
    BEARER_TOKEN = "bearer_token"


class OAuthTokenInfo(BaseModel):
    """Information about an OAuth token."""
    token_type: OAuthTokenType
    expires_at: Optional[datetime] = None
    scopes: List[str] = Field(default_factory=list)
    issuer: Optional[str] = None
    subject: Optional[str] = None
    audience: Optional[str] = None
    is_valid: bool = True
    error: Optional[str] = None


class OAuthTokenVerifier:
    """
    Verifies OAuth tokens (JWT and opaque tokens).
    """
    
    def verify_jwt_token(self, token: str) -> OAuthTokenInfo:
        """
        Verify JWT token structure and claims.
        
        Args:
            token: JWT token string
            
        Returns:
            OAuthTokenInfo with verification results
        """
        try:
            # Split JWT into parts
            parts = token.split('.')
            if len(parts) != 3:
                return OAuthTokenInfo(
                    token_type=OAuthTokenType.ACCESS_TOKEN,
                    is_valid=False,
                    error="Invalid JWT format (must have 3 parts)"
                )
            
            # Decode payload (without verification for now)
            payload = self._decode_jwt_payload(parts[1])
            
            if not payload:
                return OAuthTokenInfo(
                    token_type=OAuthTokenType.ACCESS_TOKEN,
                    is_valid=False,
                    error="Failed to decode JWT payload"
                )
            
            # Extract claims
            expires_at = None
            if 'exp' in payload:
                expires_at = datetime.fromtimestamp(payload['exp'])
            
            scopes = []
            if 'scope' in payload:
                scopes = payload['scope'].split() if isinstance(payload['scope'], str) else payload['scope']
            
            # Check expiration
            is_valid = True
            error = None
            if expires_at and datetime.utcnow() > expires_at:
                is_valid = False
                error = "Token expired"
            
            return OAuthTokenInfo(
                token_type=OAuthTokenType.ACCESS_TOKEN,
                expires_at=expires_at,
                scopes=scopes,
                issuer=payload.get('iss'),
                subject=payload.get('sub'),
                audience=payload.get('aud'),
                is_valid=is_valid,
                error=error
            )
        
        except Exception as e:
            return OAuthTokenInfo(
                token_type=OAuthTokenType.ACCESS_TOKEN,
                is_valid=False,
                error=f"Verification error: {str(e)}"
            )
    
    def verify_opaque_token(
        self,
        token: str,
        introspection_endpoint: Optional[str] = None
    ) -> OAuthTokenInfo:
        """
        Verify opaque OAuth token.
        
        Args:
            token: Opaque token string
            introspection_endpoint: Optional introspection endpoint URL
            
        Returns:
            OAuthTokenInfo with verification results
        """
        # For opaque tokens, we need to call the introspection endpoint
        # This is a placeholder implementation
        
        if not introspection_endpoint:
            # Basic validation without introspection
            if len(token) < 20:
                return OAuthTokenInfo(
                    token_type=OAuthTokenType.BEARER_TOKEN,
                    is_valid=False,
                    error="Token too short"
                )
            
            return OAuthTokenInfo(
                token_type=OAuthTokenType.BEARER_TOKEN,
                is_valid=True
            )
        
        # Would make HTTP request to introspection endpoint
        # Placeholder for actual implementation
        return OAuthTokenInfo(
            token_type=OAuthTokenType.BEARER_TOKEN,
            is_valid=True
        )
    
    def _decode_jwt_payload(self, payload_part: str) -> Optional[Dict[str, Any]]:
        """Decode JWT payload from Base64."""
        try:
            # Add padding if needed
            padding = 4 - len(payload_part) % 4
            if padding != 4:
                payload_part += '=' * padding
            
            decoded = base64.urlsafe_b64decode(payload_part)
            return json.loads(decoded)
        except:
            return None
    
    def extract_scopes(self, token: str) -> List[str]:
        """Extract scopes from token."""
        token_info = self.verify_jwt_token(token)
        return token_info.scopes


# ============================================================================
# TASK 3.4: CREDENTIAL EXPIRY TRACKING
# ============================================================================

class ExpiryAlert(BaseModel):
    """Alert for expiring credential."""
    credential_id: str
    credential_name: str
    expires_at: datetime
    days_until_expiry: int
    alert_level: str  # "warning", "urgent", "critical"
    message: str


class CredentialExpiryTracker:
    """
    Tracks credential expiration and sends alerts.
    """
    
    def __init__(self):
        self.tracked_credentials: Dict[str, Credential] = {}
        self.alert_thresholds = {
            "warning": 30,  # 30 days
            "urgent": 7,    # 7 days
            "critical": 1   # 1 day
        }
        self.alerts: List[ExpiryAlert] = []
    
    def track_credential(self, credential: Credential):
        """Add credential to expiry tracking."""
        if credential.expires_at:
            self.tracked_credentials[credential.id] = credential
    
    def untrack_credential(self, credential_id: str):
        """Remove credential from tracking."""
        if credential_id in self.tracked_credentials:
            del self.tracked_credentials[credential_id]
    
    def check_expiring_credentials(self) -> List[ExpiryAlert]:
        """
        Check for expiring credentials and generate alerts.
        
        Returns:
            List of expiry alerts
        """
        alerts = []
        now = datetime.utcnow()
        
        for credential in self.tracked_credentials.values():
            if not credential.expires_at:
                continue
            
            days_until_expiry = (credential.expires_at - now).days
            
            # Determine alert level
            alert_level = None
            if days_until_expiry <= self.alert_thresholds["critical"]:
                alert_level = "critical"
            elif days_until_expiry <= self.alert_thresholds["urgent"]:
                alert_level = "urgent"
            elif days_until_expiry <= self.alert_thresholds["warning"]:
                alert_level = "warning"
            
            if alert_level:
                message = self._generate_alert_message(
                    credential,
                    days_until_expiry,
                    alert_level
                )
                
                alert = ExpiryAlert(
                    credential_id=credential.id,
                    credential_name=f"{credential.service_name}_{credential.credential_type}",
                    expires_at=credential.expires_at,
                    days_until_expiry=days_until_expiry,
                    alert_level=alert_level,
                    message=message
                )
                
                alerts.append(alert)
        
        self.alerts = alerts
        return alerts
    
    def get_expiring_soon(self, days: int = 30) -> List[Credential]:
        """Get credentials expiring within specified days."""
        cutoff = datetime.utcnow() + timedelta(days=days)
        
        return [
            cred for cred in self.tracked_credentials.values()
            if cred.expires_at and cred.expires_at <= cutoff
        ]
    
    def get_expired(self) -> List[Credential]:
        """Get expired credentials."""
        return [
            cred for cred in self.tracked_credentials.values()
            if cred.is_expired()
        ]
    
    def set_alert_threshold(self, level: str, days: int):
        """Set custom alert threshold."""
        if level in self.alert_thresholds:
            self.alert_thresholds[level] = days
    
    def _generate_alert_message(
        self,
        credential: Credential,
        days_until_expiry: int,
        alert_level: str
    ) -> str:
        """Generate alert message."""
        if days_until_expiry <= 0:
            return f"EXPIRED: {credential.service_name} credential has expired"
        elif days_until_expiry == 1:
            return f"{alert_level.upper()}: {credential.service_name} credential expires tomorrow"
        else:
            return f"{alert_level.upper()}: {credential.service_name} credential expires in {days_until_expiry} days"


# ============================================================================
# TASK 3.5: CREDENTIAL REFRESH MECHANISMS
# ============================================================================

class RefreshStrategy(str, Enum):
    """Strategies for refreshing credentials."""
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    ON_DEMAND = "on_demand"
    SCHEDULED = "scheduled"


class RefreshResult(BaseModel):
    """Result of credential refresh operation."""
    credential_id: str
    success: bool
    new_expires_at: Optional[datetime] = None
    error: Optional[str] = None
    refreshed_at: datetime = Field(default_factory=datetime.utcnow)


class CredentialRefreshHandler:
    """
    Base class for credential refresh handlers.
    """
    
    async def refresh(self, credential: Credential) -> str:
        """
        Refresh a credential.
        
        Args:
            credential: Credential to refresh
            
        Returns:
            New credential value
        """
        raise NotImplementedError


class OAuthRefreshHandler(CredentialRefreshHandler):
    """Handler for refreshing OAuth tokens."""
    
    def __init__(self, token_endpoint: str, client_id: str, client_secret: str):
        self.token_endpoint = token_endpoint
        self.client_id = client_id
        self.client_secret = client_secret
    
    async def refresh(self, credential: Credential) -> str:
        """Refresh OAuth token using refresh token."""
        # Placeholder - would make actual HTTP request
        # POST to token_endpoint with refresh_token grant
        
        # Simulated new token
        return f"refreshed_{credential.credential_value[:20]}"


class APIKeyRotationHandler(CredentialRefreshHandler):
    """Handler for rotating API keys."""
    
    def __init__(self, rotation_endpoint: str):
        self.rotation_endpoint = rotation_endpoint
    
    async def refresh(self, credential: Credential) -> str:
        """Rotate API key."""
        # Placeholder - would call rotation API
        
        # Generate new key
        validator = APIKeyValidator()
        return validator.generate_api_key(length=32)


class CredentialRefreshManager:
    """
    Manages automatic credential refresh.
    """
    
    def __init__(self, expiry_tracker: CredentialExpiryTracker):
        self.expiry_tracker = expiry_tracker
        self.refresh_handlers: Dict[str, CredentialRefreshHandler] = {}
        self.refresh_strategy: RefreshStrategy = RefreshStrategy.AUTOMATIC
        self.refresh_threshold_days = 7
        self.refresh_history: List[RefreshResult] = []
    
    def register_handler(
        self,
        credential_type: CredentialType,
        handler: CredentialRefreshHandler
    ):
        """Register a refresh handler for a credential type."""
        self.refresh_handlers[credential_type] = handler
    
    async def auto_refresh_expiring(self) -> List[RefreshResult]:
        """
        Automatically refresh credentials expiring soon.
        
        Returns:
            List of refresh results
        """
        if self.refresh_strategy != RefreshStrategy.AUTOMATIC:
            return []
        
        expiring = self.expiry_tracker.get_expiring_soon(self.refresh_threshold_days)
        results = []
        
        for credential in expiring:
            result = await self.refresh_credential(credential)
            results.append(result)
        
        return results
    
    async def refresh_credential(self, credential: Credential) -> RefreshResult:
        """
        Refresh a specific credential.
        
        Args:
            credential: Credential to refresh
            
        Returns:
            RefreshResult with operation status
        """
        handler = self.refresh_handlers.get(credential.credential_type)
        
        if not handler:
            return RefreshResult(
                credential_id=credential.id,
                success=False,
                error=f"No refresh handler for {credential.credential_type}"
            )
        
        try:
            new_value = await handler.refresh(credential)
            
            # Update credential
            credential.credential_value = new_value
            credential.expires_at = datetime.utcnow() + timedelta(days=90)  # Default 90 days
            credential.status = CredentialStatus.ACTIVE
            
            result = RefreshResult(
                credential_id=credential.id,
                success=True,
                new_expires_at=credential.expires_at
            )
            
            self.refresh_history.append(result)
            return result
        
        except Exception as e:
            result = RefreshResult(
                credential_id=credential.id,
                success=False,
                error=str(e)
            )
            
            self.refresh_history.append(result)
            return result
    
    def get_refresh_history(
        self,
        credential_id: Optional[str] = None,
        limit: int = 100
    ) -> List[RefreshResult]:
        """Get refresh history."""
        history = self.refresh_history
        
        if credential_id:
            history = [h for h in history if h.credential_id == credential_id]
        
        return history[-limit:]


# ============================================================================
# UNIFIED ADVANCED CREDENTIAL SYSTEM
# ============================================================================

class AdvancedCredentialSystem:
    """
    Complete advanced credential management system.
    Combines all advanced features.
    """
    
    def __init__(self):
        self.api_key_validator = APIKeyValidator()
        self.oauth_verifier = OAuthTokenVerifier()
        self.expiry_tracker = CredentialExpiryTracker()
        self.refresh_manager = CredentialRefreshManager(self.expiry_tracker)
    
    # API Key Validation
    def validate_api_key(
        self,
        api_key: str,
        service_name: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Validate API key format."""
        return self.api_key_validator.validate_format(api_key, service_name)
    
    def generate_api_key(self, **kwargs) -> str:
        """Generate secure API key."""
        return self.api_key_validator.generate_api_key(**kwargs)
    
    # OAuth Verification
    def verify_oauth_token(self, token: str) -> OAuthTokenInfo:
        """Verify OAuth token."""
        return self.oauth_verifier.verify_jwt_token(token)
    
    # Expiry Tracking
    def track_credential(self, credential: Credential):
        """Track credential expiry."""
        self.expiry_tracker.track_credential(credential)
    
    def check_expiring_credentials(self) -> List[ExpiryAlert]:
        """Check for expiring credentials."""
        return self.expiry_tracker.check_expiring_credentials()
    
    # Refresh Management
    def register_refresh_handler(
        self,
        credential_type: CredentialType,
        handler: CredentialRefreshHandler
    ):
        """Register refresh handler."""
        self.refresh_manager.register_handler(credential_type, handler)
    
    async def auto_refresh(self) -> List[RefreshResult]:
        """Auto-refresh expiring credentials."""
        return await self.refresh_manager.auto_refresh_expiring()