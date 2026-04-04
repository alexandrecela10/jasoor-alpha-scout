"""
Reviewer Agent — validates research quality and prevents hallucinations.

This agent performs two key reviews:
1. SEED VALIDATION: Verifies that we correctly identified the seed company's
   problem statement, tech edge, target clients, etc.
2. SIMILARITY VALIDATION: Checks that found companies actually exist and
   match the similarity criteria.

Every review produces structured evidence that goes into the Appendix tab.
"""

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field

from models import SearchResult, ScoredCompany
from config import PORTFOLIO_COMPANIES, SCORING_DIMENSIONS
from llm_client import call_gemini, parse_json_response
from tracing import create_trace
from grounding import validate_website_domain, validate_company_name, find_exact_match

logger = logging.getLogger(__name__)


@dataclass
class ValidationItem:
    """One validation check result."""
    field: str                      # What was validated (e.g., "tech_edge")
    status: str                     # "verified", "unverified", "incorrect"
    original_value: str             # What we claimed
    evidence: str                   # Evidence supporting/refuting the claim
    source_url: str                 # Where evidence came from
    confidence: float               # 0.0 to 1.0

    def to_dict(self) -> Dict:
        return {
            "field": self.field,
            "status": self.status,
            "original_value": self.original_value,
            "evidence": self.evidence,
            "source_url": self.source_url,
            "confidence": self.confidence,
        }


@dataclass
class CompanyValidation:
    """Validation result for one company."""
    company_name: str
    exists: bool                    # Does this company actually exist?
    exists_evidence: str            # Proof of existence
    exists_source: str              # URL proving existence
    similarity_valid: bool          # Does it match the criteria?
    similarity_reason: str          # Why/why not similar
    field_validations: List[ValidationItem] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "company_name": self.company_name,
            "exists": self.exists,
            "exists_evidence": self.exists_evidence,
            "exists_source": self.exists_source,
            "similarity_valid": self.similarity_valid,
            "similarity_reason": self.similarity_reason,
            "field_validations": [v.to_dict() for v in self.field_validations],
        }


@dataclass
class ScoringExplanation:
    """Explains how a score was calculated."""
    dimension: str
    score: Optional[int]
    methodology: str                # How the score was determined
    evidence_used: str              # What evidence was considered
    source_url: str
    grounding_check: str            # "grounded" or "ungrounded"

    def to_dict(self) -> Dict:
        return {
            "dimension": self.dimension,
            "score": self.score,
            "methodology": self.methodology,
            "evidence_used": self.evidence_used,
            "source_url": self.source_url,
            "grounding_check": self.grounding_check,
        }


@dataclass
class ReviewResult:
    """Complete review output for the Appendix."""
    seed_company: str
    seed_validations: List[ValidationItem] = field(default_factory=list)
    company_validations: List[CompanyValidation] = field(default_factory=list)
    scoring_explanations: Dict[str, List[ScoringExplanation]] = field(default_factory=dict)
    overall_confidence: float = 0.0
    hallucination_flags: List[str] = field(default_factory=list)
    review_summary: str = ""

    def to_dict(self) -> Dict:
        return {
            "seed_company": self.seed_company,
            "seed_validations": [v.to_dict() for v in self.seed_validations],
            "company_validations": [v.to_dict() for v in self.company_validations],
            "scoring_explanations": {
                k: [s.to_dict() for s in v] 
                for k, v in self.scoring_explanations.items()
            },
            "overall_confidence": self.overall_confidence,
            "hallucination_flags": self.hallucination_flags,
            "review_summary": self.review_summary,
        }


def review_seed_company(seed_company: str) -> List[ValidationItem]:
    """
    Validate that our stored seed company profile is accurate.
    
    Cross-references our config data against what Gemini knows
    (with grounding — it must cite sources or say "unverified").
    """
    trace = create_trace(
        name="review_seed_company",
        input_data={"seed_company": seed_company},
        metadata={"seed_company": seed_company},
    )

    seed_data = PORTFOLIO_COMPANIES.get(seed_company, {})
    
    prompt = f"""You are a fact-checker validating company information.

COMPANY TO VALIDATE: {seed_company}

OUR CLAIMED PROFILE:
- Description: {seed_data.get('description', 'N/A')}
- Tech Edge: {seed_data.get('tech_edge', 'N/A')}
- Sector: {seed_data.get('sector', 'N/A')}
- Location: {seed_data.get('location', 'N/A')}
- Website: {seed_data.get('website', 'N/A')}

TASK: Validate each field. For each field, determine:
1. Is this claim VERIFIED (matches known facts)?
2. Is this claim UNVERIFIED (cannot confirm either way)?
3. Is this claim INCORRECT (contradicts known facts)?

RULES:
1. You MUST provide evidence for each validation.
2. If you cannot verify something, say "unverified" with reason.
3. Do NOT make up evidence — if unsure, say so.

Return JSON:
{{
  "validations": [
    {{
      "field": "description",
      "status": "verified" | "unverified" | "incorrect",
      "original_value": "what we claimed",
      "evidence": "evidence supporting or refuting this",
      "source_url": "URL or 'general knowledge' or 'unverified'",
      "confidence": 0.0 to 1.0
    }}
  ]
}}"""

    try:
        response = call_gemini(
            prompt=prompt,
            trace=trace,
            span_name="validate_seed",
            metadata={"seed_company": seed_company},
        )

        data = parse_json_response(response)
        validations = []

        for v in data.get("validations", []):
            validations.append(ValidationItem(
                field=v.get("field", "unknown"),
                status=v.get("status", "unverified"),
                original_value=v.get("original_value", ""),
                evidence=v.get("evidence", "No evidence provided"),
                source_url=v.get("source_url", "unverified"),
                confidence=float(v.get("confidence", 0.5)),
            ))

        if trace:
            trace.update(output={"validations_count": len(validations)})
            trace.end()

        return validations

    except Exception as e:
        logger.error(f"Seed validation failed: {e}")
        if trace:
            trace.update(output={"error": str(e)}, level="ERROR")
            trace.end()
        return []


def validate_website_deterministic(result: SearchResult) -> Dict:
    """
    Deterministically validate a company's website using grounding module.
    
    This is 100% code-based — no LLM calls.
    Checks:
    1. Domain contains company name
    2. Website URL appears in source text
    3. Domain is not a generic aggregator site
    
    Returns dict with validation results.
    """
    website_evidence = validate_website_domain(
        claimed_website=result.website,
        company_name=result.name,
        source_text=result.raw_source_text or result.source_snippet,
        source_url=result.source_url,
    )
    
    return {
        "website": result.website,
        "is_valid": website_evidence.is_grounded,
        "confidence": website_evidence.confidence,
        "validation_method": website_evidence.validation_method,
        "matched_text": website_evidence.matched_text,
        "proof": website_evidence.get_proof_snippet(),
    }


def validate_company_deterministic(result: SearchResult) -> Dict:
    """
    Deterministically validate a company's existence using grounding module.
    
    This is 100% code-based — no LLM calls.
    Checks if company name appears in the source text.
    
    Returns dict with validation results.
    """
    name_evidence = validate_company_name(
        company_name=result.name,
        source_text=result.raw_source_text or result.source_snippet,
        source_url=result.source_url,
    )
    
    return {
        "company_name": result.name,
        "exists_in_source": name_evidence.is_grounded,
        "match_type": name_evidence.match_type,
        "confidence": name_evidence.confidence,
        "matched_text": name_evidence.matched_text,
        "proof": name_evidence.get_proof_snippet(),
        "context_before": name_evidence.context_before,
        "context_after": name_evidence.context_after,
    }


def review_similar_companies(
    seed_company: str,
    search_results: List[SearchResult],
    criteria: List[str] = None,
) -> List[CompanyValidation]:
    """
    Validate that found companies exist and match similarity criteria.
    
    Now includes DETERMINISTIC validation first (code-based),
    then LLM validation for deeper checks.
    
    For each company:
    1. Deterministic: Verify company name appears in source (exact match)
    2. Deterministic: Verify website domain matches company name
    3. LLM: Verify it matches the selected similarity criteria
    """
    trace = create_trace(
        name="review_similar_companies",
        input_data={
            "seed_company": seed_company,
            "companies": [r.name for r in search_results],
            "criteria": criteria,
        },
        metadata={"seed_company": seed_company},
    )

    seed_data = PORTFOLIO_COMPANIES.get(seed_company, {})
    
    # STEP 1: Run DETERMINISTIC validation first (no LLM)
    deterministic_results = {}
    for result in search_results:
        deterministic_results[result.name] = {
            "company": validate_company_deterministic(result),
            "website": validate_website_deterministic(result),
            "grounding_score": result.grounding_score,
            "grounded_evidence": result.grounded_evidence,
        }
    
    # Build company list for prompt (include deterministic results)
    companies_text = ""
    for i, result in enumerate(search_results):
        det = deterministic_results[result.name]
        companies_text += f"""
--- Company {i+1}: {result.name} ---
Description: {result.description}
Website: {result.website}
Location: {result.location}
Sector: {result.sector}
Source URL: {result.source_url}
Source Snippet: {result.source_snippet[:500] if result.source_snippet else 'N/A'}
[DETERMINISTIC CHECK] Name in source: {det['company']['exists_in_source']} ({det['company']['match_type']})
[DETERMINISTIC CHECK] Website valid: {det['website']['is_valid']} ({det['website']['validation_method']})
[DETERMINISTIC CHECK] Grounding score: {det['grounding_score']:.0%}
"""

    criteria_text = ", ".join(criteria) if criteria else "all dimensions"

    prompt = f"""You are a fact-checker validating company research.

SEED COMPANY: {seed_company}
- Description: {seed_data.get('description', 'N/A')}
- Tech Edge: {seed_data.get('tech_edge', 'N/A')}
- Sector: {seed_data.get('sector', 'N/A')}

SIMILARITY CRITERIA USED: {criteria_text}

COMPANIES TO VALIDATE:
{companies_text}

TASK: For each company, validate:
1. EXISTENCE: Does this company actually exist? Look for evidence.
2. SIMILARITY: Does it genuinely match the seed company on the selected criteria?

RULES:
1. A company EXISTS if there's a real website, news coverage, or verifiable presence.
2. A company is SIMILAR if it matches on the criteria dimensions.
3. Flag any company that appears to be hallucinated or misrepresented.
4. Be skeptical — if evidence is weak, say so.

Return JSON:
{{
  "company_validations": [
    {{
      "company_name": "Company Name",
      "exists": true | false,
      "exists_evidence": "Evidence of existence or why it might not exist",
      "exists_source": "URL or source proving existence",
      "similarity_valid": true | false,
      "similarity_reason": "Why this company does/doesn't match the criteria"
    }}
  ]
}}"""

    try:
        response = call_gemini(
            prompt=prompt,
            trace=trace,
            span_name="validate_companies",
            metadata={"companies_count": len(search_results)},
        )

        data = parse_json_response(response)
        validations = []

        for v in data.get("company_validations", []):
            company_name = v.get("company_name", "Unknown")
            
            # Merge deterministic results with LLM results
            det = deterministic_results.get(company_name, {})
            det_company = det.get("company", {})
            det_website = det.get("website", {})
            
            # Override LLM "exists" with deterministic check if we have proof
            exists = v.get("exists", False)
            if det_company.get("exists_in_source"):
                exists = True  # Deterministic proof trumps LLM uncertainty
            
            # Build evidence string with deterministic proof
            exists_evidence = v.get("exists_evidence", "No evidence")
            if det_company.get("proof"):
                exists_evidence = f"[DETERMINISTIC] {det_company['proof']}\n[LLM] {exists_evidence}"
            
            # Add website validation to field_validations
            field_vals = []
            if det_website:
                field_vals.append(ValidationItem(
                    field="website",
                    status="verified" if det_website.get("is_valid") else "unverified",
                    original_value=det_website.get("website", ""),
                    evidence=det_website.get("proof", ""),
                    source_url=det_website.get("matched_text", ""),
                    confidence=det_website.get("confidence", 0.0),
                ))
            
            validations.append(CompanyValidation(
                company_name=company_name,
                exists=exists,
                exists_evidence=exists_evidence,
                exists_source=v.get("exists_source", "unverified"),
                similarity_valid=v.get("similarity_valid", False),
                similarity_reason=v.get("similarity_reason", "No reason provided"),
                field_validations=field_vals,
            ))

        if trace:
            trace.update(output={"validations_count": len(validations)})
            trace.end()

        return validations

    except Exception as e:
        logger.error(f"Company validation failed: {e}")
        if trace:
            trace.update(output={"error": str(e)}, level="ERROR")
            trace.end()
        return []


def explain_scoring(scored_companies: List[ScoredCompany]) -> Dict[str, List[ScoringExplanation]]:
    """
    Generate explanations for how each score was calculated.
    
    This creates the "scoring methodology" section of the Appendix,
    showing exactly what evidence was used for each score.
    """
    explanations = {}

    for company in scored_companies:
        company_name = company.search_result.name
        explanations[company_name] = []

        for dim_key, dim_config in SCORING_DIMENSIONS.items():
            score_obj = company.scores.get(dim_key)
            
            if score_obj:
                # Determine if score is grounded
                grounding = "grounded" if (
                    score_obj.evidence_quote and 
                    score_obj.evidence_quote != "N/A" and
                    score_obj.source_url and
                    score_obj.source_url != "N/A"
                ) else "ungrounded"

                explanations[company_name].append(ScoringExplanation(
                    dimension=dim_config["label"],
                    score=score_obj.score,
                    methodology=dim_config["prompt_guidance"][:200],
                    evidence_used=score_obj.evidence_quote,
                    source_url=score_obj.source_url,
                    grounding_check=grounding,
                ))
            else:
                explanations[company_name].append(ScoringExplanation(
                    dimension=dim_config["label"],
                    score=None,
                    methodology=dim_config["prompt_guidance"][:200],
                    evidence_used="No evidence available",
                    source_url="N/A",
                    grounding_check="ungrounded",
                ))

    return explanations


def run_full_review(
    seed_company: str,
    search_results: List[SearchResult],
    scored_companies: List[ScoredCompany],
    criteria: List[str] = None,
) -> ReviewResult:
    """
    Run the complete review pipeline.
    
    Returns a ReviewResult with all validation data for the Appendix.
    """
    logger.info(f"Starting review for {seed_company}")

    # Step 1: Validate seed company profile
    seed_validations = review_seed_company(seed_company)

    # Step 2: Validate similar companies
    company_validations = review_similar_companies(
        seed_company, search_results, criteria
    )

    # Step 3: Explain scoring methodology
    scoring_explanations = explain_scoring(scored_companies)

    # Step 4: Calculate overall confidence and flag hallucinations
    hallucination_flags = []
    confidence_scores = []

    for sv in seed_validations:
        confidence_scores.append(sv.confidence)
        if sv.status == "incorrect":
            hallucination_flags.append(f"Seed profile '{sv.field}' may be incorrect")

    for cv in company_validations:
        if not cv.exists:
            hallucination_flags.append(f"Company '{cv.company_name}' may not exist")
            confidence_scores.append(0.0)
        elif not cv.similarity_valid:
            hallucination_flags.append(f"Company '{cv.company_name}' may not be similar")
            confidence_scores.append(0.5)
        else:
            confidence_scores.append(1.0)

    overall_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0

    # Step 5: Generate summary
    verified_count = sum(1 for cv in company_validations if cv.exists and cv.similarity_valid)
    total_count = len(company_validations)

    review_summary = (
        f"Review complete. {verified_count}/{total_count} companies verified as existing and similar. "
        f"Overall confidence: {overall_confidence:.0%}. "
        f"Hallucination flags: {len(hallucination_flags)}."
    )

    return ReviewResult(
        seed_company=seed_company,
        seed_validations=seed_validations,
        company_validations=company_validations,
        scoring_explanations=scoring_explanations,
        overall_confidence=overall_confidence,
        hallucination_flags=hallucination_flags,
        review_summary=review_summary,
    )
