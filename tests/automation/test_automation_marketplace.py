"""
Tests for AutomationMarketplace — publish, install, review, search,
get_popular, deprecate, and community reuse tracking.

Design Label: TEST-MARKETPLACE-001
Owner: QA Team
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from automation_marketplace import (
    AutomationCategory,
    AutomationListing,
    AutomationMarketplace,
    ListingStatus,
    MarketplaceError,
    OwnerType,
    Review,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mp():
    return AutomationMarketplace()


@pytest.fixture
def listing(mp):
    return mp.publish(
        name="Auto-run pytest",
        description="Run pytest on file save",
        owner_id="u1",
        automation_spec={"trigger": "file_change", "command": "pytest"},
        category=AutomationCategory.CI_CD,
        owner_type=OwnerType.USER,
        tags=["testing", "ci"],
    )


# ---------------------------------------------------------------------------
# AutomationListing model
# ---------------------------------------------------------------------------


class TestAutomationListing:
    def test_defaults(self):
        listing = AutomationListing()
        assert listing.listing_id
        assert listing.status == ListingStatus.DRAFT
        assert listing.use_count == 0
        assert listing.inoni_license_granted is True

    def test_to_dict_keys(self):
        listing = AutomationListing(name="T", owner_id="u1")
        d = listing.to_dict()
        for key in ["listing_id", "name", "owner_id", "owner_type", "status",
                    "use_count", "install_count", "inoni_license_granted"]:
            assert key in d

    def test_content_hash_stable(self):
        listing = AutomationListing(automation_spec={"cmd": "pytest"})
        assert listing.content_hash() == listing.content_hash()

    def test_content_hash_changes_with_spec(self):
        l1 = AutomationListing(automation_spec={"cmd": "pytest"})
        l2 = AutomationListing(automation_spec={"cmd": "make test"})
        assert l1.content_hash() != l2.content_hash()


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------


class TestPublish:
    def test_publish_returns_listing(self, mp):
        lst = mp.publish(
            name="My Automation",
            description="Does things",
            owner_id="u1",
            automation_spec={"type": "schedule"},
        )
        assert isinstance(lst, AutomationListing)
        assert lst.status == ListingStatus.PUBLISHED
        assert lst.published_at

    def test_publish_requires_name(self, mp):
        with pytest.raises(MarketplaceError, match="name"):
            mp.publish(name="", description="D", owner_id="u1",
                       automation_spec={"x": 1})

    def test_publish_requires_owner(self, mp):
        with pytest.raises(MarketplaceError, match="owner_id"):
            mp.publish(name="N", description="D", owner_id="",
                       automation_spec={"x": 1})

    def test_publish_requires_spec(self, mp):
        with pytest.raises(MarketplaceError, match="automation_spec"):
            mp.publish(name="N", description="D", owner_id="u1",
                       automation_spec={})

    def test_inoni_license_always_granted(self, mp):
        lst = mp.publish("N", "D", "u1", {"cmd": "x"})
        assert lst.inoni_license_granted is True

    def test_publish_from_suggestion(self, mp):
        suggestion = {
            "title": "Auto-commit",
            "description": "Commit on save",
            "automation_spec": {"trigger": "save", "action": "git commit"},
        }
        lst = mp.publish_from_suggestion(suggestion, owner_id="u1")
        assert lst.name == "Auto-commit"
        assert lst.status == ListingStatus.PUBLISHED

    def test_user_and_org_owner_types_supported(self, mp):
        user_lst = mp.publish("U", "D", "u1", {"x": 1}, owner_type=OwnerType.USER)
        org_lst = mp.publish("O", "D", "org1", {"x": 1}, owner_type=OwnerType.ORGANIZATION)
        assert user_lst.owner_type == OwnerType.USER
        assert org_lst.owner_type == OwnerType.ORGANIZATION


# ---------------------------------------------------------------------------
# Install & usage
# ---------------------------------------------------------------------------


class TestInstallAndUsage:
    def test_record_install_increments_count(self, mp, listing):
        mp.record_install(listing.listing_id, user_id="u2")
        updated = mp.get_listing(listing.listing_id)
        assert updated.install_count == 1

    def test_duplicate_install_counted_once(self, mp, listing):
        mp.record_install(listing.listing_id, "u2")
        mp.record_install(listing.listing_id, "u2")  # same user
        updated = mp.get_listing(listing.listing_id)
        assert updated.install_count == 1

    def test_multiple_users_install(self, mp, listing):
        mp.record_install(listing.listing_id, "u2")
        mp.record_install(listing.listing_id, "u3")
        updated = mp.get_listing(listing.listing_id)
        assert updated.install_count == 2

    def test_record_install_unknown_listing(self, mp):
        assert mp.record_install("notexist", "u1") is False

    def test_record_use_increments_counter(self, mp, listing):
        mp.record_use(listing.listing_id)
        mp.record_use(listing.listing_id)
        updated = mp.get_listing(listing.listing_id)
        assert updated.use_count == 2


# ---------------------------------------------------------------------------
# Reviews & ratings
# ---------------------------------------------------------------------------


class TestReviewsAndRatings:
    def test_add_review_updates_average(self, mp, listing):
        mp.add_review(listing.listing_id, "u2", rating=5)
        mp.add_review(listing.listing_id, "u3", rating=3)
        updated = mp.get_listing(listing.listing_id)
        assert updated.average_rating == pytest.approx(4.0)
        assert updated.review_count == 2

    def test_add_review_invalid_rating(self, mp, listing):
        with pytest.raises(MarketplaceError, match="rating"):
            mp.add_review(listing.listing_id, "u2", rating=6)

    def test_add_review_unknown_listing(self, mp):
        with pytest.raises(MarketplaceError, match="listing not found"):
            mp.add_review("notexist", "u2", rating=4)

    def test_get_reviews(self, mp, listing):
        mp.add_review(listing.listing_id, "u2", rating=4, comment="Great!")
        reviews = mp.get_reviews(listing.listing_id)
        assert len(reviews) == 1
        assert reviews[0].comment == "Great!"


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class TestSearch:
    def test_search_by_query(self, mp, listing):
        results = mp.search("pytest")
        ids = [l.listing_id for l in results]
        assert listing.listing_id in ids

    def test_search_by_category(self, mp, listing):
        results = mp.search(category=AutomationCategory.CI_CD)
        assert all(l.category == AutomationCategory.CI_CD for l in results)

    def test_search_by_tags(self, mp, listing):
        results = mp.search(tags=["testing"])
        ids = [l.listing_id for l in results]
        assert listing.listing_id in ids

    def test_search_no_match(self, mp, listing):
        results = mp.search("zzz_no_match_zzz")
        assert results == []

    def test_search_excludes_deprecated(self, mp, listing):
        mp.deprecate(listing.listing_id, owner_id="u1")
        results = mp.search("pytest")
        ids = [l.listing_id for l in results]
        assert listing.listing_id not in ids

    def test_search_respects_limit(self, mp):
        for i in range(25):
            mp.publish(f"Auto{i}", "D", "u1",
                       {"cmd": f"cmd{i}"}, tags=["batch"])
        results = mp.search("Auto", limit=10)
        assert len(results) <= 10


# ---------------------------------------------------------------------------
# get_popular
# ---------------------------------------------------------------------------


class TestGetPopular:
    def test_get_popular_sorted_by_installs(self, mp):
        l1 = mp.publish("L1", "D", "u1", {"x": 1})
        l2 = mp.publish("L2", "D", "u1", {"x": 2})
        l3 = mp.publish("L3", "D", "u1", {"x": 3})
        for _ in range(3):
            mp.record_install(l3.listing_id, f"u_{_}")
        for _ in range(1):
            mp.record_install(l2.listing_id, "u_x")

        popular = mp.get_popular()
        ids = [l.listing_id for l in popular]
        assert ids.index(l3.listing_id) < ids.index(l2.listing_id)

    def test_get_popular_respects_limit(self, mp):
        for i in range(15):
            mp.publish(f"P{i}", "D", "u1", {"x": i})
        popular = mp.get_popular(limit=5)
        assert len(popular) <= 5


# ---------------------------------------------------------------------------
# get_similar
# ---------------------------------------------------------------------------


class TestGetSimilar:
    def test_get_similar_same_category(self, mp, listing):
        l2 = mp.publish("Other CI", "D", "u2", {"cmd": "make"},
                        category=AutomationCategory.CI_CD)
        similar = mp.get_similar(listing.listing_id)
        ids = [l.listing_id for l in similar]
        assert l2.listing_id in ids

    def test_get_similar_excludes_self(self, mp, listing):
        similar = mp.get_similar(listing.listing_id)
        ids = [l.listing_id for l in similar]
        assert listing.listing_id not in ids


# ---------------------------------------------------------------------------
# Deprecate
# ---------------------------------------------------------------------------


class TestDeprecate:
    def test_deprecate_by_owner(self, mp, listing):
        result = mp.deprecate(listing.listing_id, owner_id="u1")
        assert result is True
        updated = mp.get_listing(listing.listing_id)
        assert updated.status == ListingStatus.DEPRECATED

    def test_deprecate_by_non_owner(self, mp, listing):
        result = mp.deprecate(listing.listing_id, owner_id="u999")
        assert result is False

    def test_deprecated_listing_not_in_search(self, mp, listing):
        mp.deprecate(listing.listing_id, owner_id="u1")
        results = mp.search("pytest")
        assert not any(l.listing_id == listing.listing_id for l in results)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestStats:
    def test_stats_counts_listings(self, mp, listing):
        stats = mp.stats()
        assert stats["published_listings"] >= 1

    def test_stats_counts_installs(self, mp, listing):
        mp.record_install(listing.listing_id, "u2")
        stats = mp.stats()
        assert stats["total_installs"] >= 1


# ---------------------------------------------------------------------------
# get_user_listings
# ---------------------------------------------------------------------------


class TestGetUserListings:
    def test_returns_only_owner_listings(self, mp):
        mp.publish("A1", "D", "owner1", {"x": 1})
        mp.publish("A2", "D", "owner1", {"x": 2})
        mp.publish("B1", "D", "owner2", {"x": 3})
        lst = mp.get_user_listings("owner1")
        assert len(lst) == 2
        assert all(l.owner_id == "owner1" for l in lst)


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


class TestAuditLog:
    def test_audit_log_populated(self, mp, listing):
        mp.record_install(listing.listing_id, "u2")
        log = mp.get_audit_log()
        actions = [e["action"] for e in log]
        assert "publish" in actions
        assert "install" in actions

    def test_audit_entries_have_timestamp(self, mp, listing):
        for entry in mp.get_audit_log():
            assert "timestamp" in entry
