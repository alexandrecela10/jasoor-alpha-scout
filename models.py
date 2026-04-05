"""
Data Models — dataclasses that define the shape of data flowing through Alpha Scout.

Think of these as "blueprints" for the data. Every company, score, and search result
follows one of these shapes. This keeps the code predictable — you always know
exactly what fields a company object has.

Why dataclasses? They give us:
- Auto-generated __init__, __repr__, __eq__
- Type hints for IDE autocomplete
- Easy conversion to dicts (for JSON / Streamlit display)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING

# Avoid circular import — GroundedEvidence is defined in grounding.py
if TYPE_CHECKING:
    from grounding import GroundedEvidence


@dataclass
class SearchResult:
    """
    One company found by Tavily search.

    Every field that comes from the internet MUST have a source_url.
    If Tavily didn't find something, we leave it as "Not Found".
    This is the first layer of our grounding guarantee.
    """
    name: str                               # Company name
    description: str = "Not Found"          # One-line description from source
    website: str = "Not Found"              # Company website URL
    source_url: str = ""                    # WHERE we found this company
    source_snippet: str = ""                # Raw text snippet from the source
    location: str = "Not Found"             # Country / region
    sector: str = "Not Found"              # Industry sector
    founders: List[str] = field(default_factory=list)          # Founder names
    founders_linkedin: List[str] = field(default_factory=list) # LinkedIn URLs
    funding_stage: str = "Not Found"        # Seed, Series A, etc.
    funding_amount: str = "Not Found"       # "$2M", "Undisclosed", etc.
    
    # Grounding evidence — deterministic proof for each field
    # Maps field name -> GroundedEvidence object
    grounded_evidence: Dict = field(default_factory=dict)
    grounding_score: float = 0.0            # Overall grounding confidence (0-1)
    raw_source_text: str = ""               # Full source text for re-validation
    website_verified: bool = False          # True if website was verified via HTTP fetch
    source_date: str = ""                   # Publication date of source (for recency filtering)
    source_age_days: int = -1               # Age of source in days (-1 = unknown)

    def to_dict(self) -> Dict:
        """Convert to dict for JSON serialization / Streamlit display."""
        return {
            "name": self.name,
            "description": self.description,
            "website": self.website,
            "source_url": self.source_url,
            "source_snippet": self.source_snippet,
            "location": self.location,
            "sector": self.sector,
            "founders": self.founders,
            "founders_linkedin": self.founders_linkedin,
            "funding_stage": self.funding_stage,
            "funding_amount": self.funding_amount,
            "grounded_evidence": {
                k: v.to_dict() if hasattr(v, 'to_dict') else v 
                for k, v in self.grounded_evidence.items()
            },
            "grounding_score": self.grounding_score,
            "website_verified": self.website_verified,
            "source_date": self.source_date,
            "source_age_days": self.source_age_days,
        }


@dataclass
class DimensionScore:
    """
    Score for ONE dimension (e.g., "Tech Moat") of ONE company.

    Two-pass scoring architecture:
    - signals_detected: Objective signals found via keyword matching (Pass 1)
    - sub_scores: Breakdown by sub-component (e.g., Patents, Data Moat)
    - score: Final LLM-interpreted score (Pass 2)

    The grounding rule: every score MUST have evidence_quote + source_url.
    If Gemini can't find evidence, score = None and evidence = "N/A".
    This prevents the AI from inventing scores.
    """
    dimension: str                          # e.g., "tech_moat"
    score: Optional[float] = None           # 1.0-5.0 decimal, or None if no evidence
    evidence_quote: str = "N/A"             # Exact quote from source
    source_url: str = "N/A"                 # URL where evidence was found
    reasoning: str = ""                     # Gemini's explanation of the score
    signals_detected: List[str] = field(default_factory=list)  # Objective signals found
    sub_scores: Dict[str, float] = field(default_factory=dict) # Sub-component scores
    
    # Grounding evidence — deterministic proof that evidence_quote exists in source
    grounded_evidence: Optional[Dict] = None  # GroundedEvidence.to_dict()
    is_grounded: bool = False                 # True if evidence_quote found in source

    def to_dict(self) -> Dict:
        return {
            "dimension": self.dimension,
            "score": self.score,
            "evidence_quote": self.evidence_quote,
            "source_url": self.source_url,
            "reasoning": self.reasoning,
            "signals_detected": self.signals_detected,
            "sub_scores": self.sub_scores,
            "grounded_evidence": self.grounded_evidence,
            "is_grounded": self.is_grounded,
        }


@dataclass
class CompanyProfile:
    """
    Rich profile for a SEED or BENCHMARK company (portfolio or successful MENA startup).

    Contains 10 structured attributes used to drive the eligibility search:
    - 6 core: problem_statement, target_clients, industry_vertical, technology, location, company_size
    - 4 moat: tech_moat, tech_stack, offer_moat, sales_distribution_moat

    These are analyst-editable and feed into the Tavily search query builder.
    """
    name: str
    description: str = ""
    website: str = ""
    # 6 eligibility attributes (drive similarity search)
    problem_statement: str = ""         # What pain point does this company solve?
    target_clients: str = ""            # Who are the ideal customers? (B2B/B2C, segments)
    industry_vertical: str = ""         # Which sector/industry?
    technology: str = ""                # What tech stack or innovation?
    location: str = ""                  # Where are they based?
    company_size: str = ""              # Stage, funding, team size
    # 4 moat attributes (deepen the search and scoring context)
    tech_moat: str = ""                 # Patents, proprietary data, network effects
    tech_stack: str = ""                # Specific technologies used (e.g., ML, IoT, SaaS)
    offer_moat: str = ""                # What makes the offer uniquely compelling?
    sales_distribution_moat: str = ""   # GTM advantages, channel partnerships
    # For benchmarks: achieved maturity stage
    achieved_stage: str = ""            # e.g., "Series D", "IPO", "Acquired"

    def to_attrs_dict(self) -> Dict:
        """Return the 10 attributes as a dict for search query building."""
        return {
            "problem_statement": self.problem_statement,
            "target_clients": self.target_clients,
            "industry_vertical": self.industry_vertical,
            "technology": self.technology,
            "location": self.location,
            "company_size": self.company_size,
            "tech_moat": self.tech_moat,
            "tech_stack": self.tech_stack,
            "offer_moat": self.offer_moat,
            "sales_distribution_moat": self.sales_distribution_moat,
        }


@dataclass
class ScoredCompany:
    """
    A company with all its scores attached.

    This is the "final product" of the scoring pipeline:
    SearchResult (from Tavily) + DimensionScores (from Gemini) = ScoredCompany.
    The Plotly visualization and report both consume this shape.
    """
    search_result: SearchResult             # Original search data
    scores: Dict[str, DimensionScore] = field(default_factory=dict)
    # Keys are dimension names: "offer_power", "tech_moat", etc.
    # Values are DimensionScore objects with evidence

    # Derived fields — computed from scores for the 2x2 matrix
    expected_cac: Optional[float] = None    # AI-estimated CAC (1-5 scale)
    expected_ltv: Optional[float] = None    # AI-estimated LTV (1-5 scale)

    ai_summary: str = ""                    # One-paragraph "why this is a fit" summary
    fit_reason: str = ""                    # Short bullet-point fit explanation

    def get_score_value(self, dimension: str) -> Optional[int]:
        """Get numeric score for a dimension, or None if N/A."""
        if dimension == "expected_cac":
            return self.expected_cac
        if dimension == "expected_ltv":
            return self.expected_ltv
        ds = self.scores.get(dimension)
        return ds.score if ds else None

    def to_dict(self) -> Dict:
        return {
            **self.search_result.to_dict(),
            "scores": {k: v.to_dict() for k, v in self.scores.items()},
            "expected_cac": self.expected_cac,
            "expected_ltv": self.expected_ltv,
            "ai_summary": self.ai_summary,
            "fit_reason": self.fit_reason,
        }
