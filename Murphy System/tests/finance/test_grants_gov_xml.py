# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

import xml.etree.ElementTree as ET
import pytest
from src.billing.grants.submission.format_adapters.grants_gov_xml import GrantsGovXMLBuilder


@pytest.fixture
def builder():
    return GrantsGovXMLBuilder()


@pytest.fixture
def sample_data():
    return {
        "federal_award_identifier": "FOA-2024-001",
        "organization_name": "Test Corp",
        "uei": "TESTUEI123",
        "ein": "12-3456789",
        "project_title": "Test Project",
        "start_date": "2024-01-01",
        "end_date": "2025-12-31",
        "federal_amount": 500000,
        "match_amount": 100000,
        "ar_name": "Jane Doe",
        "ar_title": "Executive Director",
        "ar_email": "jane@testcorp.org",
        "ar_phone": "503-555-0100",
    }


def test_build_returns_string(builder, sample_data):
    xml_str = builder.build_sf424_xml(sample_data)
    assert isinstance(xml_str, str)


def test_xml_has_declaration(builder, sample_data):
    xml_str = builder.build_sf424_xml(sample_data)
    assert xml_str.startswith("<?xml")


def test_xml_is_parseable(builder, sample_data):
    xml_str = builder.build_sf424_xml(sample_data)
    root = ET.fromstring(xml_str.split("\n", 1)[1])
    assert root is not None


def test_xml_has_grant_application_root(builder, sample_data):
    xml_str = builder.build_sf424_xml(sample_data)
    root = ET.fromstring(xml_str.split("\n", 1)[1])
    assert "GrantApplication" in root.tag


def test_xml_contains_organization_name(builder, sample_data):
    xml_str = builder.build_sf424_xml(sample_data)
    assert "Test Corp" in xml_str


def test_xml_contains_project_title(builder, sample_data):
    xml_str = builder.build_sf424_xml(sample_data)
    assert "Test Project" in xml_str


def test_xml_contains_federal_amount(builder, sample_data):
    xml_str = builder.build_sf424_xml(sample_data)
    assert "500000" in xml_str


def test_xml_contains_uei(builder, sample_data):
    xml_str = builder.build_sf424_xml(sample_data)
    assert "TESTUEI123" in xml_str


def test_xml_has_namespace(builder, sample_data):
    xml_str = builder.build_sf424_xml(sample_data)
    assert "grants.gov" in xml_str


def test_build_full_package_returns_dict(builder, sample_data):
    pkg = builder.build_full_package(sample_data)
    assert isinstance(pkg, dict)
    assert "sf424.xml" in pkg


def test_empty_data_produces_valid_xml(builder):
    xml_str = builder.build_sf424_xml({})
    root = ET.fromstring(xml_str.split("\n", 1)[1])
    assert root is not None
