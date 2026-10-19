"""
backend/app/services/matching_engine.py
========================================
JobMatch Dual-Metric Recommendation Engine
-------------------------------------------

Two independent metrics are computed and NEVER confused:

  Metric 1 – required_skill_coverage  (primary, fully transparent)
  ─────────────────────────────────────────────────────────────────
  Definition : |candidate_skills ∩ job_required_skills|
               ─────────────────────────────────────────
               |job_required_skills|

  Range      : 0.0 (no overlap) → 1.0 (all required skills matched)
  Strength   : deterministic, instantly explainable, no model needed.
  Used for   : "You have X of Y required skills" UI label.

  Metric 2 – semantic_similarity  (secondary, AI-powered)
  ─────────────────────────────────────────────────────────
  Model      : paraphrase-multilingual-MiniLM-L12-v2
               (sentence-transformers, 278 M parameters)
  Why this model?
    • Trained on 50+ languages including Unicode-heavy scripts.
    • Khmer (ភាសាខ្មែរ) is romanised in job postings but full
      Unicode Khmer also appears in descriptions. The model's
      multilingual tokeniser handles both without pre-processing.
    • 384-dimensional embeddings are fast to compute even on CPU.
    • Sentence Transformers cosine-similarity scores on English
      text closely match human relevance judgements (STSB, SICK).
  Candidate text : concatenation of skill names + preferred_role
                   + education (whatever is stored in the profile).
  Job text       : job title + company + description.
  Metric         : cosine similarity between the two unit vectors.
  Range          : 0.0 → 1.0

  Metric 3 – ranking_score  (configurable weighted combination)
  ──────────────────────────────────────────────────────────────
  Formula : ranking_score = w_skill · required_skill_coverage
                           + w_semantic · semantic_similarity

  Defaults: w_skill=0.70, w_semantic=0.30
  Rationale: skill coverage is the more reliable signal because job
  descriptions in Cambodia often list requirements precisely. The
  semantic score catches conceptually related roles where the exact
  skill keywords do not match (e.g. "React" vs "React.js frontend").
  The weights are not claimed to be optimal — they are a reasonable
  starting point. Callers may tune them via query parameters.

NOTE: The embedding model is loaded once at module import time and
      cached globally so repeated API calls do not reload it.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine
from sqlalchemy.orm import Session

from app.models.models import JobListing, Profile, ProfileSkill, Skill
from app.api.jobs import format_job_item

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Embedding model — loaded once, reused for every request
# ─────────────────────────────────────────────────────────────────────────────

_EMBEDDING_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
_embedding_model = None  # loaded lazily on first call


def _get_embedding_model():
    """
    Returns the shared SentenceTransformer model instance.
    Loaded lazily so the server starts quickly even without GPU.
    Falls back gracefully if sentence-transformers is not installed.
    """
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model

    try:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading embedding model: %s …", _EMBEDDING_MODEL_NAME)
        _embedding_model = SentenceTransformer(_EMBEDDING_MODEL_NAME)
        logger.info("Embedding model loaded successfully.")
    except Exception as exc:
        logger.warning(
            "Could not load sentence-transformers model (%s). "
            "Semantic similarity will default to 0.0. Error: %s",
            _EMBEDDING_MODEL_NAME, exc
        )
        _embedding_model = None

    return _embedding_model


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _compute_skill_coverage(
    candidate_skills: set[str],
    job_skills: set[str],
) -> float:
    """
    Metric 1 — required_skill_coverage.

    Returns the fraction of the job's required skills that the candidate
    already possesses.  Returns 0.0 when the job has no listed skills
    (so an unlisted-skills job never unfairly tops the ranking).
    """
    if not job_skills:
        return 0.0
    matched = candidate_skills & job_skills
    return len(matched) / len(job_skills)


def _embed(model, text: str) -> np.ndarray:
    """Produce a unit-norm embedding vector for *text* using *model*."""
    vec = model.encode(text, normalize_embeddings=True)
    return vec.astype(np.float32)


def _compute_semantic_similarity(
    candidate_text: str,
    job_text: str,
) -> float:
    """
    Metric 2 — semantic_similarity (normalised to [0, 1]).

    Step 1 — cosine similarity
    --------------------------
    Encodes both texts with paraphrase-multilingual-MiniLM-L12-v2.
    With normalize_embeddings=True the dot product equals cosine similarity,
    which is in the range [-1, 1].

    Step 2 — linear normalisation to [0, 1]
    ----------------------------------------
    We map the raw cosine value using:

        S_semantic = (S_cosine + 1) / 2

    This is a standard scoring convention that maps:
        -1  →  0.0   (maximally opposite meaning)
         0  →  0.5   (orthogonal / unrelated)
        +1  →  1.0   (identical meaning)

    Important: this is a monotone transformation that preserves ranking
    order. It does NOT represent a probability of being hired.

    Returns 0.0 if the model is unavailable, either text is empty,
    or any intermediate value is non-finite (NaN / ±inf).
    """
    model = _get_embedding_model()
    if model is None or not candidate_text.strip() or not job_text.strip():
        return 0.0

    try:
        emb_candidate = _embed(model, candidate_text)
        emb_job = _embed(model, job_text)

        # Guard: reject NaN/inf vectors that could corrupt the dot product
        if not (np.all(np.isfinite(emb_candidate)) and np.all(np.isfinite(emb_job))):
            logger.warning("Non-finite embedding vector detected; returning 0.0")
            return 0.0

        # Both vectors are unit-norm → dot product = cosine ∈ [-1, 1]
        raw_cosine = float(np.dot(emb_candidate, emb_job))

        # Guard against the (unlikely) case that dot product itself is non-finite
        if not math.isfinite(raw_cosine):
            logger.warning("Non-finite cosine similarity (%s); returning 0.0", raw_cosine)
            return 0.0

        # Normalise: map [-1, 1] → [0, 1]
        normalised = (raw_cosine + 1.0) / 2.0

        # Final range check (floating-point arithmetic should not violate this,
        # but we verify explicitly rather than silently clamping)
        if not (0.0 <= normalised <= 1.0):
            logger.warning(
                "Normalised semantic score out of range (%s); clamping.", normalised
            )
            normalised = max(0.0, min(1.0, normalised))

        return normalised

    except Exception as exc:
        logger.warning("Semantic similarity computation failed: %s", exc)
        return 0.0


def _build_candidate_text(profile: Optional[Profile], skills: List[str]) -> str:
    """
    Builds a plain-text representation of the candidate for embedding.
    Combines skill names, preferred role, and education level.
    """
    parts: List[str] = []
    if skills:
        parts.append("Skills: " + ", ".join(skills))
    if profile:
        if profile.preferred_role:
            parts.append("Role: " + profile.preferred_role)
        if profile.education:
            parts.append("Education: " + profile.education)
    return ". ".join(parts)


def _build_job_text(job: JobListing) -> str:
    """
    Builds a plain-text representation of the job for embedding.
    Combines title, company, and description.
    """
    parts: List[str] = [job.title, job.company]
    if job.description:
        parts.append(job.description)
    return ". ".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Main public function
# ─────────────────────────────────────────────────────────────────────────────

def compute_ai_recommendations(
    user_id: int,
    db: Session,
    min_score: int = 0,
    w_skill: float = 0.70,
    w_semantic: float = 0.30,
) -> List[Dict[str, Any]]:
    """
    Computes job recommendations for *user_id* using two independent metrics.

    Parameters
    ----------
    user_id     : ID of the authenticated candidate.
    db          : Active SQLAlchemy database session.
    min_score   : Minimum required_skill_coverage × 100 to include a job
                  (0 = include all jobs, 80 = only jobs where candidate
                   covers ≥ 80 % of required skills).
    w_skill     : Weight for required_skill_coverage in ranking_score.
                  Must be between 0.0 and 1.0. Default 0.70.
    w_semantic  : Weight for semantic_similarity in ranking_score.
                  Must be between 0.0 and 1.0. Default 0.30.

    Returns
    -------
    List of recommendation dicts, each containing:
      - job                    : serialised JobItemResponse
      - required_skill_coverage: float 0.0–1.0
      - semantic_similarity    : float 0.0–1.0
      - ranking_score          : float 0.0–1.0 (weighted combination)
      - matched_skills         : list[str]  — skills the candidate has
      - missing_skills         : list[str]  — skills the candidate lacks
      - match_score            : int  0–100  (legacy, = coverage × 100)

    Ranking formula  (normalised weighted average)
    ------------------------------------------------
    Both input scores are in [0, 1] before combination:
      • required_skill_coverage  : fraction, naturally in [0, 1]
      • semantic_similarity      : raw cosine normalised via (cosine+1)/2

    The combined score is a proper weighted average:

        ranking_score = (w_skill · C + w_semantic · S) / (w_skill + w_semantic)

    This is mathematically guaranteed to produce a value in [0, 1] whenever
    both C and S are in [0, 1] and at least one weight is positive.
    No clamping is needed or used for the combined score.

    Clamping is only used as a last-resort safety net inside
    _compute_semantic_similarity to catch floating-point edge cases in the
    normalisation step — it is not relied on to fix incorrect arithmetic.

    The default weights (0.70, 0.30) are a reasonable starting point;
    they have NOT been tuned against labelled Cambodian job-matching data.
    """
    # ── 1. Fetch candidate's skills ──────────────────────────────────────
    candidate_skill_rows = (
        db.query(Skill.name)
        .join(ProfileSkill, ProfileSkill.skill_id == Skill.id)
        .filter(ProfileSkill.profile.has(user_id=user_id))
        .all()
    )
    candidate_skill_names: List[str] = [r[0] for r in candidate_skill_rows]
    candidate_skills_lower: set[str] = {s.strip().lower() for s in candidate_skill_names}

    # ── 2. Fetch candidate's profile (for semantic text) ─────────────────
    candidate_profile: Optional[Profile] = (
        db.query(Profile).filter(Profile.user_id == user_id).first()
    )
    candidate_text = _build_candidate_text(candidate_profile, candidate_skill_names)

    # ── 3. Fetch all active job listings ─────────────────────────────────
    active_jobs: List[JobListing] = (
        db.query(JobListing).filter(JobListing.is_active == True).all()
    )
    if not active_jobs:
        return []

    # ── 4. Score each job ────────────────────────────────────────────────
    results: List[Dict[str, Any]] = []

    for job in active_jobs:
        # Raw job skill strings (original casing for display)
        job_skill_names_raw: List[str] = [
            js.skill.name for js in job.skills if js.skill
        ]
        job_skills_lower: set[str] = {s.strip().lower() for s in job_skill_names_raw}

        # ── Metric 1: required skill coverage ────────────────────────────
        coverage = _compute_skill_coverage(candidate_skills_lower, job_skills_lower)

        # Apply min_score filter (min_score is in % units, coverage is 0–1)
        if int(round(coverage * 100)) < min_score:
            continue

        # ── Metric 2: semantic similarity ────────────────────────────────
        job_text = _build_job_text(job)
        semantic = _compute_semantic_similarity(candidate_text, job_text)

        # ── Metric 3: ranking score (normalised weighted average) ──────
        # Formula: (w_skill·C + w_semantic·S) / (w_skill + w_semantic)
        # Denominator is guaranteed > 0 by _validate_weights() in the endpoint.
        # Both C and S are in [0,1], so the result is in [0,1] by the
        # convex-combination property — no clamping required.
        weight_sum = w_skill + w_semantic
        ranking = (w_skill * coverage + w_semantic * semantic) / weight_sum

        # Safety net: detect non-finite results (should never occur given the
        # validated inputs, but we handle it explicitly rather than silently
        # producing a NaN that would corrupt the sort)
        if not math.isfinite(ranking):
            logger.warning(
                "Non-finite ranking_score for job %s (coverage=%s, semantic=%s, "
                "w_skill=%s, w_semantic=%s); defaulting to 0.0",
                job.id, coverage, semantic, w_skill, w_semantic,
            )
            ranking = 0.0

        # ── Explainability breakdown ──────────────────────────────────────
        matched = [s for s in job_skill_names_raw if s.strip().lower() in candidate_skills_lower]
        missing = [s for s in job_skill_names_raw if s.strip().lower() not in candidate_skills_lower]

        results.append({
            "job": format_job_item(job),
            # ── three clearly named, distinct metrics ──
            "required_skill_coverage": round(coverage, 4),
            "semantic_similarity": round(semantic, 4),
            "ranking_score": round(ranking, 4),
            # ── explainability ──
            "matched_skills": matched,
            "missing_skills": missing,
            # ── legacy field (backwards compat with mobile app) ──
            "match_score": int(round(coverage * 100)),
        })

    # ── 5. Sort by ranking_score descending ──────────────────────────────
    results.sort(key=lambda x: x["ranking_score"], reverse=True)

    return results
