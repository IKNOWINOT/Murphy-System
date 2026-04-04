"""
Tests for Security Plane - Entrance & Exit Hardening
====================================================

Tests input validation, output encoding, and injection prevention.
"""

import pytest
from src.security_plane.hardening import (
    ValidationError,
    InjectionAttemptError,
    InputType,
    OutputContext,
    ValidationRule,
    InputValidator,
    OutputEncoder,
    CommandInjectionPreventer,
    PathTraversalPreventer,
    HardeningStatistics
)


class TestValidationRule:
    """Test validation rules"""

    def test_string_validation(self):
        """Test string validation"""
        rule = ValidationRule(
            input_type=InputType.STRING,
            min_length=3,
            max_length=10
        )

        assert rule.validate("hello", "test") == "hello"

        with pytest.raises(ValidationError):
            rule.validate("ab", "test")  # Too short

        with pytest.raises(ValidationError):
            rule.validate("12345678901", "test")  # Too long

    def test_integer_validation(self):
        """Test integer validation"""
        rule = ValidationRule(
            input_type=InputType.INTEGER,
            min_value=0,
            max_value=100
        )

        assert rule.validate(50, "test") == 50
        assert rule.validate("50", "test") == 50

        with pytest.raises(ValidationError):
            rule.validate(-1, "test")  # Too small

        with pytest.raises(ValidationError):
            rule.validate(101, "test")  # Too large

    def test_email_validation(self):
        """Test email validation"""
        rule = ValidationRule(input_type=InputType.EMAIL)

        assert rule.validate("user@example.com", "email") == "user@example.com"
        assert rule.validate("USER@EXAMPLE.COM", "email") == "user@example.com"  # Lowercase

        with pytest.raises(ValidationError):
            rule.validate("invalid-email", "email")

        with pytest.raises(ValidationError):
            rule.validate("@example.com", "email")

    def test_url_validation(self):
        """Test URL validation"""
        rule = ValidationRule(input_type=InputType.URL)

        assert rule.validate("https://example.com", "url") == "https://example.com"
        assert rule.validate("http://example.com/path", "url") == "http://example.com/path"

        with pytest.raises(ValidationError):
            rule.validate("ftp://example.com", "url")  # Only HTTP/HTTPS allowed

        with pytest.raises(ValidationError):
            rule.validate("not-a-url", "url")

    def test_path_validation_blocks_traversal(self):
        """Test path validation blocks traversal attempts"""
        rule = ValidationRule(input_type=InputType.PATH)

        assert rule.validate("file.txt", "path") == "file.txt"
        assert rule.validate("dir/file.txt", "path") == "dir/file.txt"

        with pytest.raises(InjectionAttemptError):
            rule.validate("../etc/passwd", "path")

        with pytest.raises(InjectionAttemptError):
            rule.validate("dir/../../etc/passwd", "path")

        with pytest.raises(ValidationError):
            rule.validate("/etc/passwd", "path")  # Absolute path

    def test_command_validation_blocks_injection(self):
        """Test command validation blocks injection attempts"""
        rule = ValidationRule(input_type=InputType.COMMAND)

        assert rule.validate("ls -la", "cmd") == "ls -la"

        with pytest.raises(InjectionAttemptError):
            rule.validate("ls; rm -rf /", "cmd")  # Command chaining

        with pytest.raises(InjectionAttemptError):
            rule.validate("ls | grep secret", "cmd")  # Pipe

        with pytest.raises(InjectionAttemptError):
            rule.validate("ls $(whoami)", "cmd")  # Command substitution

    def test_json_validation(self):
        """Test JSON validation"""
        rule = ValidationRule(input_type=InputType.JSON)

        result = rule.validate('{"key": "value"}', "json")
        assert result == {"key": "value"}

        result = rule.validate({"key": "value"}, "json")
        assert result == {"key": "value"}

        with pytest.raises(ValidationError):
            rule.validate("not-json", "json")

    def test_uuid_validation(self):
        """Test UUID validation"""
        rule = ValidationRule(input_type=InputType.UUID)

        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        assert rule.validate(valid_uuid, "uuid") == valid_uuid

        with pytest.raises(ValidationError):
            rule.validate("not-a-uuid", "uuid")

    def test_identifier_validation(self):
        """Test identifier validation"""
        rule = ValidationRule(input_type=InputType.IDENTIFIER)

        assert rule.validate("valid_identifier", "id") == "valid_identifier"
        assert rule.validate("_private", "id") == "_private"
        assert rule.validate("CamelCase123", "id") == "CamelCase123"

        with pytest.raises(ValidationError):
            rule.validate("123invalid", "id")  # Can't start with number

        with pytest.raises(ValidationError):
            rule.validate("invalid-identifier", "id")  # No hyphens

    def test_required_field(self):
        """Test required field validation"""
        rule = ValidationRule(input_type=InputType.STRING, required=True)

        with pytest.raises(ValidationError):
            rule.validate(None, "test")

        with pytest.raises(ValidationError):
            rule.validate("", "test")

    def test_optional_field(self):
        """Test optional field validation"""
        rule = ValidationRule(input_type=InputType.STRING, required=False)

        assert rule.validate(None, "test") is None
        assert rule.validate("", "test") is None


class TestInputValidator:
    """Test input validator"""

    def test_validate_multiple_fields(self):
        """Test validating multiple fields"""
        validator = InputValidator()
        validator.add_rule("name", ValidationRule(InputType.STRING, min_length=3))
        validator.add_rule("age", ValidationRule(InputType.INTEGER, min_value=0))
        validator.add_rule("email", ValidationRule(InputType.EMAIL))

        data = {
            "name": "John",
            "age": 30,
            "email": "john@example.com"
        }

        result = validator.validate(data)
        assert result["name"] == "John"
        assert result["age"] == 30
        assert result["email"] == "john@example.com"

    def test_validate_rejects_unexpected_fields(self):
        """Test validation rejects unexpected fields"""
        validator = InputValidator()
        validator.add_rule("name", ValidationRule(InputType.STRING))

        data = {
            "name": "John",
            "unexpected": "value"
        }

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(data)
        assert "Unexpected fields" in str(exc_info.value)

    def test_validate_single_field(self):
        """Test validating single field"""
        validator = InputValidator()
        validator.add_rule("email", ValidationRule(InputType.EMAIL))

        result = validator.validate_single("email", "user@example.com")
        assert result == "user@example.com"


class TestOutputEncoder:
    """Test output encoder"""

    def test_encode_html(self):
        """Test HTML encoding"""
        dangerous = '<script>alert("XSS")</script>'
        encoded = OutputEncoder.encode_html(dangerous)

        assert "<script>" not in encoded
        assert "&lt;script&gt;" in encoded

    def test_encode_html_attribute(self):
        """Test HTML attribute encoding"""
        dangerous = '" onclick="alert(\'XSS\')"'
        encoded = OutputEncoder.encode_html_attribute(dangerous)

        assert '"' not in encoded
        assert "onclick" not in encoded or r"&quot;" in encoded

    def test_encode_javascript(self):
        """Test JavaScript encoding"""
        dangerous = '"; alert("XSS"); "'
        encoded = OutputEncoder.encode_javascript(dangerous)

        assert '\\"' in encoded or '&quot;' in encoded
        assert 'alert("XSS")' not in encoded

    def test_encode_url(self):
        """Test URL encoding"""
        dangerous = "hello world&param=value"
        encoded = OutputEncoder.encode_url(dangerous)

        assert " " not in encoded
        assert "%20" in encoded

    def test_encode_url_parameter(self):
        """Test URL parameter encoding"""
        dangerous = "hello world"
        encoded = OutputEncoder.encode_url_parameter(dangerous)

        assert " " not in encoded
        assert "+" in encoded or "%20" in encoded

    def test_encode_json(self):
        """Test JSON encoding"""
        data = {"key": "value", "number": 123}
        encoded = OutputEncoder.encode_json(data)

        assert '"key"' in encoded
        assert '"value"' in encoded
        assert "123" in encoded

    def test_encode_xml(self):
        """Test XML encoding"""
        dangerous = '<tag attr="value">content & more</tag>'
        encoded = OutputEncoder.encode_xml(dangerous)

        assert "&lt;" in encoded
        assert "&gt;" in encoded
        assert "&amp;" in encoded
        assert "&quot;" in encoded

    def test_encode_shell(self):
        """Test shell encoding"""
        dangerous = "file name with spaces.txt"
        encoded = OutputEncoder.encode_shell(dangerous)

        # Should be quoted
        assert encoded.startswith("'") or encoded.startswith('"')

    def test_encode_sql(self):
        """Test SQL encoding"""
        dangerous = "O'Reilly"
        encoded = OutputEncoder.encode_sql(dangerous)

        assert "''" in encoded  # Single quote escaped


class TestCommandInjectionPreventer:
    """Test command injection prevention"""

    def test_safe_commands_allowed(self):
        """Test safe commands are allowed"""
        assert CommandInjectionPreventer.is_safe_command("ls -la")
        assert CommandInjectionPreventer.is_safe_command("grep pattern file.txt")
        assert CommandInjectionPreventer.is_safe_command("python script.py")

    def test_command_chaining_blocked(self):
        """Test command chaining is blocked"""
        assert not CommandInjectionPreventer.is_safe_command("ls; rm -rf /")
        assert not CommandInjectionPreventer.is_safe_command("ls && rm file")
        assert not CommandInjectionPreventer.is_safe_command("ls || echo fail")

    def test_pipe_blocked(self):
        """Test pipe is blocked"""
        assert not CommandInjectionPreventer.is_safe_command("ls | grep secret")

    def test_command_substitution_blocked(self):
        """Test command substitution is blocked"""
        assert not CommandInjectionPreventer.is_safe_command("ls $(whoami)")
        assert not CommandInjectionPreventer.is_safe_command("ls `whoami`")

    def test_redirection_blocked(self):
        """Test redirection is blocked"""
        assert not CommandInjectionPreventer.is_safe_command("cat file > /etc/passwd")
        assert not CommandInjectionPreventer.is_safe_command("cat < /etc/passwd")

    def test_disallowed_commands_blocked(self):
        """Test disallowed commands are blocked"""
        assert not CommandInjectionPreventer.is_safe_command("rm -rf /")
        assert not CommandInjectionPreventer.is_safe_command("sudo su")
        assert not CommandInjectionPreventer.is_safe_command("curl http://evil.com")

    def test_sanitize_command(self):
        """Test command sanitization"""
        result = CommandInjectionPreventer.sanitize_command("ls -la /tmp")
        assert result == ["ls", "-la", "/tmp"]

        with pytest.raises(InjectionAttemptError):
            CommandInjectionPreventer.sanitize_command("ls; rm -rf /")


class TestPathTraversalPreventer:
    """Test path traversal prevention"""

    def test_safe_paths_allowed(self):
        """Test safe paths are allowed"""
        preventer = PathTraversalPreventer(["/workspace"])

        assert preventer.is_safe_path("/workspace/file.txt")
        assert preventer.is_safe_path("/workspace/dir/file.txt")

    def test_traversal_blocked(self):
        """Test path traversal is blocked"""
        preventer = PathTraversalPreventer(["/workspace"])

        assert not preventer.is_safe_path("/workspace/../etc/passwd")
        assert not preventer.is_safe_path("/etc/passwd")

    def test_sanitize_path(self):
        """Test path sanitization"""
        preventer = PathTraversalPreventer(["/workspace"])

        result = preventer.sanitize_path("/workspace/file.txt")
        assert "file.txt" in str(result)

        with pytest.raises(InjectionAttemptError):
            preventer.sanitize_path("/workspace/../etc/passwd")


class TestHardeningStatistics:
    """Test hardening statistics"""

    def test_statistics_creation(self):
        """Test creating statistics"""
        stats = HardeningStatistics(
            total_validations=100,
            successful_validations=95,
            failed_validations=5,
            injection_attempts_blocked=3
        )

        assert stats.total_validations == 100
        assert stats.successful_validations == 95
        assert stats.failed_validations == 5
        assert stats.injection_attempts_blocked == 3

    def test_statistics_to_dict(self):
        """Test converting statistics to dict"""
        stats = HardeningStatistics(total_validations=10)
        result = stats.to_dict()

        assert isinstance(result, dict)
        assert result["total_validations"] == 10


class TestIntegration:
    """Test integrated hardening scenarios"""

    def test_validate_and_encode_user_input(self):
        """Test validating and encoding user input"""
        # Validate input
        validator = InputValidator()
        validator.add_rule("comment", ValidationRule(InputType.STRING, max_length=200))

        user_input = {
            "comment": '<script>alert("XSS")</script>'
        }

        validated = validator.validate(user_input)

        # Encode for HTML output
        encoded = OutputEncoder.encode_html(validated["comment"])

        assert "<script>" not in encoded
        assert "&lt;script&gt;" in encoded

    def test_prevent_sql_injection(self):
        """Test preventing SQL injection"""
        validator = InputValidator()
        validator.add_rule("username", ValidationRule(InputType.STRING, max_length=50))

        malicious_input = {
            "username": "admin' OR '1'='1"
        }

        validated = validator.validate(malicious_input)

        # Encode for SQL (though parameterized queries preferred)
        encoded = OutputEncoder.encode_sql(validated["username"])

        assert "''" in encoded  # Single quotes escaped

    def test_prevent_command_injection_workflow(self):
        """Test preventing command injection in workflow"""
        # User wants to list files
        user_command = "ls -la"

        # Validate command is safe
        assert CommandInjectionPreventer.is_safe_command(user_command)

        # Sanitize into argument list
        args = CommandInjectionPreventer.sanitize_command(user_command)
        assert args == ["ls", "-la"]

        # Malicious attempt
        malicious_command = "ls; rm -rf /"
        assert not CommandInjectionPreventer.is_safe_command(malicious_command)

        with pytest.raises(InjectionAttemptError):
            CommandInjectionPreventer.sanitize_command(malicious_command)

    def test_prevent_path_traversal_workflow(self):
        """Test preventing path traversal in workflow"""
        preventer = PathTraversalPreventer(["/workspace"])

        # Safe file access
        safe_path = "/workspace/data/file.txt"
        assert preventer.is_safe_path(safe_path)
        sanitized = preventer.sanitize_path(safe_path)
        assert "file.txt" in str(sanitized)

        # Malicious attempt
        malicious_path = "/workspace/../etc/passwd"
        assert not preventer.is_safe_path(malicious_path)

        with pytest.raises(InjectionAttemptError):
            preventer.sanitize_path(malicious_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
