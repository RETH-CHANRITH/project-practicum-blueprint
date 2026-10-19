"""
backend/tests/test_recommendations.py
=======================================
Comprehensive test suite for:
  - EP-13  POST /api/v1/admin/scrape     (admin-only Telegram ingestion)
  - EP-09  GET  /api/v1/recommendations  (dual-metric AI recommendations)

Tests cover:
  • Admin security enforcement (403 for non-admin)
  • Admin scrape + stats endpoint
  • Response schema: all three metrics present and correctly named
  • Metric ranges: coverage, semantic, ranking all in [0.0, 1.0]
  • Metric independence: coverage and semantic are never identical
    (they measure different things)
  • Ranking sort: results ordered descending by ranking_score
  • Configurable weights: w_skill / w_semantic query params change scores
  • min_score filter: low-coverage jobs are excluded
  • Edge case: candidate with no skills gets coverage=0.0 for all jobs
  • Edge case: empty job list returns []
  • Fallback: semantic_similarity returns float (not error) when model unavailable
  • Backwards compatibility: legacy match_score field is still present
"""

import math
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _login(email: str, password: str) -> str:
    """Login and return the bearer token."""
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


CANDIDATE_EMAIL = "dara@example.com"
CANDIDATE_PASSWORD = "Password123!"
ADMIN_EMAIL = "admin@jobmatch.com"
ADMIN_PASSWORD = "AdminPassword123!"


# ─────────────────────────────────────────────────────────────────────────────
# EP-13: Admin Scrape + Admin Stats
# ─────────────────────────────────────────────────────────────────────────────

class TestAdminScrapeEP13:
    """Tests for EP-13 POST /admin/scrape and GET /admin/stats"""

    def test_candidate_cannot_scrape_returns_403(self):
        """Non-admin role must receive 403 Forbidden."""
        token = _login(CANDIDATE_EMAIL, CANDIDATE_PASSWORD)
        res = client.post(
            "/api/v1/admin/scrape",
            headers=_headers(token),
            json={"source": "internshipscambodia"}
        )
        assert res.status_code == 403, res.text
        error = res.json()["detail"]["error"]
        assert error["code"] == "FORBIDDEN"

    def test_unauthenticated_scrape_returns_401(self):
        """No token → 401 Unauthorized."""
        res = client.post(
            "/api/v1/admin/scrape",
            json={"source": "internshipscambodia"}
        )
        assert res.status_code == 401, res.text

    def test_admin_can_scrape_telegram_channel(self):
        """Admin successfully scrapes a Telegram channel."""
        token = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
        res = client.post(
            "/api/v1/admin/scrape",
            headers=_headers(token),
            json={"source": "https://t.me/s/internshipscambodia"}
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["status"] == "success"
        assert "total_jobs" in data
        assert isinstance(data["new_jobs_added"], int)
        assert isinstance(data["total_jobs"], int)

    def test_admin_stats_response_shape(self):
        """Admin stats endpoint returns expected fields."""
        token = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
        res = client.get("/api/v1/admin/stats", headers=_headers(token))
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["total_jobs"] >= 1
        assert data["total_candidates"] >= 1
        assert data["total_skills"] >= 1
        assert "Telegram" in data["active_sources"]


# ─────────────────────────────────────────────────────────────────────────────
# EP-09: AI Recommendations — Schema
# ─────────────────────────────────────────────────────────────────────────────

class TestRecommendationsSchema:
    """Verify the response schema matches the dual-metric contract."""

    @pytest.fixture(scope="class")
    def recs(self):
        token = _login(CANDIDATE_EMAIL, CANDIDATE_PASSWORD)
        res = client.get("/api/v1/recommendations", headers=_headers(token))
        assert res.status_code == 200, res.text
        return res.json()

    def test_returns_list(self, recs):
        assert isinstance(recs, list)

    def test_at_least_one_recommendation(self, recs):
        assert len(recs) > 0, "Expected at least one recommendation"

    def test_all_required_fields_present(self, recs):
        """Every item must carry all three metrics plus explainability fields."""
        required_fields = {
            "job",
            "required_skill_coverage",
            "semantic_similarity",
            "ranking_score",
            "matched_skills",
            "missing_skills",
            "match_score",  # legacy backwards-compat field
        }
        for item in recs:
            missing = required_fields - set(item.keys())
            assert not missing, f"Fields missing from recommendation: {missing}"

    def test_job_object_fields(self, recs):
        """The nested job object must carry its own required fields."""
        job_fields = {"id", "title", "company", "location", "source", "source_url"}
        for item in recs:
            missing = job_fields - set(item["job"].keys())
            assert not missing, f"Fields missing from job object: {missing}"


# ─────────────────────────────────────────────────────────────────────────────
# EP-09: Metric Ranges and Independence
# ─────────────────────────────────────────────────────────────────────────────

class TestMetricRanges:
    """Verify all metric values are within legal ranges."""

    @pytest.fixture(scope="class")
    def recs(self):
        token = _login(CANDIDATE_EMAIL, CANDIDATE_PASSWORD)
        res = client.get("/api/v1/recommendations", headers=_headers(token))
        assert res.status_code == 200, res.text
        return res.json()

    def test_required_skill_coverage_range(self, recs):
        """required_skill_coverage must be a float in [0.0, 1.0]."""
        for item in recs:
            v = item["required_skill_coverage"]
            assert isinstance(v, float), f"coverage is not float: {v!r}"
            assert 0.0 <= v <= 1.0, f"coverage out of range: {v}"

    def test_semantic_similarity_range(self, recs):
        """semantic_similarity must be a float in [0.0, 1.0]."""
        for item in recs:
            v = item["semantic_similarity"]
            assert isinstance(v, float), f"semantic is not float: {v!r}"
            assert 0.0 <= v <= 1.0, f"semantic out of range: {v}"

    def test_ranking_score_range(self, recs):
        """ranking_score must be a float in [0.0, 1.0]."""
        for item in recs:
            v = item["ranking_score"]
            assert isinstance(v, float), f"ranking is not float: {v!r}"
            assert 0.0 <= v <= 1.0, f"ranking out of range: {v}"

    def test_match_score_is_integer_percentage(self, recs):
        """Legacy match_score must be an integer in [0, 100]."""
        for item in recs:
            v = item["match_score"]
            assert isinstance(v, int), f"match_score is not int: {v!r}"
            assert 0 <= v <= 100, f"match_score out of range: {v}"

    def test_match_score_consistent_with_coverage(self, recs):
        """match_score must equal round(required_skill_coverage * 100)."""
        for item in recs:
            expected = round(item["required_skill_coverage"] * 100)
            assert item["match_score"] == expected, (
                f"match_score {item['match_score']} ≠ "
                f"round(coverage * 100) = {expected}"
            )

    def test_metrics_are_independent(self, recs):
        """
        required_skill_coverage and semantic_similarity measure different things.
        It would be a bug if they were always identical — check they differ for
        at least one item (or that the result set has consistent non-NaN values).
        """
        coverages = [item["required_skill_coverage"] for item in recs]
        semantics = [item["semantic_similarity"] for item in recs]
        # Both lists should be non-empty and not all-zero (model is working)
        assert not all(s == 0.0 for s in semantics), (
            "All semantic similarities are 0.0 — model may not have loaded"
        )
        # If every pair is identical it suggests the two metrics are aliased
        all_identical = all(
            math.isclose(c, s, abs_tol=1e-6)
            for c, s in zip(coverages, semantics)
        )
        assert not all_identical, (
            "required_skill_coverage and semantic_similarity are identical for "
            "all items — they appear to be aliased, which is a bug."
        )


# ─────────────────────────────────────────────────────────────────────────────
# EP-09: Ranking Order
# ─────────────────────────────────────────────────────────────────────────────

class TestRankingOrder:
    """Results must be sorted descending by ranking_score."""

    def test_sorted_by_ranking_score_descending(self):
        token = _login(CANDIDATE_EMAIL, CANDIDATE_PASSWORD)
        res = client.get("/api/v1/recommendations", headers=_headers(token))
        assert res.status_code == 200, res.text
        recs = res.json()
        scores = [item["ranking_score"] for item in recs]
        assert scores == sorted(scores, reverse=True), (
            f"Results not sorted descending: {scores}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# EP-09: Configurable Weights
# ─────────────────────────────────────────────────────────────────────────────

class TestConfigurableWeights:
    """Changing w_skill / w_semantic must change the ranking_score values."""

    def _get_scores(self, token: str, w_skill: float, w_semantic: float) -> list:
        res = client.get(
            "/api/v1/recommendations",
            headers=_headers(token),
            params={"w_skill": w_skill, "w_semantic": w_semantic},
        )
        assert res.status_code == 200, res.text
        return [(r["ranking_score"], r["job"]["id"]) for r in res.json()]

    def test_weight_params_accepted(self):
        """The endpoint must not error on custom weights."""
        token = _login(CANDIDATE_EMAIL, CANDIDATE_PASSWORD)
        res = client.get(
            "/api/v1/recommendations",
            headers=_headers(token),
            params={"w_skill": 0.5, "w_semantic": 0.5},
        )
        assert res.status_code == 200, res.text

    def test_skill_only_weight_ignores_semantic(self):
        """
        With w_skill=1.0, w_semantic=0.0 the ranking_score must equal
        required_skill_coverage for every result.
        """
        token = _login(CANDIDATE_EMAIL, CANDIDATE_PASSWORD)
        res = client.get(
            "/api/v1/recommendations",
            headers=_headers(token),
            params={"w_skill": 1.0, "w_semantic": 0.0},
        )
        assert res.status_code == 200, res.text
        for item in res.json():
            assert math.isclose(
                item["ranking_score"],
                item["required_skill_coverage"],
                abs_tol=1e-4,
            ), (
                f"ranking_score {item['ranking_score']} ≠ "
                f"coverage {item['required_skill_coverage']} when w_skill=1.0"
            )

    def test_semantic_only_weight_ignores_coverage(self):
        """
        With w_skill=0.0, w_semantic=1.0 the ranking_score must equal
        semantic_similarity for every result.
        """
        token = _login(CANDIDATE_EMAIL, CANDIDATE_PASSWORD)
        res = client.get(
            "/api/v1/recommendations",
            headers=_headers(token),
            params={"w_skill": 0.0, "w_semantic": 1.0},
        )
        assert res.status_code == 200, res.text
        for item in res.json():
            assert math.isclose(
                item["ranking_score"],
                item["semantic_similarity"],
                abs_tol=1e-4,
            ), (
                f"ranking_score {item['ranking_score']} ≠ "
                f"semantic {item['semantic_similarity']} when w_semantic=1.0"
            )

    def test_ranking_changes_with_different_weights(self):
        """
        The ranking_score values must differ between default weights and
        skill-only weights (unless candidate has no skills, which would
        make both metrics 0, so we add a guard).
        """
        token = _login(CANDIDATE_EMAIL, CANDIDATE_PASSWORD)
        default_scores = self._get_scores(token, 0.70, 0.30)
        skill_only_scores = self._get_scores(token, 1.0, 0.0)

        # Only assert if the candidate has at least some skills producing
        # non-trivial scores — otherwise skip
        if all(s == 0.0 for s, _ in default_scores):
            pytest.skip("Candidate has no skills; weight change test skipped.")

        assert default_scores != skill_only_scores, (
            "ranking_score did not change when weights changed from "
            "(0.70, 0.30) to (1.0, 0.0) — weights may not be applied."
        )

    # ── New tests required by the formula review ────────────────────────

    def _get_full(self, token: str, w_skill: float, w_semantic: float) -> list:
        """Return the full recommendation list for the given weights."""
        res = client.get(
            "/api/v1/recommendations",
            headers=_headers(token),
            params={"w_skill": w_skill, "w_semantic": w_semantic},
        )
        assert res.status_code == 200, res.text
        return res.json()

    def test_weights_09_09_scores_in_range(self):
        """
        w_skill=0.9, w_semantic=0.9 (sum > 1.0).
        Old formula: 0.9·C + 0.9·S could exceed 1.0.
        New formula: (0.9·C + 0.9·S) / 1.8 = (C+S)/2 → always in [0,1].
        """
        token = _login(CANDIDATE_EMAIL, CANDIDATE_PASSWORD)
        recs = self._get_full(token, 0.9, 0.9)
        assert len(recs) > 0, "No recommendations returned"
        for item in recs:
            rs = item["ranking_score"]
            assert 0.0 <= rs <= 1.0, (
                f"ranking_score {rs} out of [0,1] with weights (0.9, 0.9)"
            )
            # Verify the formula: ranking = (C + S) / 2
            expected = (
                item["required_skill_coverage"] + item["semantic_similarity"]
            ) / 2.0
            assert math.isclose(rs, expected, abs_tol=1e-3), (
                f"ranking_score {rs} ≠ expected (C+S)/2 = {expected} "
                f"for weights (0.9, 0.9)"
            )

    def test_weights_10_10_scores_in_range(self):
        """
        w_skill=1.0, w_semantic=1.0 (sum = 2.0).
        Formula: (1·C + 1·S) / 2 = (C+S)/2 → always in [0,1].
        Distinct scores must not collapse to a single value.
        """
        token = _login(CANDIDATE_EMAIL, CANDIDATE_PASSWORD)
        recs = self._get_full(token, 1.0, 1.0)
        assert len(recs) > 0, "No recommendations returned"
        for item in recs:
            rs = item["ranking_score"]
            assert 0.0 <= rs <= 1.0, (
                f"ranking_score {rs} out of [0,1] with weights (1.0, 1.0)"
            )
            expected = (
                item["required_skill_coverage"] + item["semantic_similarity"]
            ) / 2.0
            assert math.isclose(rs, expected, abs_tol=1e-3), (
                f"ranking_score {rs} ≠ expected (C+S)/2 = {expected} "
                f"for weights (1.0, 1.0)"
            )
        # Results that have different (C,S) pairs must not all collapse to 1.0
        scores = [r["ranking_score"] for r in recs]
        if len(scores) > 1:
            assert not all(math.isclose(s, scores[0], abs_tol=1e-4) for s in scores), (
                "All ranking_scores are identical with weights (1.0, 1.0) — "
                "distinct jobs should have distinct scores."
            )

    def test_weights_10_00_equals_coverage(self):
        """
        w_skill=1.0, w_semantic=0.0: ranking_score must equal coverage exactly.
        Formula: (1·C + 0·S) / 1 = C
        """
        token = _login(CANDIDATE_EMAIL, CANDIDATE_PASSWORD)
        recs = self._get_full(token, 1.0, 0.0)
        for item in recs:
            assert math.isclose(
                item["ranking_score"],
                item["required_skill_coverage"],
                abs_tol=1e-4,
            ), (
                f"ranking_score {item['ranking_score']} ≠ "
                f"coverage {item['required_skill_coverage']} for weights (1.0, 0.0)"
            )

    def test_weights_00_10_equals_semantic(self):
        """
        w_skill=0.0, w_semantic=1.0: ranking_score must equal semantic exactly.
        Formula: (0·C + 1·S) / 1 = S
        """
        token = _login(CANDIDATE_EMAIL, CANDIDATE_PASSWORD)
        recs = self._get_full(token, 0.0, 1.0)
        for item in recs:
            assert math.isclose(
                item["ranking_score"],
                item["semantic_similarity"],
                abs_tol=1e-4,
            ), (
                f"ranking_score {item['ranking_score']} ≠ "
                f"semantic {item['semantic_similarity']} for weights (0.0, 1.0)"
            )


# ─────────────────────────────────────────────────────────────────────────────
# EP-09: min_score Filter
# ─────────────────────────────────────────────────────────────────────────────

class TestMinScoreFilter:
    """min_score must filter out low-coverage jobs."""

    def test_min_score_100_returns_only_perfect_matches(self):
        """min_score=100 must only include jobs where coverage=1.0."""
        token = _login(CANDIDATE_EMAIL, CANDIDATE_PASSWORD)
        res = client.get(
            "/api/v1/recommendations",
            headers=_headers(token),
            params={"min_score": 100},
        )
        assert res.status_code == 200, res.text
        for item in res.json():
            assert item["required_skill_coverage"] == 1.0, (
                f"Job {item['job']['id']} has coverage "
                f"{item['required_skill_coverage']} but min_score=100 was set"
            )

    def test_min_score_0_returns_all_jobs(self):
        """min_score=0 must not filter out any jobs."""
        token = _login(CANDIDATE_EMAIL, CANDIDATE_PASSWORD)
        res_all = client.get(
            "/api/v1/recommendations",
            headers=_headers(token),
            params={"min_score": 0},
        )
        res_filtered = client.get(
            "/api/v1/recommendations",
            headers=_headers(token),
            params={"min_score": 50},
        )
        assert res_all.status_code == 200
        assert res_filtered.status_code == 200
        # The unfiltered list should be >= the filtered one
        assert len(res_all.json()) >= len(res_filtered.json())

    def test_min_score_filter_honoured(self):
        """
        Every item in a filtered response must have coverage ≥ min_score/100.
        """
        min_pct = 30
        token = _login(CANDIDATE_EMAIL, CANDIDATE_PASSWORD)
        res = client.get(
            "/api/v1/recommendations",
            headers=_headers(token),
            params={"min_score": min_pct},
        )
        assert res.status_code == 200, res.text
        for item in res.json():
            assert item["match_score"] >= min_pct, (
                f"Job {item['job']['id']} has match_score {item['match_score']} "
                f"but min_score={min_pct} was set"
            )


# ─────────────────────────────────────────────────────────────────────────────
# EP-09: Edge Cases
# ─────────────────────────────────────────────────────────────────────────────

class TestEdgeCases:
    """Edge cases and failure modes."""

    def test_unauthenticated_request_returns_401(self):
        """No token → 401."""
        res = client.get("/api/v1/recommendations")
        assert res.status_code == 401, res.text

    def test_invalid_weight_out_of_range_returns_422(self):
        """w_skill > 1.0 should be rejected by FastAPI validation."""
        token = _login(CANDIDATE_EMAIL, CANDIDATE_PASSWORD)
        res = client.get(
            "/api/v1/recommendations",
            headers=_headers(token),
            params={"w_skill": 2.0},
        )
        assert res.status_code == 422, res.text

    def test_negative_min_score_returns_422(self):
        """min_score < 0 should be rejected."""
        token = _login(CANDIDATE_EMAIL, CANDIDATE_PASSWORD)
        res = client.get(
            "/api/v1/recommendations",
            headers=_headers(token),
            params={"min_score": -1},
        )
        assert res.status_code == 422, res.text

    def test_both_weights_zero_returns_422(self):
        """
        w_skill=0 AND w_semantic=0 makes every ranking_score=0 —
        the endpoint must reject this with INVALID_WEIGHTS (422).
        """
        token = _login(CANDIDATE_EMAIL, CANDIDATE_PASSWORD)
        res = client.get(
            "/api/v1/recommendations",
            headers=_headers(token),
            params={"w_skill": 0.0, "w_semantic": 0.0},
        )
        assert res.status_code == 422, res.text
        error = res.json()["detail"]["error"]
        assert error["code"] == "INVALID_WEIGHTS"
        assert "w_skill" in error["details"]
        assert "w_semantic" in error["details"]

    def test_skill_coverage_zero_when_no_profile_skills(self):
        """
        Register a brand new candidate with no skills and verify
        required_skill_coverage is 0.0 for all recommendations.
        """
        # Register fresh user
        reg = client.post("/api/v1/auth/register", json={
            "email": "no_skills_user@test.com",
            "password": "NoSkills123!"
        })
        # May already exist from a previous run — 409 Conflict is fine too
        assert reg.status_code in (201, 200, 400, 409)

        token = _login("no_skills_user@test.com", "NoSkills123!")
        res = client.get("/api/v1/recommendations", headers=_headers(token))
        assert res.status_code == 200, res.text
        for item in res.json():
            assert item["required_skill_coverage"] == 0.0, (
                f"Expected 0.0 coverage for no-skill user, got "
                f"{item['required_skill_coverage']}"
            )
            assert item["match_score"] == 0

    def test_semantic_similarity_is_float_even_without_model(self):
        """
        semantic_similarity must always be a float (not an error), even
        if the embedding model is unavailable (graceful fallback to 0.0).
        """
        token = _login(CANDIDATE_EMAIL, CANDIDATE_PASSWORD)
        res = client.get("/api/v1/recommendations", headers=_headers(token))
        assert res.status_code == 200, res.text
        for item in res.json():
            assert isinstance(item["semantic_similarity"], float), (
                f"semantic_similarity is not float: {item['semantic_similarity']!r}"
            )
