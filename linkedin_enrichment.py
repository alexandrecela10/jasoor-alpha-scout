"""
LinkedIn Enrichment Module — Fetch company details from LinkedIn.

After the initial search finds companies, this module enriches them with:
- Employee count (critical for filtering startups vs large companies)
- Headquarters location (verified)
- Founders and leadership team
- Company description from LinkedIn

This uses Tavily to search for LinkedIn company pages, then extracts
structured data. We don't scrape LinkedIn directly (against ToS).

Why this matters:
- Employee count is a hard filter — we only want startups (<100 employees)
- LinkedIn location is more reliable than news article mentions
- Founder info helps assess team quality
"""

import logging
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

from tavily import TavilyClient
from llm_client import call_gemini, parse_json_response
from models import SearchResult

logger = logging.getLogger(__name__)

# Default employee threshold — companies above this are filtered out
DEFAULT_MAX_EMPLOYEES = 100

# MENA region countries — only companies headquartered here pass the location filter
MENA_COUNTRIES = [
    # Gulf Cooperation Council (GCC)
    "uae", "united arab emirates", "dubai", "abu dhabi",
    "saudi arabia", "ksa", "riyadh", "jeddah",
    "qatar", "doha",
    "kuwait",
    "bahrain",
    "oman",
    # North Africa
    "egypt", "cairo",
    "morocco", "casablanca",
    "tunisia", "tunis",
    "algeria",
    "libya",
    # Levant
    "jordan", "amman",
    "lebanon", "beirut",
    "palestine", "west bank", "gaza",
    # Other MENA
    "iraq", "baghdad",
    "yemen",
    "syria",
    "iran", "tehran",
    # Generic terms
    "mena", "middle east", "gulf", "gcc", "north africa", "levant",
]


@dataclass
class LinkedInEnrichment:
    """
    Enriched company data from LinkedIn.
    
    This is the "second pass" data that adds verified info
    to the initial search results.
    """
    company_name: str
    linkedin_url: str = ""
    employee_count: int = -1              # -1 = unknown
    employee_range: str = ""              # e.g., "11-50", "51-200"
    headquarters: str = ""                # Verified location from LinkedIn
    founded_year: int = -1
    industry: str = ""
    company_type: str = ""                # e.g., "Privately Held"
    specialties: List[str] = field(default_factory=list)
    
    # Leadership info
    founders: List[str] = field(default_factory=list)
    leadership_team: List[Dict] = field(default_factory=list)  # [{name, title, linkedin_url}]
    
    # Enrichment metadata
    enrichment_source: str = ""           # URL where we found this data
    enrichment_confidence: float = 0.0    # How confident we are in the data
    is_verified: bool = False             # True if we found the actual LinkedIn page
    
    def to_dict(self) -> Dict:
        return {
            "company_name": self.company_name,
            "linkedin_url": self.linkedin_url,
            "employee_count": self.employee_count,
            "employee_range": self.employee_range,
            "headquarters": self.headquarters,
            "founded_year": self.founded_year,
            "industry": self.industry,
            "company_type": self.company_type,
            "specialties": self.specialties,
            "founders": self.founders,
            "leadership_team": self.leadership_team,
            "enrichment_source": self.enrichment_source,
            "enrichment_confidence": self.enrichment_confidence,
            "is_verified": self.is_verified,
        }
    
    def passes_size_filter(self, max_employees: int = DEFAULT_MAX_EMPLOYEES) -> bool:
        """
        Check if company passes the employee count filter.
        
        Returns True if:
        - Employee count is unknown (give benefit of doubt)
        - Employee count is <= max_employees
        """
        if self.employee_count == -1:
            # Unknown — check the range if available
            if self.employee_range:
                # Parse ranges like "11-50", "51-200"
                match = re.search(r'(\d+)', self.employee_range)
                if match:
                    lower_bound = int(match.group(1))
                    # If lower bound is already too high, filter out
                    if lower_bound > max_employees:
                        return False
            return True  # Unknown, give benefit of doubt
        return self.employee_count <= max_employees
    
    def is_in_mena(self) -> bool:
        """
        Check if company is headquartered in MENA region.
        
        Returns True if:
        - Headquarters contains a MENA country/city name
        - Location is unknown (give benefit of doubt for initial search results)
        """
        if not self.headquarters:
            return True  # Unknown location — give benefit of doubt
        
        hq_lower = self.headquarters.lower()
        
        # Check if any MENA country/city is mentioned
        for mena_term in MENA_COUNTRIES:
            if mena_term in hq_lower:
                return True
        
        return False


def _get_tavily_client() -> TavilyClient:
    """Get Tavily client for LinkedIn searches."""
    import os
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("TAVILY_API_KEY not set")
    return TavilyClient(api_key=api_key)


def search_linkedin_company(company_name: str) -> Optional[Dict]:
    """
    Search for a company's LinkedIn page using Tavily.
    
    Returns the raw search result with LinkedIn URL and snippet.
    """
    try:
        client = _get_tavily_client()
        
        # Search specifically for LinkedIn company page
        query = f'"{company_name}" site:linkedin.com/company'
        
        results = client.search(
            query=query,
            search_depth="basic",
            max_results=3,
            include_domains=["linkedin.com"],
        )
        
        # Find the best match (company page, not person)
        for r in results.get("results", []):
            url = r.get("url", "")
            if "/company/" in url.lower():
                return {
                    "url": url,
                    "title": r.get("title", ""),
                    "content": r.get("content", ""),
                }
        
        return None
        
    except Exception as e:
        logger.warning(f"LinkedIn search failed for {company_name}: {e}")
        return None


def extract_linkedin_data(
    company_name: str,
    linkedin_result: Dict,
) -> LinkedInEnrichment:
    """
    Extract structured data from LinkedIn search result using Gemini.
    
    The search result contains a snippet from the LinkedIn page.
    We use Gemini to parse out the structured fields.
    """
    enrichment = LinkedInEnrichment(
        company_name=company_name,
        linkedin_url=linkedin_result.get("url", ""),
        enrichment_source=linkedin_result.get("url", ""),
    )
    
    content = linkedin_result.get("content", "")
    title = linkedin_result.get("title", "")
    
    if not content:
        return enrichment
    
    prompt = f"""Extract company information from this LinkedIn page snippet.

Company Name: {company_name}
LinkedIn Title: {title}
LinkedIn Snippet: {content}

Extract the following fields. Return "unknown" if not found:

Return JSON:
{{
    "employee_count": <number or -1 if unknown>,
    "employee_range": "<range like '11-50' or 'unknown'>",
    "headquarters": "<city, country or 'unknown'>",
    "founded_year": <year or -1 if unknown>,
    "industry": "<industry or 'unknown'>",
    "company_type": "<e.g., 'Privately Held' or 'unknown'>",
    "specialties": ["<specialty1>", "<specialty2>"],
    "founders": ["<founder1>", "<founder2>"],
    "leadership_team": [
        {{"name": "<name>", "title": "<title>"}}
    ]
}}

IMPORTANT:
- For employee_count, look for patterns like "11-50 employees", "51-200", etc.
- Convert ranges to the LOWER bound number (e.g., "11-50" → 11)
- Only include founders/leadership if explicitly mentioned
- Return valid JSON only"""

    try:
        response = call_gemini(
            prompt=prompt,
            trace=None,
            span_name="extract_linkedin_data",
        )
        
        data = parse_json_response(response)
        
        if isinstance(data, dict):
            enrichment.employee_count = data.get("employee_count", -1)
            enrichment.employee_range = data.get("employee_range", "")
            enrichment.headquarters = data.get("headquarters", "")
            enrichment.founded_year = data.get("founded_year", -1)
            enrichment.industry = data.get("industry", "")
            enrichment.company_type = data.get("company_type", "")
            enrichment.specialties = data.get("specialties", [])
            enrichment.founders = data.get("founders", [])
            enrichment.leadership_team = data.get("leadership_team", [])
            enrichment.is_verified = True
            enrichment.enrichment_confidence = 0.8
            
            # Clean up "unknown" values
            if enrichment.headquarters == "unknown":
                enrichment.headquarters = ""
            if enrichment.employee_range == "unknown":
                enrichment.employee_range = ""
        
        return enrichment
        
    except Exception as e:
        logger.warning(f"LinkedIn data extraction failed for {company_name}: {e}")
        return enrichment


def enrich_company(company_name: str) -> LinkedInEnrichment:
    """
    Full enrichment pipeline for a single company.
    
    1. Search for LinkedIn company page
    2. Extract structured data from the result
    """
    # Step 1: Find LinkedIn page
    linkedin_result = search_linkedin_company(company_name)
    
    if not linkedin_result:
        logger.info(f"No LinkedIn page found for {company_name}")
        return LinkedInEnrichment(company_name=company_name)
    
    # Step 2: Extract structured data
    enrichment = extract_linkedin_data(company_name, linkedin_result)
    
    logger.info(
        f"Enriched {company_name}: {enrichment.employee_range} employees, "
        f"HQ: {enrichment.headquarters or 'unknown'}"
    )
    
    return enrichment


def enrich_search_results(
    search_results: List[SearchResult],
    max_employees: int = DEFAULT_MAX_EMPLOYEES,
    mena_only: bool = True,
) -> Tuple[List[SearchResult], List[SearchResult], Dict[str, LinkedInEnrichment]]:
    """
    Enrich all search results with LinkedIn data and apply hard filters.
    
    Args:
        search_results: Companies from initial search
        max_employees: Maximum employee count (default: 100)
        mena_only: Only include companies headquartered in MENA (default: True)
    
    Returns:
        (passed_filter, filtered_out, enrichments_dict)
        
    Hard filters applied:
    1. Company size: Must have <= max_employees
    2. Location: Must be headquartered in MENA region (if mena_only=True)
    """
    passed = []
    filtered_out = []
    enrichments = {}
    
    for sr in search_results:
        # Enrich with LinkedIn data
        enrichment = enrich_company(sr.name)
        enrichments[sr.name] = enrichment
        
        # Apply size filter
        passes_size = enrichment.passes_size_filter(max_employees)
        
        # Apply MENA location filter
        passes_location = enrichment.is_in_mena() if mena_only else True
        
        if passes_size and passes_location:
            # Update SearchResult with enriched data
            if enrichment.headquarters and enrichment.headquarters != "unknown":
                sr.location = enrichment.headquarters
            if enrichment.founders:
                sr.founders = enrichment.founders
            
            # Store enrichment in grounded_evidence
            if not hasattr(sr, 'grounded_evidence') or sr.grounded_evidence is None:
                sr.grounded_evidence = {}
            sr.grounded_evidence["linkedin_enrichment"] = enrichment.to_dict()
            
            passed.append(sr)
            logger.info(f"✓ {sr.name} passed filters ({enrichment.employee_range}, {enrichment.headquarters or 'unknown location'})")
        else:
            filtered_out.append(sr)
            if not passes_size:
                logger.info(
                    f"✗ {sr.name} filtered out — too large "
                    f"({enrichment.employee_count} employees > {max_employees})"
                )
            elif not passes_location:
                logger.info(
                    f"✗ {sr.name} filtered out — not in MENA "
                    f"(HQ: {enrichment.headquarters})"
                )
    
    logger.info(
        f"LinkedIn enrichment complete: {len(passed)} passed, "
        f"{len(filtered_out)} filtered out"
    )
    
    return passed, filtered_out, enrichments


def format_enrichment_for_display(enrichment: LinkedInEnrichment) -> str:
    """
    Format enrichment data for UI display.
    """
    parts = []
    
    if enrichment.linkedin_url:
        parts.append(f"🔗 [LinkedIn]({enrichment.linkedin_url})")
    
    if enrichment.employee_range:
        parts.append(f"👥 {enrichment.employee_range} employees")
    elif enrichment.employee_count > 0:
        parts.append(f"👥 ~{enrichment.employee_count} employees")
    
    if enrichment.headquarters:
        parts.append(f"📍 {enrichment.headquarters}")
    
    if enrichment.founded_year > 0:
        parts.append(f"📅 Founded {enrichment.founded_year}")
    
    if enrichment.founders:
        founders_str = ", ".join(enrichment.founders[:3])
        parts.append(f"👤 Founders: {founders_str}")
    
    if enrichment.industry:
        parts.append(f"🏢 {enrichment.industry}")
    
    return " | ".join(parts) if parts else "No LinkedIn data found"
