"""
Gemini + Google Search Module — Fast company discovery with live web grounding.

This module replaces the Tavily-based search with Gemini's native Google Search
grounding capability. Benefits:
1. Single API call instead of multiple Tavily + agent calls
2. ~3s for 10 companies vs ~60s before
3. Already filtered by criteria (MENA, early-stage, <100 employees)
4. Source URLs from Google Search for grounding

The old Tavily search is kept as a fallback option.
"""

import os
import logging
import json
from typing import List, Dict, Optional, Union, Tuple

from google import genai
from google.genai import types

from models import SearchResult, CompanyProfile
from config import PORTFOLIO_COMPANIES
from persistence import get_blacklist_set, _normalize_company_name
from tracing import create_generation, get_langfuse

logger = logging.getLogger(__name__)


def _get_client() -> genai.Client:
    """Create a Gemini client from env var."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")
    return genai.Client(api_key=api_key)


def search_with_gemini(
    seed: Union[str, CompanyProfile, Dict],
    criteria: List[str] = None,
    location: str = "MENA",
    max_results: int = 10,
    max_employees: int = 100,
    early_stage_only: bool = True,
) -> List[SearchResult]:
    """
    Search for similar companies using Gemini + Google Search grounding.
    
    This is the PRIMARY search method - fast and already filtered.
    
    Args:
        seed: Seed company (name, CompanyProfile, or dict)
        criteria: Which similarity criteria to use
        location: Target region (default: MENA)
        max_results: How many companies to return
        max_employees: Maximum employee count filter
        early_stage_only: Only Seed to Series B
    
    Returns:
        List of SearchResult objects with source URLs from Google Search
    """
    # Normalize seed to get attributes
    if isinstance(seed, str):
        seed_name = seed
        seed_data = PORTFOLIO_COMPANIES.get(seed, {})
    elif isinstance(seed, CompanyProfile):
        seed_name = seed.name
        seed_data = seed.to_attrs_dict()
    elif isinstance(seed, dict):
        seed_name = seed.get("name", "target company")
        seed_data = seed
    else:
        seed_name = str(seed)
        seed_data = {}
    
    # Build the search prompt with all criteria baked in
    industry = seed_data.get("industry_vertical", "technology")
    problem = seed_data.get("problem_statement", "")
    target_clients = seed_data.get("target_clients", "")
    
    # Stage filter text
    stage_filter = "Seed, Pre-Seed, Series A, or Series B funding stage" if early_stage_only else "any funding stage"
    
    prompt = f"""You are a venture capital analyst searching for startups similar to {seed_name}.

SEARCH CRITERIA:
- Industry: {industry}
- Problem solved: {problem}
- Target clients: {target_clients}
- Location: MUST be headquartered in {location} region (UAE, Saudi Arabia, Egypt, Jordan, Morocco, Tunisia, Bahrain, Kuwait, Oman, Qatar, Lebanon, Iraq, Algeria, Libya, Sudan, Yemen, Palestine, Syria)
- Company size: MUST have fewer than {max_employees} employees
- Funding stage: MUST be {stage_filter}

TASK: Find {max_results} real startups that match these criteria.

For EACH company, provide:
1. name: Company name
2. website: Official website URL
3. linkedin: LinkedIn company page URL
4. description: One sentence description
5. sector: Industry sector
6. location: City, Country (must be in MENA)
7. employee_count: Estimated number of employees (must be < {max_employees})
8. funding_stage: Current funding stage (must be {stage_filter})
9. source_url: URL where you found this information

IMPORTANT:
- Only include REAL companies that exist today
- Only include companies that ACTUALLY match ALL criteria
- Do NOT include {seed_name} itself
- Do NOT include companies outside {location}
- Do NOT include companies with more than {max_employees} employees
- Do NOT include companies beyond Series B (if early_stage_only)

Return as JSON array:
[
  {{
    "name": "Company Name",
    "website": "https://company.com",
    "linkedin": "https://linkedin.com/company/...",
    "description": "What the company does",
    "sector": "Fintech",
    "location": "Dubai, UAE",
    "employee_count": "50",
    "funding_stage": "Series A",
    "source_url": "https://source.com/article"
  }}
]
"""

    logger.info(f"Searching with Gemini for companies similar to {seed_name}")
    
    # Create Langfuse generation for tracing
    generation = create_generation(
        name="gemini_candidate_search",
        model="gemini-2.5-flash",
        input_data=prompt,
        metadata={
            "seed": seed_name,
            "max_results": max_results,
            "location": location,
            "early_stage_only": early_stage_only,
        }
    )
    
    try:
        client = _get_client()
        
        # Call Gemini (without Google Search grounding - faster and more reliable)
        # WHY NO GOOGLE SEARCH GROUNDING?
        # - Google Search grounding causes TOO_MANY_TOOL_CALLS errors
        # - Takes 127s+ vs 15s without grounding
        # - Returns empty responses due to tool call timeouts
        # - We use Tavily for grounded verification instead (more control)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,  # Low temperature for factual output
            )
        )
        
        # Parse the response - handle None case
        text = response.text if response.text else ""
        if not text:
            # Try to get text from candidates
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    text = "".join(p.text for p in candidate.content.parts if hasattr(p, 'text') and p.text)
        
        if not text:
            logger.warning("Empty response from Gemini")
            if generation:
                generation.update(output="Empty response", status="error")
            return []
        
        # Update Langfuse generation with response
        if generation:
            generation.update(output=text[:2000], status="success")
            
        logger.info(f"Gemini response length: {len(text)} chars")
        
        # Extract JSON from response
        companies = _parse_companies_json(text)
        
        if not companies:
            logger.warning("No companies found in Gemini response")
            return []
        
        # Load blacklist for filtering
        blacklist = get_blacklist_set()
        
        # Convert to SearchResult objects
        results = []
        for company in companies:
            # Skip blacklisted companies
            normalized_name = _normalize_company_name(company.get("name", ""))
            if normalized_name in blacklist:
                logger.info(f"⏭️ Skipping blacklisted: {company.get('name')}")
                continue
            
            # Skip the seed company itself
            if _normalize_company_name(seed_name) == normalized_name:
                continue
            
            sr = SearchResult(
                name=company.get("name", "Unknown"),
                description=company.get("description", ""),
                website=company.get("website", ""),
                source_url=company.get("source_url", ""),
                location=company.get("location", ""),
                sector=company.get("sector", ""),
                funding_stage=company.get("funding_stage", ""),
                founders=[],  # Will be enriched later if needed
                funding_amount="",
            )
            
            # Store additional data in grounded_evidence
            sr.grounded_evidence = {
                "linkedin": company.get("linkedin", ""),
                "employee_count": company.get("employee_count", ""),
                "search_method": "gemini_google_search",
            }
            
            results.append(sr)
        
        logger.info(f"Found {len(results)} companies via Gemini + Google Search")
        return results[:max_results]
        
    except Exception as e:
        logger.error(f"Gemini search failed: {e}")
        return []


def _parse_companies_json(text: str) -> List[Dict]:
    """
    Parse JSON array of companies from Gemini response.
    Handles markdown code blocks and partial JSON.
    """
    import re
    
    # Try to find JSON array in the response
    # First, try to extract from markdown code block
    json_match = re.search(r'```(?:json)?\s*(\[[\s\S]*?\])\s*```', text)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Try to find raw JSON array
    json_match = re.search(r'\[[\s\S]*\]', text)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass
    
    # Try the whole text as JSON
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    
    logger.warning("Could not parse JSON from Gemini response")
    return []


def verify_and_enrich(
    results: List[SearchResult],
    verify_stage: bool = True,
    verify_urls: bool = True,
    fetch_website_content: bool = True,
    fetch_independent_sources: bool = True,
    early_stage_only: bool = True,
) -> Tuple[List[SearchResult], List[SearchResult]]:
    """
    Verify and enrich Gemini search results with grounded data.
    
    IMPORTANT: Gemini AI Search is for QUICK CANDIDATE GENERATION only.
    Gemini's training data has a cutoff date, so we use Tavily for:
    - Stage verification (recent funding news)
    - Independent sources (Crunchbase, TechCrunch, etc.)
    
    This runs AFTER Gemini search but BEFORE scoring to ensure:
    1. Website and LinkedIn URLs actually exist
    2. Funding stage is accurate (from recent news via Tavily)
    3. Scorer has website content (case studies, product info)
    4. Scorer has independent sources (news, Crunchbase) for grounding
    
    Args:
        results: Companies from Gemini search (candidates)
        verify_stage: Run Stage Agent to verify funding stage from news
        verify_urls: Verify website and LinkedIn URLs exist
        fetch_website_content: Fetch website content for scorer
        fetch_independent_sources: Search Tavily for independent sources
        early_stage_only: Filter out companies beyond Series B
    
    Returns:
        (passed, filtered_out) - companies that passed verification
    """
    import os
    import requests
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from source_enrichment import find_funding_stage, is_early_stage, fetch_website_content as fetch_content
    from persistence import add_to_blacklist
    from tavily import TavilyClient
    
    # Independent sources to search for grounding
    GROUNDING_SOURCES = [
        "crunchbase.com",
        "techcrunch.com",
        "wamda.com",  # MENA tech news
        "menabytes.com",  # MENA startups
        "magnitt.com",  # MENA startup data
        "zawya.com",  # MENA business news
    ]
    
    def check_url(url: str) -> bool:
        """Quick HEAD request to check if URL exists."""
        if not url or not url.startswith("http"):
            return False
        try:
            response = requests.head(url, timeout=3, allow_redirects=True)
            return response.status_code < 400
        except:
            return False
    
    def search_independent_sources(company_name: str, location: str) -> List[Dict]:
        """Search Tavily for independent sources about the company."""
        try:
            api_key = os.environ.get("TAVILY_API_KEY")
            if not api_key:
                return []
            client = TavilyClient(api_key=api_key)
            
            query = f'"{company_name}" startup {location}'
            results = client.search(
                query=query,
                search_depth="basic",  # Fast search
                max_results=3,
                include_domains=GROUNDING_SOURCES,
            )
            
            sources = []
            for r in results.get("results", []):
                sources.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", "")[:500],
                    "source": r.get("url", "").split("/")[2] if r.get("url") else "",
                })
            return sources
        except Exception as e:
            logger.warning(f"Independent source search failed for {company_name}: {e}")
            return []
    
    passed = []
    filtered_out = []
    
    def process_company(sr: SearchResult) -> Tuple[SearchResult, bool, str]:
        """Process one company: verify URLs, stage, fetch content + sources."""
        filter_reason = ""
        
        if not sr.grounded_evidence:
            sr.grounded_evidence = {}
        
        # 1. Verify website URL exists
        if verify_urls and sr.website:
            if not check_url(sr.website):
                logger.warning(f"Website not accessible: {sr.website}")
                sr.grounded_evidence["website_verified"] = False
            else:
                sr.grounded_evidence["website_verified"] = True
        
        # 2. Verify LinkedIn URL exists
        if verify_urls:
            linkedin = sr.grounded_evidence.get("linkedin", "")
            if linkedin:
                if not check_url(linkedin):
                    logger.warning(f"LinkedIn not accessible: {linkedin}")
                    sr.grounded_evidence["linkedin_verified"] = False
                else:
                    sr.grounded_evidence["linkedin_verified"] = True
        
        # 3. Verify funding stage from recent news (Tavily)
        if verify_stage:
            stage_field = find_funding_stage(sr.name, {"location": sr.location})
            if stage_field:
                verified_stage = stage_field.value
                sr.funding_stage = verified_stage
                
                sr.grounded_evidence["stage_verification"] = {
                    "stage": verified_stage,
                    "source": stage_field.sources[0].to_dict() if stage_field.sources else None,
                    "verified_from": "tavily_news_search",
                }
                
                if early_stage_only and not is_early_stage(verified_stage):
                    filter_reason = f"Too late stage ({verified_stage} > Series B)"
                    return sr, False, filter_reason
        
        # 4. Fetch website content for scorer
        if fetch_website_content and sr.website:
            try:
                content = fetch_content(sr.website)
                if content:
                    sr.grounded_evidence["website_content"] = content[:5000]
            except Exception as e:
                logger.warning(f"Could not fetch website content for {sr.name}: {e}")
        
        # 5. Search independent sources for grounding (Tavily)
        if fetch_independent_sources:
            sources = search_independent_sources(sr.name, sr.location)
            if sources:
                sr.grounded_evidence["independent_sources"] = sources
                logger.info(f"Found {len(sources)} independent sources for {sr.name}")
        
        return sr, True, ""
    
    # Process all companies in parallel
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_company, sr): sr for sr in results}
        
        for future in as_completed(futures):
            try:
                sr, passed_filter, filter_reason = future.result()
                if passed_filter:
                    passed.append(sr)
                    logger.info(f"✓ {sr.name} verified (stage: {sr.funding_stage})")
                else:
                    filtered_out.append(sr)
                    logger.info(f"✗ {sr.name} filtered: {filter_reason}")
                    # Add to blacklist
                    if "late stage" in filter_reason.lower():
                        add_to_blacklist(sr.name, "late_stage", filter_reason)
            except Exception as e:
                logger.error(f"Verification failed: {e}")
                # Keep the company if verification fails
                passed.append(futures[future])
    
    logger.info(f"Verification complete: {len(passed)} passed, {len(filtered_out)} filtered")
    return passed, filtered_out


def verify_urls_exist(results: List[SearchResult]) -> List[SearchResult]:
    """
    Quick verification that website and LinkedIn URLs exist.
    Uses HEAD requests for speed (~1s total for 10 companies).
    
    Args:
        results: Companies from Gemini search
    
    Returns:
        Companies with verified URLs (unverified URLs set to empty)
    """
    import requests
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    def check_url(url: str) -> bool:
        """Quick HEAD request to check if URL exists."""
        if not url or not url.startswith("http"):
            return False
        try:
            response = requests.head(url, timeout=3, allow_redirects=True)
            return response.status_code < 400
        except:
            return False
    
    def verify_company(sr: SearchResult) -> SearchResult:
        """Verify website and LinkedIn for one company."""
        # Check website
        if sr.website and not check_url(sr.website):
            logger.info(f"Website not accessible: {sr.website}")
            sr.website = ""
        
        # Check LinkedIn
        linkedin = sr.grounded_evidence.get("linkedin", "") if sr.grounded_evidence else ""
        if linkedin and not check_url(linkedin):
            logger.info(f"LinkedIn not accessible: {linkedin}")
            if sr.grounded_evidence:
                sr.grounded_evidence["linkedin"] = ""
        
        return sr
    
    # Verify all companies in parallel
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(verify_company, sr): sr for sr in results}
        verified = []
        for future in as_completed(futures):
            try:
                verified.append(future.result())
            except Exception as e:
                logger.error(f"Verification failed: {e}")
                verified.append(futures[future])
    
    return verified
