"""
Tavily Search Module — finds similar MENAT startups based on a seed company.

Flow:
1. Build a search query from the seed company's tech_edge + location
2. Call Tavily API to get 10-20 raw search results (URLs + snippets)
3. Use Gemini to extract structured company data from the snippets
4. Return a list of SearchResult objects with source URLs attached

Grounding guarantee: Every SearchResult has a source_url. If Gemini can't
extract a field from the source, it returns "Not Found" (not a guess).
"""

import os
import logging
from typing import List, Optional

from tavily import TavilyClient

from models import SearchResult
from config import PORTFOLIO_COMPANIES, DEFAULT_SOURCES, DEFAULT_EXCLUSIONS
from llm_client import call_gemini, parse_json_response
from tracing import create_trace, get_langfuse
from grounding import (
    validate_all_fields,
    compute_grounding_score,
    validate_company_name,
    validate_website_domain,
)

logger = logging.getLogger(__name__)


def validate_grounding(company_name: str, source_content: str) -> bool:
    """
    Validate that a company name actually appears in the source content.
    
    This prevents hallucinations where the LLM invents company names
    that aren't mentioned in the source URL.
    
    Uses case-insensitive exact matching with fuzzy tolerance for
    common variations (e.g., "Byanat" vs "Byanat AI").
    """
    if not company_name or not source_content:
        return False
    
    # Normalize for comparison
    name_lower = company_name.lower().strip()
    content_lower = source_content.lower()
    
    # Check exact match
    if name_lower in content_lower:
        return True
    
    # Check first word (company names often have suffixes like "AI", "Tech", etc.)
    first_word = name_lower.split()[0] if name_lower.split() else ""
    if first_word and len(first_word) >= 3 and first_word in content_lower:
        return True
    
    # Check without common suffixes
    suffixes_to_remove = [" ai", " tech", " inc", " ltd", " llc", " co", " labs"]
    clean_name = name_lower
    for suffix in suffixes_to_remove:
        if clean_name.endswith(suffix):
            clean_name = clean_name[:-len(suffix)].strip()
    
    if clean_name and len(clean_name) >= 3 and clean_name in content_lower:
        return True
    
    return False


def filter_by_exclusions(results: list, exclusions: list) -> list:
    """
    Filter out search results that contain exclusion keywords.
    
    Example: If user excludes "raises", "funding round", results about
    recent fundraising will be filtered out (opportunity already gone).
    """
    if not exclusions:
        return results
    
    filtered = []
    for r in results:
        content = (r.get("content", "") + " " + r.get("title", "")).lower()
        
        # Check if any exclusion keyword is present
        excluded = False
        for excl in exclusions:
            if excl.lower() in content:
                excluded = True
                logger.info(f"Excluded result due to '{excl}': {r.get('title', '')[:50]}")
                break
        
        if not excluded:
            filtered.append(r)
    
    return filtered


def _get_tavily_client() -> TavilyClient:
    """Create Tavily client from env var. Raises ValueError if key missing."""
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise ValueError(
            "TAVILY_API_KEY not set. Get yours at https://tavily.com"
        )
    return TavilyClient(api_key=api_key)


def build_search_query(
    seed_company: str,
    criteria: List[str] = None,
    location: str = None,
    custom_attrs: dict = None,
) -> str:
    """
    Build a search query from the seed company's 6 structured attributes.

    The 6 attributes are:
    1. problem_statement - What pain point does the company solve?
    2. target_clients - Who are the ideal customers?
    3. industry_vertical - Which sector/industry?
    4. technology - What tech stack or innovation?
    5. location - Where are they based?
    6. company_size - What stage are they at?

    Example output:
    "startups solving climate change carbon removal B2B corporations Climate Tech in GCC MENA"

    Why this format? Tavily works best with natural language queries.
    We include only the criteria the user selected.
    """
    # Use custom attributes if provided (from UI edits), otherwise use config
    company_data = custom_attrs if custom_attrs else PORTFOLIO_COMPANIES.get(seed_company, {})
    query_parts = [f"startups similar to {seed_company}"]

    # Default to all 6 criteria if none specified
    if criteria is None:
        criteria = ["problem_statement", "target_clients", "industry_vertical", 
                    "technology", "location", "company_size"]

    # Add criteria-specific keywords from the 6 structured attributes
    if "problem_statement" in criteria:
        problem = company_data.get("problem_statement", "")
        if problem:
            query_parts.append(problem[:80])

    if "target_clients" in criteria:
        clients = company_data.get("target_clients", "")
        if clients:
            query_parts.append(clients[:60])

    if "industry_vertical" in criteria:
        vertical = company_data.get("industry_vertical", "")
        if vertical:
            query_parts.append(f"in {vertical} sector")

    if "technology" in criteria:
        tech = company_data.get("technology", "")
        if tech:
            query_parts.append(tech[:80])

    if "location" in criteria:
        loc = location or company_data.get("location", "MENA")
        query_parts.append(f"in {loc} MENA Middle East")

    if "company_size" in criteria:
        size = company_data.get("company_size", "")
        if size:
            query_parts.append(size[:40])
        else:
            query_parts.append("early-stage startup seed series-A")

    return " ".join(query_parts)


def search_similar_companies(
    seed_company: str,
    criteria: List[str] = None,
    location: str = None,
    sources: List[str] = None,
    exclusions: List[str] = None,
    custom_attrs: dict = None,
    max_results: int = 10,
) -> List[SearchResult]:
    """
    Find companies similar to a Jasoor portfolio company.

    Args:
        seed_company: Name of the seed (e.g., "Byanat AI")
        criteria:     Which similarity criteria to use (e.g., ["technology", "location"])
        location:     Override location filter (default: seed company's location)
        sources:      Websites to prioritize (default: DEFAULT_SOURCES)
        custom_attrs: Custom attributes from UI edits (overrides config)
        exclusions:   Keywords to exclude (e.g., ["raises", "funding round"])
        max_results:  How many companies to return (default: 10)

    Returns:
        List of SearchResult objects, each with source_url attached.
    """
    # Create Langfuse trace for this search operation
    trace = create_trace(
        name="search_similar_companies",
        input_data={
            "seed_company": seed_company,
            "criteria": criteria,
            "location": location,
            "sources": sources,
            "exclusions": exclusions,
            "max_results": max_results,
        },
        metadata={"seed_company": seed_company},
    )

    try:
        # Step 1: Build the search query using custom attributes if provided
        query = build_search_query(seed_company, criteria, location, custom_attrs)
        logger.info(f"Search query: {query}")

        # Step 2: Call Tavily API
        client = _get_tavily_client()
        source_domains = sources or DEFAULT_SOURCES

        # Tavily search — we ask for more results than needed because some
        # will be duplicates or irrelevant (news articles about the seed company)
        raw_results = client.search(
            query=query,
            search_depth="advanced",      # Deeper search, better results
            max_results=max_results * 3,  # Get extra for filtering
            include_domains=source_domains,
        )

        # Step 2.5: Filter by exclusions (e.g., remove fundraising news)
        filtered_results = filter_by_exclusions(
            raw_results.get("results", []),
            exclusions or DEFAULT_EXCLUSIONS,
        )
        logger.info(f"After exclusion filter: {len(filtered_results)} results (was {len(raw_results.get('results', []))})")

        # Step 3: Extract structured data using Gemini
        search_results = _extract_companies_from_results(
            filtered_results,
            seed_company=seed_company,
            max_results=max_results,
            criteria=criteria,
            trace=trace,
        )

        # Log success to Langfuse
        if trace is not None:
            try:
                trace.update(output={
                    "query": query,
                    "raw_results_count": len(raw_results.get("results", [])),
                    "extracted_companies": len(search_results),
                    "companies": [r.name for r in search_results],
                })
                trace.end()
            except Exception:
                pass

        return search_results

    except Exception as e:
        logger.error(f"Search failed: {e}")
        if trace is not None:
            try:
                trace.update(output={"error": str(e)}, level="ERROR")
                trace.end()
            except Exception:
                pass
        raise


def _extract_companies_from_results(
    raw_results: List[dict],
    seed_company: str,
    max_results: int,
    criteria: List[str] = None,
    trace=None,
) -> List[SearchResult]:
    """
    Use Gemini to extract structured company data from Tavily search results.

    Each raw result has: {"url": "...", "title": "...", "content": "..."}
    We ask Gemini to identify which results are about COMPANIES (not news articles)
    and extract: name, description, location, founders, funding.

    Grounding: Gemini is instructed to return "Not Found" for missing fields.
    """
    if not raw_results:
        return []

    # Format raw results for the prompt
    results_text = ""
    for i, r in enumerate(raw_results):
        results_text += f"""
--- Result {i+1} ---
URL: {r.get('url', 'N/A')}
Title: {r.get('title', 'N/A')}
Content: {r.get('content', 'N/A')[:1000]}
"""

    # Build criteria description for the prompt
    criteria_labels = {
        "problem_statement": "Problem Statement (what pain point they solve)",
        "target_clients": "Target Clients (who they sell to)",
        "industry_vertical": "Industry Vertical (sector they operate in)",
        "technology": "Technology (tech stack, AI, IoT, etc.)",
        "location": "Location (country/region)",
        "company_size": "Company Size (stage, team size)",
    }
    
    if criteria:
        criteria_text = "\n".join([f"- {criteria_labels.get(c, c)}" for c in criteria])
    else:
        criteria_text = "- All dimensions (problem, clients, industry, technology, location, size)"

    # Get seed company info for context
    seed_data = PORTFOLIO_COMPANIES.get(seed_company, {})
    seed_context = f"""
SEED COMPANY PROFILE:
- Name: {seed_company}
- Description: {seed_data.get('description', 'N/A')}
- Tech Edge: {seed_data.get('tech_edge', 'N/A')}
- Sector: {seed_data.get('sector', 'N/A')}
- Location: {seed_data.get('location', 'N/A')}
"""

    prompt = f"""You are a research analyst finding startups SIMILAR to a seed company.

{seed_context}

SIMILARITY CRITERIA (focus on these dimensions):
{criteria_text}

SEARCH RESULTS:
{results_text}

TASK: Extract up to {max_results} DISTINCT startup companies that are SIMILAR to {seed_company} based on the criteria above.

SIMILARITY MATCHING:
- Prioritize companies that match the selected criteria
- For "Problem Statement": look for companies solving similar pain points
- For "Target Clients": look for companies targeting similar customer segments
- For "Industry Vertical": look for companies in the same or adjacent sectors
- For "Technology": look for companies using similar tech stacks
- For "Location": look for companies in similar regions (MENA, GCC, etc.)
- For "Company Size": look for companies at similar stages (seed, Series A, etc.)

CRITICAL GROUNDING RULES:
1. Only extract COMPANIES that are EXPLICITLY NAMED in the source content.
2. The company name MUST appear in the source text — do NOT invent company names.
3. Do NOT include the seed company "{seed_company}" itself.
4. For each company, extract ONLY what is explicitly stated in the source.
5. If a field is not mentioned, use "Not Found".
6. Do NOT guess or invent founder names, funding amounts, or descriptions.
7. Include a "similarity_reason" explaining WHY this company matches the criteria.
8. ALWAYS try to find the company's official website URL.

WEBSITE RETRIEVAL:
- Look for the company's official website in the source content.
- If not directly mentioned, construct it from the company name (e.g., "companyname.com").
- The website is CRITICAL for scoring — it contains case studies and product info.

Return a JSON array with this structure:
[
  {{
    "name": "Company Name (MUST appear in source)",
    "description": "One-line description from the source",
    "website": "https://company-website.com (REQUIRED - find or construct)",
    "source_url": "URL where this company was found",
    "source_snippet": "EXACT quote from source that mentions this company name",
    "location": "Country or region",
    "sector": "Industry sector",
    "founders": ["Founder 1", "Founder 2"],
    "founders_linkedin": ["https://linkedin.com/in/...", "..."],
    "funding_stage": "Seed / Series A / etc.",
    "funding_amount": "$X million or Not Found",
    "similarity_reason": "Why this company matches the selected criteria"
  }}
]

Return ONLY the JSON array, no other text."""

    try:
        response = call_gemini(
            prompt=prompt,
            trace=trace,
            span_name="extract_companies",
            metadata={"raw_results_count": len(raw_results)},
        )

        data = parse_json_response(response)

        # Handle both list and dict responses
        if isinstance(data, dict):
            if "error" in data:
                logger.warning(f"Extraction failed: {data}")
                return []
            # Sometimes Gemini wraps the array in a key
            data = data.get("companies", [])

        # Build a lookup of raw results by URL for grounding validation
        raw_content_by_url = {
            r.get("url", ""): r.get("content", "") + " " + r.get("title", "")
            for r in raw_results
        }

        # Convert to SearchResult objects with ABSOLUTE GROUNDING
        results = []
        for item in data[:max_results * 2]:  # Check more items in case some fail validation
            company_name = item.get("name", "Unknown")
            source_url = item.get("source_url", "")
            source_snippet = item.get("source_snippet", "")
            
            # Get full source content for grounding
            source_content = raw_content_by_url.get(source_url, source_snippet)
            
            # ABSOLUTE GROUNDING: Validate ALL fields deterministically
            evidence_map = validate_all_fields(
                extracted_data=item,
                source_text=source_content,
                source_url=source_url,
            )
            
            # Check company name grounding (critical — must pass)
            name_evidence = evidence_map.get("name")
            if not name_evidence or not name_evidence.is_grounded:
                logger.warning(f"GROUNDING FAILED: '{company_name}' not found in source {source_url[:50]}...")
                continue  # Skip this company — likely hallucinated
            
            # Check website grounding (important — flag if wrong)
            website_evidence = evidence_map.get("website")
            website = item.get("website", "Not Found")
            if website_evidence and not website_evidence.is_grounded:
                logger.warning(f"WEBSITE UNGROUNDED: '{website}' for {company_name}")
                # Don't skip, but flag it — website might still be correct
            
            # Compute overall grounding score
            grounding_score = compute_grounding_score(evidence_map)
            
            # Convert evidence objects to dicts for storage
            evidence_dict = {k: v.to_dict() for k, v in evidence_map.items()}
            
            results.append(SearchResult(
                name=company_name,
                description=item.get("description", "Not Found"),
                website=website,
                source_url=source_url,
                source_snippet=source_snippet,
                location=item.get("location", "Not Found"),
                sector=item.get("sector", "Not Found"),
                founders=item.get("founders", []),
                founders_linkedin=item.get("founders_linkedin", []),
                funding_stage=item.get("funding_stage", "Not Found"),
                funding_amount=item.get("funding_amount", "Not Found"),
                grounded_evidence=evidence_dict,
                grounding_score=grounding_score,
                raw_source_text=source_content[:2000],  # Store for re-validation
            ))
            
            # Stop once we have enough validated results
            if len(results) >= max_results:
                break
        
        logger.info(f"Grounding validation: {len(results)} companies passed (from {len(data)} extracted)")
        return results

    except Exception as e:
        logger.error(f"Company extraction failed: {e}")
        return []
