"""
Multi-Dimensional Scorer — two-pass scoring with objective signals + LLM interpretation.

SCORING ARCHITECTURE:
1. Pass 1: Objective Signal Detection — Keywords and patterns (fast, verifiable)
2. Pass 2: LLM Interpretation — Contextual reasoning using gemini-2.5-pro (powerful)

Each company gets scored on:
1. Offer Power (Hormozi Value Equation: Dream Outcome, Likelihood, Time, Effort)
2. Sales Ability (Inbound Lead Gen, Outbound Lead Gen, Conversion)
3. Tech Moat (Patents, Data Moat, Network Effects, Switching Costs, etc.)
4. Founder Strength (Prior Exits, Domain Expertise, Technical Depth, Network)

GROUNDING RULE: Every score MUST have:
- evidence_quote: Exact text from the source
- source_url: Where the evidence came from
- signals_detected: Objective signals found in the text
- If no evidence exists, score = None and evidence = "N/A"

This prevents Gemini from inventing scores or founder backgrounds.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from models import SearchResult, DimensionScore, ScoredCompany
from config import SCORING_DIMENSIONS
from llm_client import call_gemini, parse_json_response
from tracing import create_trace
from scoring_criteria import (
    ALL_SCORING_DIMENSIONS,
    ScoringDimension,
    SubComponent,
    SignalDefinition,
    get_all_signals_for_dimension,
)
from grounding import validate_claim, find_exact_match

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pass 1: Objective Signal Detection
# ---------------------------------------------------------------------------

@dataclass
class SignalMatch:
    """A detected signal match in company text."""
    signal_name: str
    keyword_matched: str
    context: str  # Surrounding text for evidence
    weight: float
    inverse: bool


def detect_signals_in_text(
    text: str,
    signals: List[SignalDefinition],
) -> List[SignalMatch]:
    """
    Detect objective signals in company text using keyword matching.
    
    This is Pass 1 — fast, verifiable, no LLM required.
    Returns list of SignalMatch objects with context for evidence.
    """
    if not text:
        return []
    
    text_lower = text.lower()
    matches = []
    
    for signal in signals:
        for keyword in signal.keywords:
            keyword_lower = keyword.lower()
            # Find all occurrences
            idx = text_lower.find(keyword_lower)
            if idx != -1:
                # Extract context (50 chars before and after)
                start = max(0, idx - 50)
                end = min(len(text), idx + len(keyword) + 50)
                context = text[start:end]
                
                matches.append(SignalMatch(
                    signal_name=signal.name,
                    keyword_matched=keyword,
                    context=f"...{context}...",
                    weight=signal.weight,
                    inverse=signal.inverse,
                ))
                break  # Only count each signal once per keyword set
    
    return matches


def calculate_signal_score(
    matches: List[SignalMatch],
    max_score: float = 5.0,
) -> Tuple[float, List[str]]:
    """
    Calculate a score based on detected signals.
    
    Returns (score, list of signal names detected).
    Inverse signals reduce the score.
    """
    if not matches:
        return 0.0, []
    
    positive_weight = sum(m.weight for m in matches if not m.inverse)
    negative_weight = sum(m.weight for m in matches if m.inverse)
    
    # Normalize: more signals = higher score, but cap at max
    # Each signal contributes ~0.5-1.0 points
    raw_score = (positive_weight * 0.8) - (negative_weight * 0.5)
    
    # Clamp to 1.0 - 5.0 range
    score = max(1.0, min(max_score, 1.0 + raw_score))
    
    signal_names = [m.signal_name for m in matches]
    return score, signal_names


def detect_dimension_signals(
    company: SearchResult,
    dimension_key: str,
) -> Dict[str, List[SignalMatch]]:
    """
    Detect all signals for a dimension across company data.
    
    Returns dict mapping sub-component name to list of matches.
    """
    dimension = ALL_SCORING_DIMENSIONS.get(dimension_key)
    if not dimension:
        return {}
    
    # Combine all text sources for searching
    company_text = " ".join(filter(None, [
        company.description or "",
        company.source_snippet or "",
        " ".join(company.founders) if company.founders else "",
        company.funding_stage or "",
        company.sector or "",
    ]))
    
    results = {}
    for sub in dimension.sub_components:
        matches = detect_signals_in_text(company_text, sub.signals)
        results[sub.name] = matches
    
    return results


# ---------------------------------------------------------------------------
# Pass 2: LLM Interpretation (using gemini-2.5-pro)
# ---------------------------------------------------------------------------

def score_company(
    search_result: SearchResult,
    dimensions: List[str] = None,
    weights: Dict[str, float] = None,
    custom_criteria: Dict[str, str] = None,
) -> ScoredCompany:
    """
    Score a single company on all dimensions.

    Args:
        search_result:    The company to score (from Tavily search)
        dimensions:       Which dimensions to score (default: all 4)
        weights:          User-defined weights for each dimension
        custom_criteria:  User-defined criteria descriptions for each dimension

    Returns:
        ScoredCompany with all dimension scores + AI summary.
    """
    dims_to_score = dimensions or list(SCORING_DIMENSIONS.keys())
    custom_criteria = custom_criteria or {}

    # Create Langfuse trace for this scoring operation
    trace = create_trace(
        name="score_company",
        input_data={
            "company": search_result.name,
            "source_url": search_result.source_url,
            "dimensions": dims_to_score,
        },
        metadata={"company": search_result.name},
    )

    scored = ScoredCompany(search_result=search_result)

    try:
        # Score each dimension
        for dim in dims_to_score:
            dim_config = SCORING_DIMENSIONS.get(dim)
            if not dim_config:
                continue

            # Use custom criteria if provided, otherwise use default
            criteria_override = custom_criteria.get(dim)
            score = _score_dimension(
                company=search_result,
                dimension=dim,
                dim_config=dim_config,
                criteria_override=criteria_override,
                trace=trace,
            )
            scored.scores[dim] = score

        # Estimate CAC and LTV (for 2x2 matrix axes)
        cac_ltv = _estimate_cac_ltv(search_result, trace=trace)
        scored.expected_cac = cac_ltv.get("cac")
        scored.expected_ltv = cac_ltv.get("ltv")

        # Generate AI summary ("why this is a fit")
        scored.ai_summary = _generate_fit_summary(scored, trace=trace)

        # Log to Langfuse
        if trace is not None:
            try:
                trace.update(output={
                    "company": search_result.name,
                    "scores": {k: v.score for k, v in scored.scores.items()},
                    "expected_cac": scored.expected_cac,
                    "expected_ltv": scored.expected_ltv,
                })
                trace.end()
            except Exception:
                pass

    except Exception as e:
        logger.error(f"Scoring failed for {search_result.name}: {e}")
        if trace is not None:
            try:
                trace.update(output={"error": str(e)}, level="ERROR")
                trace.end()
            except Exception:
                pass

    return scored


def _score_dimension(
    company: SearchResult,
    dimension: str,
    dim_config: dict,
    criteria_override: str = None,
    trace=None,
) -> DimensionScore:
    """
    Two-pass scoring for a company on ONE dimension.
    
    Pass 1: Detect objective signals (keywords) — fast, verifiable
    Pass 2: LLM interpretation using gemini-2.5-pro — contextual reasoning
    
    The final score combines both passes for robustness.
    Returns a DimensionScore with evidence and signals attached.
    """
    # --- PASS 1: Objective Signal Detection ---
    signal_results = detect_dimension_signals(company, dimension)
    
    # Flatten all matches and calculate signal-based score
    all_matches = []
    sub_scores = {}
    for sub_name, matches in signal_results.items():
        all_matches.extend(matches)
        if matches:
            score, signals = calculate_signal_score(matches)
            sub_scores[sub_name] = {"score": score, "signals": signals}
    
    # Build signal summary for LLM context
    signal_summary = ""
    if all_matches:
        signal_summary = "\n\nOBJECTIVE SIGNALS DETECTED:\n"
        for sub_name, data in sub_scores.items():
            signal_summary += f"- {sub_name}: {', '.join(data['signals'])} (signal score: {data['score']:.1f})\n"
    
    # Get sub-component details for the prompt
    dimension_def = ALL_SCORING_DIMENSIONS.get(dimension)
    sub_component_text = ""
    if dimension_def:
        sub_component_text = "\n\nSUB-COMPONENTS TO EVALUATE:\n"
        for sub in dimension_def.sub_components:
            sub_component_text += f"- {sub.name} (weight: {sub.weight:.0%}): {sub.description}\n"
    
    # --- PASS 2: LLM Interpretation ---
    # Use custom criteria if provided, otherwise use default from config
    scoring_guidance = criteria_override if criteria_override else dim_config['prompt_guidance']
    
    # Build website context hint
    website_hint = ""
    if company.website and company.website != "Not Found":
        website_hint = f"""
IMPORTANT - COMPANY WEBSITE: {company.website}
- The company website often contains CASE STUDIES, customer testimonials, and product details.
- Look for evidence of: customer success stories, ROI claims, implementation timelines.
- Case studies are strong evidence for Offer Power and Sales Ability dimensions.
"""
    
    prompt = f"""Score this company on the "{dim_config['label']}" dimension using TWO-PASS analysis.

COMPANY DATA:
- Name: {company.name}
- Description: {company.description}
- Website: {company.website}
- Location: {company.location}
- Sector: {company.sector}
- Founders: {', '.join(company.founders) if company.founders else 'Not Found'}
- Funding Stage: {company.funding_stage}
- Funding Amount: {company.funding_amount}
- Source URL: {company.source_url}
- Source Snippet: {company.source_snippet}
{website_hint}
DIMENSION: {dim_config['label']}
DESCRIPTION: {dim_config['description']}
{sub_component_text}
{signal_summary}

SCORING GUIDANCE (Analyst-defined criteria):
{scoring_guidance}

RULES:
1. Score from 1.0 (lowest) to 5.0 (highest) using DECIMAL values (e.g., 2.3, 3.7, 4.5).
2. Consider the objective signals detected above as evidence.
3. Use the full range with decimals to differentiate companies precisely.
4. You MUST provide an exact quote from the source data as evidence.
5. If there is NO evidence in the source data for this dimension, return score: null.
6. Do NOT use your training data — only use the COMPANY DATA above.
7. Do NOT guess or invent information.
8. Break down your reasoning by sub-component if possible.
9. If company website is available, consider what case studies/testimonials might indicate.

Return JSON:
{{
  "score": 1.0-5.0 (decimal) or null,
  "sub_scores": {{"sub_component_name": score, ...}},
  "signals_detected": ["signal1", "signal2", ...],
  "evidence_quote": "Exact quote from source or 'N/A'",
  "source_url": "{company.source_url}",
  "reasoning": "Brief explanation referencing sub-components and signals"
}}"""

    try:
        # Use PRO model for scoring (more powerful reasoning)
        response = call_gemini(
            prompt=prompt,
            trace=trace,
            span_name=f"score_{dimension}",
            metadata={"company": company.name, "dimension": dimension},
            use_pro_model=True,  # Use gemini-2.5-pro for complex scoring
        )

        data = parse_json_response(response)
        
        # Combine LLM signals with detected signals
        llm_signals = data.get("signals_detected", [])
        detected_signal_names = [m.signal_name for m in all_matches]
        all_signals = list(set(llm_signals + detected_signal_names))
        
        # ABSOLUTE GROUNDING: Validate evidence_quote exists in source
        evidence_quote = data.get("evidence_quote", "N/A")
        source_text = company.source_snippet or ""
        if hasattr(company, 'raw_source_text') and company.raw_source_text:
            source_text = company.raw_source_text
        
        # Deterministic check: does the evidence quote actually appear in source?
        grounded_evidence = None
        is_grounded = False
        if evidence_quote and evidence_quote != "N/A":
            ev = validate_claim(
                claim=evidence_quote,
                claim_field=f"evidence_{dimension}",
                source_text=source_text,
                source_url=company.source_url,
            )
            grounded_evidence = ev.to_dict()
            is_grounded = ev.is_grounded
            
            if not is_grounded:
                logger.warning(f"EVIDENCE UNGROUNDED for {company.name}/{dimension}: quote not found in source")

        return DimensionScore(
            dimension=dimension,
            score=data.get("score"),  # Can be None if no evidence
            evidence_quote=evidence_quote,
            source_url=data.get("source_url", company.source_url),
            reasoning=data.get("reasoning", ""),
            signals_detected=all_signals,
            sub_scores=data.get("sub_scores", {}),
            grounded_evidence=grounded_evidence,
            is_grounded=is_grounded,
        )

    except Exception as e:
        logger.error(f"Dimension scoring failed ({dimension}): {e}")
        return DimensionScore(
            dimension=dimension,
            score=None,
            evidence_quote="N/A",
            source_url=company.source_url,
            reasoning=f"Scoring failed: {str(e)}",
        )


def _estimate_cac_ltv(company: SearchResult, trace=None) -> Dict[str, Optional[float]]:
    """
    Estimate CAC and LTV on a 1-5 scale based on available data.

    These are rough estimates for the 2x2 matrix visualization.
    If no evidence exists, returns None (not plotted on that axis).
    """
    prompt = f"""Estimate Customer Acquisition Cost (CAC) and Lifetime Value (LTV) for this company.

COMPANY DATA:
- Name: {company.name}
- Description: {company.description}
- Sector: {company.sector}
- Funding Stage: {company.funding_stage}
- Source Snippet: {company.source_snippet}

TASK: Based on the business model implied by the description, estimate:
1. Expected CAC (1.0 = very low, 5.0 = very high) - use DECIMAL values
2. Expected LTV (1.0 = very low, 5.0 = very high) - use DECIMAL values

Consider:
- B2B typically has higher CAC but higher LTV
- B2C/consumer typically has lower CAC but lower LTV
- SaaS has recurring revenue (higher LTV)
- Marketplace models have network effects (lower CAC over time)

RULES:
1. Use DECIMAL values (e.g., 2.3, 3.7, 4.2) to differentiate companies precisely.
2. If you cannot determine the business model, return null for both.
3. Provide brief reasoning based on the source data.

Return JSON:
{{
  "cac": 1.0-5.0 (decimal) or null,
  "ltv": 1.0-5.0 (decimal) or null,
  "reasoning": "Brief explanation"
}}"""

    try:
        response = call_gemini(
            prompt=prompt,
            trace=trace,
            span_name="estimate_cac_ltv",
            metadata={"company": company.name},
        )

        data = parse_json_response(response)
        return {
            "cac": data.get("cac"),
            "ltv": data.get("ltv"),
        }

    except Exception as e:
        logger.error(f"CAC/LTV estimation failed: {e}")
        return {"cac": None, "ltv": None}


def _generate_fit_summary(scored: ScoredCompany, trace=None) -> str:
    """
    Generate a one-paragraph "why this is a fit" summary.

    Uses all the scores and evidence to create a compelling summary
    for the final report.
    """
    company = scored.search_result
    scores_text = "\n".join(
        f"- {SCORING_DIMENSIONS[k]['label']}: {v.score}/5 — {v.reasoning}"
        for k, v in scored.scores.items()
        if v.score is not None
    )

    prompt = f"""Write a brief "Why This Is A Fit" summary for an investor report.

COMPANY: {company.name}
DESCRIPTION: {company.description}
LOCATION: {company.location}
SECTOR: {company.sector}

SCORES:
{scores_text}

TASK: Write 2-3 sentences explaining why this company is worth considering.
Focus on the strongest scores and most compelling evidence.
Be specific — reference actual data points, not generic statements.

If most scores are N/A or low, be honest about the limited data available.

Return ONLY the summary text, no JSON."""

    try:
        response = call_gemini(
            prompt=prompt,
            trace=trace,
            span_name="generate_fit_summary",
            metadata={"company": company.name},
        )
        return response.strip()

    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        return "Summary unavailable due to limited data."


def score_companies(
    search_results: List[SearchResult],
    dimensions: List[str] = None,
    weights: Dict[str, float] = None,
    custom_criteria: Dict[str, str] = None,
) -> List[ScoredCompany]:
    """
    Score multiple companies. Convenience wrapper around score_company().

    Args:
        search_results:  Companies to score
        dimensions:      Which dimensions to score
        weights:         User-defined weights
        custom_criteria: User-defined criteria descriptions

    Returns list of ScoredCompany objects, sorted by average score (descending).
    """
    scored_list = []

    for result in search_results:
        logger.info(f"Scoring: {result.name}")
        scored = score_company(result, dimensions, weights, custom_criteria)
        scored_list.append(scored)

    # Sort by average score (companies with more N/A scores rank lower)
    def avg_score(sc: ScoredCompany) -> float:
        valid_scores = [v.score for v in sc.scores.values() if v.score is not None]
        return sum(valid_scores) / len(valid_scores) if valid_scores else 0

    scored_list.sort(key=avg_score, reverse=True)

    return scored_list
