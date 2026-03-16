"""
Tests for Agentic Onboarding & Account Setup Engine.

Covers:
- OnboardingProfile creation for every business type
- Requirements extraction from sample text
- Integration provisioning flow
- Regulatory zone resolution for multiple countries
- Deployment manifest generation (all platforms)
- Full end-to-end onboarding pipeline

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import threading
import pytest

from src.agentic_onboarding_engine import (
    AgenticOnboardingEngine,
    OnboardingOrchestrator,
    OnboardingProfile,
    BUSINESS_DEMOGRAPHICS,
    REGULATORY_ZONES,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def orchestrator():
    return OnboardingOrchestrator()


@pytest.fixture
def engine():
    return AgenticOnboardingEngine()


# ---------------------------------------------------------------------------
# OnboardingProfile dataclass
# ---------------------------------------------------------------------------


class TestOnboardingProfile:
    def test_profile_has_required_fields(self):
        p = OnboardingProfile(
            profile_id="test-001",
            business_name="Acme Corp",
            business_type="small_retail",
            industry="retail",
            country="US",
            region="CA",
            language="en",
            regulatory_zone="us_federal_state",
            email="owner@acme.com",
        )
        assert p.profile_id == "test-001"
        assert p.business_name == "Acme Corp"
        assert p.status == "intake"
        assert p.deployment_target == "cloudflare"
        assert p.requirements_extracted == []
        assert p.integrations_needed == []
        assert p.integrations_provisioned == {}

    def test_profile_created_at_is_utc_iso(self):
        p = OnboardingProfile(
            profile_id="test-002",
            business_name="B",
            business_type="restaurant",
            industry="food",
            country="GB",
            region="",
            language="en",
            regulatory_zone="uk",
            email="b@b.com",
        )
        assert "T" in p.created_at  # ISO format contains 'T'
        assert "+" in p.created_at or "Z" in p.created_at or p.created_at.endswith("+00:00")


# ---------------------------------------------------------------------------
# BUSINESS_DEMOGRAPHICS catalog
# ---------------------------------------------------------------------------


class TestBusinessDemographics:
    def test_all_expected_types_present(self):
        expected = [
            "sole_proprietor", "small_retail", "restaurant", "professional_services",
            "manufacturing", "healthcare", "construction", "logistics", "real_estate",
            "education", "nonprofit", "agriculture", "enterprise",
        ]
        for btype in expected:
            assert btype in BUSINESS_DEMOGRAPHICS, f"Missing: {btype}"

    def test_each_type_has_integrations_list(self):
        for btype, data in BUSINESS_DEMOGRAPHICS.items():
            assert "integrations" in data, f"Missing integrations key for {btype}"
            assert isinstance(data["integrations"], list)
            assert len(data["integrations"]) > 0

    @pytest.mark.parametrize("btype", list(BUSINESS_DEMOGRAPHICS.keys()))
    def test_business_type_integrations_are_strings(self, btype):
        for integration in BUSINESS_DEMOGRAPHICS[btype]["integrations"]:
            assert isinstance(integration, str)


# ---------------------------------------------------------------------------
# REGULATORY_ZONES catalog
# ---------------------------------------------------------------------------


class TestRegulatoryZones:
    @pytest.mark.parametrize("country,expected_zone", [
        ("US", "us_federal_state"),
        ("GB", "uk"),
        ("DE", "eu"),
        ("JP", "apac"),
        ("AU", "apac"),
        ("BR", "latam"),
        ("CA", "canada"),
        ("IN", "apac"),
        ("AE", "mena"),
    ])
    def test_known_countries_resolve_correctly(self, country, expected_zone):
        assert REGULATORY_ZONES[country]["zone"] == expected_zone

    def test_default_zone_present(self):
        assert "default" in REGULATORY_ZONES
        assert REGULATORY_ZONES["default"]["zone"] == "international"

    def test_each_zone_has_frameworks(self):
        for country, data in REGULATORY_ZONES.items():
            assert "frameworks" in data, f"Missing frameworks for {country}"
            assert isinstance(data["frameworks"], list)
            assert len(data["frameworks"]) > 0


# ---------------------------------------------------------------------------
# Profile creation for each business type
# ---------------------------------------------------------------------------


class TestProfileCreation:
    @pytest.mark.parametrize("btype", list(BUSINESS_DEMOGRAPHICS.keys()))
    def test_start_onboarding_for_every_business_type(self, orchestrator, btype):
        profile = orchestrator.start_onboarding(
            business_name=f"Test {btype}",
            business_type=btype,
            industry="test_industry",
            country="US",
            language="en",
            email=f"test@{btype}.com",
        )
        assert isinstance(profile, OnboardingProfile)
        assert profile.business_type == btype
        assert profile.status == "intake"
        assert profile.regulatory_zone == "us_federal_state"
        expected_integrations = BUSINESS_DEMOGRAPHICS[btype]["integrations"]
        assert profile.integrations_needed == expected_integrations

    def test_profile_id_is_unique(self, orchestrator):
        p1 = orchestrator.start_onboarding("A", "restaurant", "food", "US", "en", "a@a.com")
        p2 = orchestrator.start_onboarding("B", "restaurant", "food", "US", "en", "b@b.com")
        assert p1.profile_id != p2.profile_id

    def test_profile_stored_in_orchestrator(self, orchestrator):
        profile = orchestrator.start_onboarding("C", "education", "edu", "CA", "en", "c@c.com")
        retrieved = orchestrator.get_profile(profile.profile_id)
        assert retrieved is not None
        assert retrieved.profile_id == profile.profile_id

    def test_unknown_business_type_has_no_integrations(self, orchestrator):
        profile = orchestrator.start_onboarding(
            "X", "unknown_type", "misc", "US", "en", "x@x.com"
        )
        assert profile.integrations_needed == []

    def test_unknown_country_gets_default_zone(self, orchestrator):
        profile = orchestrator.start_onboarding(
            "Y", "sole_proprietor", "misc", "ZZ", "en", "y@y.com"
        )
        assert profile.regulatory_zone == "international"


# ---------------------------------------------------------------------------
# Requirements extraction
# ---------------------------------------------------------------------------


class TestRequirementsExtraction:
    def test_extract_from_bullet_list(self, orchestrator):
        profile = orchestrator.start_onboarding("D", "restaurant", "food", "US", "en", "d@d.com")
        text = "• Need online ordering\n• Need table reservations\n• Need staff scheduling"
        reqs = orchestrator.extract_requirements(profile.profile_id, text)
        assert len(reqs) == 3

    def test_extract_from_numbered_list(self, orchestrator):
        profile = orchestrator.start_onboarding("E", "healthcare", "health", "US", "en", "e@e.com")
        text = "1. Patient portal\n2. Appointment booking\n3. Billing integration"
        reqs = orchestrator.extract_requirements(profile.profile_id, text)
        assert len(reqs) == 3

    def test_extract_from_prose(self, orchestrator):
        profile = orchestrator.start_onboarding("F", "logistics", "transport", "GB", "en", "f@f.com")
        text = "We need fleet tracking; route optimisation; and a driver app"
        reqs = orchestrator.extract_requirements(profile.profile_id, text)
        assert len(reqs) >= 1

    def test_extract_empty_text_returns_empty(self, orchestrator):
        profile = orchestrator.start_onboarding("G", "nonprofit", "charity", "CA", "en", "g@g.com")
        reqs = orchestrator.extract_requirements(profile.profile_id, "")
        assert reqs == []

    def test_requirements_merged_into_profile(self, orchestrator):
        profile = orchestrator.start_onboarding("H", "agriculture", "farming", "AU", "en", "h@h.com")
        orchestrator.extract_requirements(profile.profile_id, "Need crop tracking; Need weather alerts")
        p = orchestrator.get_profile(profile.profile_id)
        assert len(p.requirements_extracted) >= 1

    def test_duplicate_requirements_not_added_twice(self, orchestrator):
        profile = orchestrator.start_onboarding("I", "education", "edu", "US", "en", "i@i.com")
        orchestrator.extract_requirements(profile.profile_id, "Need LMS")
        orchestrator.extract_requirements(profile.profile_id, "Need LMS")
        p = orchestrator.get_profile(profile.profile_id)
        count = p.requirements_extracted.count("Need LMS")
        assert count == 1

    def test_extract_invalid_profile_raises(self, orchestrator):
        with pytest.raises(KeyError):
            orchestrator.extract_requirements("nonexistent-id", "some text")


# ---------------------------------------------------------------------------
# Integration provisioning
# ---------------------------------------------------------------------------


class TestIntegrationProvisioning:
    def test_provision_returns_status_per_integration(self, orchestrator):
        profile = orchestrator.start_onboarding(
            "J", "small_retail", "retail", "US", "en", "j@j.com"
        )
        status = orchestrator.provision_integrations(profile.profile_id)
        for integration in BUSINESS_DEMOGRAPHICS["small_retail"]["integrations"]:
            assert integration in status
            assert status[integration] in ("active", "failed", "pending", "provisioning")

    def test_all_integrations_become_active(self, orchestrator):
        profile = orchestrator.start_onboarding(
            "K", "sole_proprietor", "freelance", "US", "en", "k@k.com"
        )
        status = orchestrator.provision_integrations(profile.profile_id)
        assert all(v == "active" for v in status.values())

    def test_profile_status_becomes_building_on_success(self, orchestrator):
        profile = orchestrator.start_onboarding(
            "L", "restaurant", "food", "DE", "en", "l@l.com"
        )
        orchestrator.provision_integrations(profile.profile_id)
        p = orchestrator.get_profile(profile.profile_id)
        assert p.status == "building"

    def test_provisioned_dict_stored_on_profile(self, orchestrator):
        profile = orchestrator.start_onboarding(
            "M", "professional_services", "law", "GB", "en", "m@m.com"
        )
        orchestrator.provision_integrations(profile.profile_id)
        p = orchestrator.get_profile(profile.profile_id)
        assert len(p.integrations_provisioned) == len(BUSINESS_DEMOGRAPHICS["professional_services"]["integrations"])

    def test_provision_invalid_profile_raises(self, orchestrator):
        with pytest.raises(KeyError):
            orchestrator.provision_integrations("nonexistent-id")


# ---------------------------------------------------------------------------
# Build system
# ---------------------------------------------------------------------------


class TestBuildSystem:
    def test_build_returns_config_dict(self, orchestrator):
        profile = orchestrator.start_onboarding(
            "N", "manufacturing", "industry", "JP", "en", "n@n.com"
        )
        orchestrator.provision_integrations(profile.profile_id)
        config = orchestrator.build_system(profile.profile_id)
        assert config["profile_id"] == profile.profile_id
        assert config["business_type"] == "manufacturing"
        assert "integrations" in config

    def test_build_includes_regulatory_frameworks(self, orchestrator):
        profile = orchestrator.start_onboarding(
            "O", "healthcare", "health", "US", "en", "o@o.com"
        )
        orchestrator.provision_integrations(profile.profile_id)
        config = orchestrator.build_system(profile.profile_id)
        assert "HIPAA" in config["frameworks"]

    def test_build_transitions_profile_to_deploying(self, orchestrator):
        profile = orchestrator.start_onboarding(
            "P", "real_estate", "property", "AU", "en", "p@p.com"
        )
        orchestrator.provision_integrations(profile.profile_id)
        orchestrator.build_system(profile.profile_id)
        p = orchestrator.get_profile(profile.profile_id)
        assert p.status == "deploying"

    def test_build_invalid_profile_raises(self, orchestrator):
        with pytest.raises(KeyError):
            orchestrator.build_system("nonexistent-id")


# ---------------------------------------------------------------------------
# Deployment manifest generation
# ---------------------------------------------------------------------------


class TestDeploy:
    def _run_pipeline(self, orchestrator, business_type, country):
        profile = orchestrator.start_onboarding(
            "TestBiz", business_type, "industry", country, "en", "test@test.com"
        )
        orchestrator.provision_integrations(profile.profile_id)
        orchestrator.build_system(profile.profile_id)
        return profile

    def test_cloudflare_manifest_structure(self, orchestrator):
        profile = self._run_pipeline(orchestrator, "logistics", "US")
        manifest = orchestrator.deploy(profile.profile_id, target="cloudflare")
        assert manifest["platform"] == "cloudflare"
        assert "wrangler_config" in manifest
        assert manifest["wrangler_config"]["vars"]["PROFILE_ID"] == profile.profile_id

    def test_aws_manifest_structure(self, orchestrator):
        profile = self._run_pipeline(orchestrator, "enterprise", "US")
        manifest = orchestrator.deploy(profile.profile_id, target="aws")
        assert manifest["platform"] == "aws"
        assert manifest["type"] == "lambda"
        assert "function_name" in manifest

    def test_gcp_manifest_structure(self, orchestrator):
        profile = self._run_pipeline(orchestrator, "education", "IN")
        manifest = orchestrator.deploy(profile.profile_id, target="gcp")
        assert manifest["platform"] == "gcp"
        assert manifest["type"] == "cloud_run"

    def test_self_hosted_manifest_structure(self, orchestrator):
        profile = self._run_pipeline(orchestrator, "nonprofit", "BR")
        manifest = orchestrator.deploy(profile.profile_id, target="self_hosted")
        assert manifest["platform"] == "self_hosted"
        assert manifest["type"] == "docker_compose"

    def test_default_deploy_target_is_cloudflare(self, orchestrator):
        profile = self._run_pipeline(orchestrator, "construction", "CA")
        manifest = orchestrator.deploy(profile.profile_id)
        assert manifest["platform"] == "cloudflare"

    def test_deploy_sets_profile_status_active(self, orchestrator):
        profile = self._run_pipeline(orchestrator, "small_retail", "AE")
        orchestrator.deploy(profile.profile_id, target="cloudflare")
        p = orchestrator.get_profile(profile.profile_id)
        assert p.status == "active"

    def test_deploy_manifest_contains_deployed_at(self, orchestrator):
        profile = self._run_pipeline(orchestrator, "agriculture", "AU")
        manifest = orchestrator.deploy(profile.profile_id, target="gcp")
        assert "deployed_at" in manifest
        assert "T" in manifest["deployed_at"]

    def test_deploy_invalid_profile_raises(self, orchestrator):
        with pytest.raises(KeyError):
            orchestrator.deploy("nonexistent-id")


# ---------------------------------------------------------------------------
# Full end-to-end pipeline
# ---------------------------------------------------------------------------


class TestEndToEndOnboarding:
    @pytest.mark.parametrize("btype,country,target", [
        ("sole_proprietor", "US", "cloudflare"),
        ("restaurant", "GB", "aws"),
        ("healthcare", "DE", "gcp"),
        ("enterprise", "JP", "self_hosted"),
        ("agriculture", "IN", "cloudflare"),
    ])
    def test_full_pipeline(self, orchestrator, btype, country, target):
        # Intake
        profile = orchestrator.start_onboarding(
            f"Test {btype}",
            btype,
            "test_industry",
            country,
            "en",
            f"owner@{btype}.com",
            requirements_text=f"We need the following for {btype}: automation and reporting",
        )
        assert profile.status == "intake"

        # Provisioning
        status = orchestrator.provision_integrations(profile.profile_id)
        assert all(v == "active" for v in status.values())

        # Building
        config = orchestrator.build_system(profile.profile_id)
        assert config["business_type"] == btype

        # Deployment
        manifest = orchestrator.deploy(profile.profile_id, target=target)
        assert manifest["platform"] == target
        assert manifest["profile_id"] == profile.profile_id

        # Final status
        final = orchestrator.get_profile(profile.profile_id)
        assert final.status == "active"

    def test_requirements_from_email_text_flow(self, orchestrator):
        profile = orchestrator.start_onboarding(
            "Spa & Wellness", "professional_services", "beauty", "US", "en", "spa@spa.com"
        )
        email_body = (
            "Hi Murphy,\n"
            "We need:\n"
            "• Online booking system\n"
            "• Client management\n"
            "• Payment processing\n"
            "Thank you"
        )
        reqs = orchestrator.extract_requirements(profile.profile_id, email_body)
        assert len(reqs) >= 3
        p = orchestrator.get_profile(profile.profile_id)
        assert len(p.requirements_extracted) >= 3


# ---------------------------------------------------------------------------
# List profiles and status summary
# ---------------------------------------------------------------------------


class TestProfileManagement:
    def test_list_profiles_returns_all(self, orchestrator):
        for i in range(3):
            orchestrator.start_onboarding(f"Biz{i}", "restaurant", "food", "US", "en", f"biz{i}@test.com")
        profiles = orchestrator.list_profiles()
        assert len(profiles) == 3

    def test_list_profiles_filtered_by_status(self, orchestrator):
        p1 = orchestrator.start_onboarding("A1", "logistics", "transport", "US", "en", "a1@t.com")
        orchestrator.start_onboarding("A2", "logistics", "transport", "US", "en", "a2@t.com")
        # Provision and deploy first profile to move it to active
        orchestrator.provision_integrations(p1.profile_id)
        orchestrator.build_system(p1.profile_id)
        orchestrator.deploy(p1.profile_id)
        active = orchestrator.list_profiles(status="active")
        intake = orchestrator.list_profiles(status="intake")
        assert len(active) == 1
        assert len(intake) == 1

    def test_get_onboarding_status_summary(self, orchestrator):
        orchestrator.start_onboarding("B1", "education", "edu", "CA", "en", "b1@e.com")
        orchestrator.start_onboarding("B2", "nonprofit", "charity", "BR", "en", "b2@n.com")
        summary = orchestrator.get_onboarding_status()
        assert summary["total_profiles"] == 2
        assert "by_status" in summary
        assert "by_business_type" in summary
        assert "success_rate" in summary
        assert 0.0 <= summary["success_rate"] <= 1.0

    def test_get_profile_returns_none_for_missing(self, orchestrator):
        assert orchestrator.get_profile("does-not-exist") is None


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_onboarding_creates_distinct_profiles(self, orchestrator):
        results = []
        errors = []

        def _onboard(idx):
            try:
                p = orchestrator.start_onboarding(
                    f"Biz{idx}", "small_retail", "retail", "US", "en", f"biz{idx}@t.com"
                )
                results.append(p.profile_id)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_onboard, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(set(results)) == 20  # all distinct IDs

    def test_concurrent_provisioning_is_safe(self, orchestrator):
        profiles = [
            orchestrator.start_onboarding(
                f"C{i}", "sole_proprietor", "misc", "US", "en", f"c{i}@t.com"
            )
            for i in range(5)
        ]
        errors = []

        def _provision(pid):
            try:
                orchestrator.provision_integrations(pid)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_provision, args=(p.profile_id,)) for p in profiles]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []


# ---------------------------------------------------------------------------
# AgenticOnboardingEngine
# ---------------------------------------------------------------------------


class TestAgenticOnboardingEngine:
    def test_engine_stores_and_retrieves_key(self, engine):
        key_name = "test_engine_key_001"
        engine.store_key(key_name, "secret_value_xyz")
        value = engine.retrieve_key(key_name)
        assert value == "secret_value_xyz"

    def test_engine_tracks_event(self, engine):
        engine.track_event("test_event", {"key": "value"})
        summary = engine.telemetry.get_telemetry_summary()
        assert summary["total_metrics"] >= 1

    def test_engine_records_and_replays_onboarding_path(self, engine):
        spec = {"steps": ["provision", "build", "deploy"], "business_type": "restaurant"}
        path_id = engine.record_onboarding_path("restaurant", spec, {"test": True})
        assert path_id is not None
        replayed = engine.replay_onboarding_path(path_id)
        assert replayed is not None
