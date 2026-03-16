"""
Tests for phone number support in signup_gateway.py.

Covers:
  - Phone field on UserProfile dataclass
  - signup() accepts optional phone parameter
  - send_phone_otp() generates and stores a 6-digit OTP
  - validate_phone() verifies the OTP and marks phone as validated
  - to_dict() includes phone fields
  - is_fully_onboarded() still only requires email validation (phone is optional)
"""

import os


import pytest
from signup_gateway import SignupGateway, UserProfile, SignupError, AuthError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_gateway() -> SignupGateway:
    return SignupGateway()


def _signup(gw: SignupGateway, phone: str = "", email: str = "test@example.com") -> UserProfile:
    return gw.signup(
        name="Test User",
        email=email,
        position="Engineer",
        justification="Testing phone",
        new_org_name="TestCo",
        phone=phone,
    )


# ---------------------------------------------------------------------------
# UserProfile dataclass fields
# ---------------------------------------------------------------------------

class TestUserProfileFields:
    def test_phone_field_defaults_to_empty(self):
        profile = UserProfile()
        assert profile.phone == ""

    def test_phone_validated_defaults_to_false(self):
        profile = UserProfile()
        assert profile.phone_validated is False

    def test_phone_validation_code_defaults_to_empty(self):
        profile = UserProfile()
        assert profile.phone_validation_code == ""

    def test_to_dict_includes_phone(self):
        profile = UserProfile(phone="+15551234567")
        d = profile.to_dict()
        assert "phone" in d
        assert d["phone"] == "+15551234567"

    def test_to_dict_includes_phone_validated(self):
        profile = UserProfile(phone_validated=True)
        d = profile.to_dict()
        assert "phone_validated" in d
        assert d["phone_validated"] is True

    def test_to_dict_excludes_phone_validation_code(self):
        """OTP code must NOT appear in the serialized dict (security)."""
        profile = UserProfile(phone_validation_code="123456")
        d = profile.to_dict()
        assert "phone_validation_code" not in d


# ---------------------------------------------------------------------------
# signup() with phone
# ---------------------------------------------------------------------------

class TestSignupWithPhone:
    def test_signup_without_phone_succeeds(self):
        gw = _make_gateway()
        profile = _signup(gw)
        assert profile.phone == ""

    def test_signup_with_phone_stores_phone(self):
        gw = _make_gateway()
        profile = _signup(gw, phone="+15551234567")
        assert profile.phone == "+15551234567"

    def test_signup_phone_stripped_of_whitespace(self):
        gw = _make_gateway()
        profile = _signup(gw, phone="  +1 555 000 0000  ")
        assert profile.phone == "+1 555 000 0000"

    def test_phone_validated_false_after_signup(self):
        gw = _make_gateway()
        profile = _signup(gw, phone="+15559876543")
        assert profile.phone_validated is False

    def test_signup_with_both_email_and_phone(self):
        gw = _make_gateway()
        profile = gw.signup(
            name="Dual User",
            email="dual@example.com",
            position="Manager",
            justification="Full profile",
            new_org_name="DualCo",
            phone="+447700900000",
        )
        assert profile.email == "dual@example.com"
        assert profile.phone == "+447700900000"


# ---------------------------------------------------------------------------
# send_phone_otp()
# ---------------------------------------------------------------------------

class TestSendPhoneOtp:
    def test_returns_6_digit_string(self):
        gw = _make_gateway()
        profile = _signup(gw, phone="+15550001111")
        otp = gw.send_phone_otp(profile.user_id)
        assert isinstance(otp, str)
        assert len(otp) == 6
        assert otp.isdigit()

    def test_otp_stored_on_profile(self):
        gw = _make_gateway()
        profile = _signup(gw, phone="+15550002222")
        otp = gw.send_phone_otp(profile.user_id)
        updated = gw.get_profile(profile.user_id)
        assert updated.phone_validation_code == otp

    def test_raises_if_user_not_found(self):
        gw = _make_gateway()
        with pytest.raises(AuthError):
            gw.send_phone_otp("nonexistent-user-id")

    def test_raises_if_no_phone_on_file(self):
        gw = _make_gateway()
        profile = _signup(gw)  # no phone
        with pytest.raises(SignupError):
            gw.send_phone_otp(profile.user_id)

    def test_returns_zero_padded_otp(self):
        """OTPs less than 100000 must be zero-padded to 6 digits."""
        gw = _make_gateway()
        profile = _signup(gw, phone="+10000000000")
        for _ in range(10):
            otp = gw.send_phone_otp(profile.user_id)
            assert len(otp) == 6


# ---------------------------------------------------------------------------
# validate_phone()
# ---------------------------------------------------------------------------

class TestValidatePhone:
    def test_correct_otp_marks_phone_validated(self):
        gw = _make_gateway()
        profile = _signup(gw, phone="+15553334444")
        otp = gw.send_phone_otp(profile.user_id)
        updated = gw.validate_phone(profile.user_id, otp)
        assert updated.phone_validated is True

    def test_correct_otp_clears_validation_code(self):
        gw = _make_gateway()
        profile = _signup(gw, phone="+15554445555")
        otp = gw.send_phone_otp(profile.user_id)
        gw.validate_phone(profile.user_id, otp)
        updated = gw.get_profile(profile.user_id)
        assert updated.phone_validation_code == ""

    def test_wrong_otp_raises_auth_error(self):
        gw = _make_gateway()
        profile = _signup(gw, phone="+15555556666")
        gw.send_phone_otp(profile.user_id)
        with pytest.raises(AuthError):
            gw.validate_phone(profile.user_id, "000000")

    def test_no_otp_issued_raises_auth_error(self):
        gw = _make_gateway()
        profile = _signup(gw, phone="+15556667777")
        with pytest.raises(AuthError):
            gw.validate_phone(profile.user_id, "123456")

    def test_user_not_found_raises_auth_error(self):
        gw = _make_gateway()
        with pytest.raises(AuthError):
            gw.validate_phone("nonexistent", "123456")

    def test_no_phone_raises_signup_error(self):
        gw = _make_gateway()
        profile = _signup(gw)  # no phone
        with pytest.raises(SignupError):
            gw.validate_phone(profile.user_id, "123456")


# ---------------------------------------------------------------------------
# is_fully_onboarded() — phone is optional
# ---------------------------------------------------------------------------

class TestFullyOnboarded:
    def test_phone_not_required_for_onboarding(self):
        """Phone validation is optional — email + EULA is sufficient."""
        gw = _make_gateway()
        profile = _signup(gw)  # no phone
        gw.validate_email(profile.user_id, profile.email_validation_token)
        gw.accept_eula(profile.user_id, ip_address="127.0.0.1")
        assert gw.get_profile(profile.user_id).is_fully_onboarded() is True

    def test_phone_validated_does_not_affect_onboarding_requirement(self):
        gw = _make_gateway()
        profile = _signup(gw, phone="+15557778888")
        # Validate email and accept EULA
        gw.validate_email(profile.user_id, profile.email_validation_token)
        gw.accept_eula(profile.user_id, ip_address="127.0.0.1")
        # Validate phone too
        otp = gw.send_phone_otp(profile.user_id)
        gw.validate_phone(profile.user_id, otp)
        # Still fully onboarded
        assert gw.get_profile(profile.user_id).is_fully_onboarded() is True

    def test_phone_only_is_not_sufficient_for_onboarding(self):
        """Phone validation alone is NOT sufficient — email still required."""
        gw = _make_gateway()
        profile = _signup(gw, phone="+15558889999")
        otp = gw.send_phone_otp(profile.user_id)
        gw.validate_phone(profile.user_id, otp)
        assert gw.get_profile(profile.user_id).is_fully_onboarded() is False
