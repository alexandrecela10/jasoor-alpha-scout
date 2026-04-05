"""
Source Enrichment Module — Find and verify company websites and LinkedIn pages.

This module implements an agentic workflow with two key agents:
1. Website Finder — Searches for and verifies the official company website
2. LinkedIn Finder — Searches for the company's LinkedIn page

After finding these sources, it extracts structured data from each and
combines them with strong grounding verification.

Key improvements over basic search:
- Websites are FOUND via search, not hallucinated from company name
- LinkedIn pages are verified to exist and match the company
- Multiple sources per data point (website + LinkedIn + news)
- Every claim is verified against actual page content
"""

import logging
import re
import requests
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from tavily import TavilyClient
from llm_client import call_gemini, parse_json_response
from models import SearchResult

logger = logging.getLogger(__name__)

# Timeout for HTTP requests
HTTP_TIMEOUT = 10

# Default employee threshold — companies above this are filtered out
DEFAULT_MAX_EMPLOYEES = 100

# Funding stages in order (for filtering)
# Companies at Series C or later are filtered out by default
FUNDING_STAGES_ORDER = [
    "pre-seed",
    "seed",
    "series a",
    "series b",
    "series c",
    "series d",
    "series e",
    "ipo",
    "public",
]

# Stages that pass the "early stage" filter (Series B and before)
EARLY_STAGE_CUTOFF = "series b"  # Inclusive

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
class SourceEvidence:
    """
    Evidence from a single source supporting a claim.
    
    Multiple SourceEvidence objects can support the same data point,
    providing stronger grounding.
    """
    source_url: str
    source_type: str  # "website", "linkedin", "news", "crunchbase"
    quote: str  # Exact text from source
    verified: bool = False  # True if we fetched the page and found the quote
    page_title: str = ""
    fetch_timestamp: str = ""


@dataclass
class EnrichedField:
    """
    A single data field with multiple sources of evidence.
    
    Example: location = "Dubai, UAE" supported by:
    - Website "About Us" page
    - LinkedIn headquarters field
    - News article mention
    """
    value: str
    confidence: float  # 0.0 to 1.0 based on source agreement
    sources: List[SourceEvidence] = field(default_factory=list)
    
    def add_source(self, source: SourceEvidence):
        """Add a source and recalculate confidence."""
        self.sources.append(source)
        # Confidence increases with more verified sources
        verified_count = sum(1 for s in self.sources if s.verified)
        self.confidence = min(1.0, 0.3 + (verified_count * 0.25))
    
    def to_dict(self) -> Dict:
        return {
            "value": self.value,
            "confidence": self.confidence,
            "source_count": len(self.sources),
            "sources": [
                {
                    "url": s.source_url,
                    "type": s.source_type,
                    "quote": s.quote[:200],  # Truncate for storage
                    "verified": s.verified,
                }
                for s in self.sources
            ]
        }


@dataclass
class CompanyEnrichment:
    """
    Complete enriched data for a company from multiple sources.
    
    Each field is an EnrichedField with multiple sources of evidence.
    """
    company_name: str
    
    # Found sources
    website_url: EnrichedField = None
    linkedin_url: EnrichedField = None
    
    # Enriched data (each with multiple sources)
    description: EnrichedField = None
    sector: EnrichedField = None
    location: EnrichedField = None
    employee_count: EnrichedField = None
    founded_year: EnrichedField = None
    founders: EnrichedField = None
    funding_stage: EnrichedField = None
    
    # Scoring-relevant data
    product_description: EnrichedField = None
    tech_stack: EnrichedField = None
    customers: EnrichedField = None
    partnerships: EnrichedField = None
    
    # Raw content for scoring
    website_content: str = ""
    linkedin_content: str = ""
    
    def to_dict(self) -> Dict:
        result = {"company_name": self.company_name}
        for field_name in ["website_url", "linkedin_url", "description", "sector", 
                          "location", "employee_count", "founded_year", "founders",
                          "funding_stage", "product_description", "tech_stack",
                          "customers", "partnerships"]:
            field_val = getattr(self, field_name)
            if field_val:
                result[field_name] = field_val.to_dict()
        return result


def get_tavily_client() -> TavilyClient:
    """Get Tavily client from environment."""
    import os
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("TAVILY_API_KEY not set")
    return TavilyClient(api_key=api_key)


def fetch_page_content(url: str) -> Tuple[bool, str, str]:
    """
    Fetch a webpage and return its text content.
    
    Returns:
        (success, content, title)
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; AlphaScout/1.0; +https://jasoor.vc)"
        }
        response = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT, allow_redirects=True)
        response.raise_for_status()
        
        # Extract title
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', response.text, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else ""
        
        # Extract text content (simple extraction)
        # Remove scripts and styles
        text = re.sub(r'<script[^>]*>.*?</script>', '', response.text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        # Clean whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return True, text[:50000], title  # Limit content size
        
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return False, "", ""


def verify_content_match(content: str, claim: str, threshold: float = 0.5) -> Tuple[bool, str]:
    """
    Verify that a claim appears in the content.
    
    Uses keyword matching and returns the matching quote if found.
    
    Args:
        content: Page content to search
        claim: The claim to verify (e.g., "Dubai, UAE")
        threshold: Minimum match ratio
    
    Returns:
        (matched, quote) - quote is the surrounding context if matched
    """
    if not content or not claim:
        return False, ""
    
    content_lower = content.lower()
    claim_lower = claim.lower()
    
    # Direct match
    if claim_lower in content_lower:
        # Find the quote with context
        idx = content_lower.find(claim_lower)
        start = max(0, idx - 50)
        end = min(len(content), idx + len(claim) + 50)
        quote = content[start:end].strip()
        return True, f"...{quote}..."
    
    # Keyword match - check if key terms appear
    keywords = [w for w in claim_lower.split() if len(w) > 2]
    if not keywords:
        return False, ""
    
    matches = sum(1 for kw in keywords if kw in content_lower)
    match_ratio = matches / len(keywords)
    
    if match_ratio >= threshold:
        # Find first keyword and get context
        for kw in keywords:
            if kw in content_lower:
                idx = content_lower.find(kw)
                start = max(0, idx - 50)
                end = min(len(content), idx + 100)
                quote = content[start:end].strip()
                return True, f"...{quote}..."
    
    return False, ""


# =============================================================================
# WEBSITE FINDER AGENT
# =============================================================================

def find_company_website(company_name: str, known_info: Dict = None) -> Optional[EnrichedField]:
    """
    Website Finder Agent — Search for and verify the official company website.
    
    This agent:
    1. Searches Tavily for "{company_name} official website"
    2. Filters results to find likely official sites
    3. Fetches the page to verify it mentions the company
    4. Returns the verified URL with evidence
    
    Args:
        company_name: Name of the company to find
        known_info: Any known info (sector, location) to help disambiguate
    
    Returns:
        EnrichedField with verified website URL, or None if not found
    """
    logger.info(f"🔍 Website Finder: Searching for {company_name}")
    
    try:
        client = get_tavily_client()
        
        # Build search query
        query = f'"{company_name}" official website'
        if known_info:
            if known_info.get("sector"):
                query += f' {known_info["sector"]}'
            if known_info.get("location"):
                query += f' {known_info["location"]}'
        
        # Search
        results = client.search(
            query=query,
            search_depth="basic",
            max_results=5,
            include_domains=[],  # No restrictions
            exclude_domains=["linkedin.com", "facebook.com", "twitter.com", "crunchbase.com"]
        )
        
        if not results.get("results"):
            logger.warning(f"No website results for {company_name}")
            return None
        
        # Score and filter results
        candidates = []
        for r in results["results"]:
            url = r.get("url", "")
            title = r.get("title", "")
            content = r.get("content", "")
            
            # Skip social media and aggregators
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if any(skip in domain for skip in ["linkedin", "facebook", "twitter", "crunchbase", "wikipedia"]):
                continue
            
            # Score based on company name in domain or title
            score = 0
            company_words = company_name.lower().split()
            
            # Check domain
            for word in company_words:
                if len(word) > 2 and word in domain:
                    score += 3
            
            # Check title
            if company_name.lower() in title.lower():
                score += 2
            
            # Check content
            if company_name.lower() in content.lower():
                score += 1
            
            if score > 0:
                candidates.append({
                    "url": url,
                    "title": title,
                    "content": content,
                    "score": score
                })
        
        if not candidates:
            logger.warning(f"No valid website candidates for {company_name}")
            return None
        
        # Sort by score and try top candidates
        candidates.sort(key=lambda x: x["score"], reverse=True)
        
        for candidate in candidates[:3]:
            url = candidate["url"]
            
            # Fetch and verify
            success, page_content, page_title = fetch_page_content(url)
            
            if success:
                # Verify company name appears on the page
                matched, quote = verify_content_match(page_content, company_name)
                
                if matched:
                    logger.info(f"✅ Found verified website for {company_name}: {url}")
                    
                    field = EnrichedField(value=url, confidence=0.0)
                    field.add_source(SourceEvidence(
                        source_url=url,
                        source_type="website",
                        quote=quote,
                        verified=True,
                        page_title=page_title
                    ))
                    return field
        
        # If no verified match, return best candidate with lower confidence
        best = candidates[0]
        logger.warning(f"⚠️ Unverified website for {company_name}: {best['url']}")
        
        field = EnrichedField(value=best["url"], confidence=0.3)
        field.add_source(SourceEvidence(
            source_url=best["url"],
            source_type="website",
            quote=best["content"][:200],
            verified=False,
            page_title=best["title"]
        ))
        return field
        
    except Exception as e:
        logger.error(f"Website finder failed for {company_name}: {e}")
        return None


# =============================================================================
# LINKEDIN FINDER AGENT
# =============================================================================

def find_company_linkedin(company_name: str, known_info: Dict = None) -> Optional[EnrichedField]:
    """
    LinkedIn Finder Agent — Search for the company's LinkedIn page.
    
    This agent:
    1. Searches Tavily for "{company_name} LinkedIn company"
    2. Filters to linkedin.com/company/ URLs
    3. Verifies the page matches the company
    4. Returns the verified URL with evidence
    
    Args:
        company_name: Name of the company to find
        known_info: Any known info to help disambiguate
    
    Returns:
        EnrichedField with verified LinkedIn URL, or None if not found
    """
    logger.info(f"🔍 LinkedIn Finder: Searching for {company_name}")
    
    try:
        client = get_tavily_client()
        
        # Search specifically for LinkedIn
        query = f'site:linkedin.com/company "{company_name}"'
        
        results = client.search(
            query=query,
            search_depth="basic",
            max_results=5,
            include_domains=["linkedin.com"]
        )
        
        if not results.get("results"):
            logger.warning(f"No LinkedIn results for {company_name}")
            return None
        
        # Filter to company pages only
        for r in results["results"]:
            url = r.get("url", "")
            title = r.get("title", "")
            content = r.get("content", "")
            
            # Must be a company page
            if "/company/" not in url.lower():
                continue
            
            # Check if company name appears in title or content
            if company_name.lower() in title.lower() or company_name.lower() in content.lower():
                logger.info(f"✅ Found LinkedIn for {company_name}: {url}")
                
                field = EnrichedField(value=url, confidence=0.8)
                field.add_source(SourceEvidence(
                    source_url=url,
                    source_type="linkedin",
                    quote=content[:200] if content else title,
                    verified=True,  # Tavily already fetched it
                    page_title=title
                ))
                return field
        
        # Return first company page even if name match is weak
        for r in results["results"]:
            url = r.get("url", "")
            if "/company/" in url.lower():
                logger.warning(f"⚠️ Weak LinkedIn match for {company_name}: {url}")
                
                field = EnrichedField(value=url, confidence=0.4)
                field.add_source(SourceEvidence(
                    source_url=url,
                    source_type="linkedin",
                    quote=r.get("content", "")[:200],
                    verified=False,
                    page_title=r.get("title", "")
                ))
                return field
        
        return None
        
    except Exception as e:
        logger.error(f"LinkedIn finder failed for {company_name}: {e}")
        return None


# =============================================================================
# WEBSITE CONTENT EXTRACTOR
# =============================================================================

def extract_from_website(url: str, company_name: str) -> Dict[str, EnrichedField]:
    """
    Extract structured data from a company website.
    
    Fetches the website and uses Gemini to extract:
    - Description
    - Sector/Industry
    - Location
    - Product info
    - Tech stack mentions
    - Customer mentions
    
    Returns dict of EnrichedFields with verified quotes.
    """
    logger.info(f"📄 Extracting data from website: {url}")
    
    success, content, title = fetch_page_content(url)
    if not success:
        return {}
    
    # Use Gemini to extract structured data
    prompt = f"""Extract company information from this website content.
Company name: {company_name}
Website: {url}

Content:
{content[:15000]}

Extract the following. For each field, provide the EXACT quote from the content that supports it.
If a field is not found, set it to null.

Return JSON:
{{
    "description": {{
        "value": "company description",
        "quote": "exact text from content"
    }},
    "sector": {{
        "value": "industry/sector",
        "quote": "exact text mentioning sector"
    }},
    "location": {{
        "value": "city, country",
        "quote": "exact text mentioning location"
    }},
    "product_description": {{
        "value": "what they sell/do",
        "quote": "exact text describing product"
    }},
    "tech_stack": {{
        "value": "technologies mentioned",
        "quote": "exact text mentioning tech"
    }},
    "customers": {{
        "value": "customer names or types",
        "quote": "exact text mentioning customers"
    }}
}}

IMPORTANT: Only include fields where you found clear evidence in the content.
The quote must be an EXACT substring from the content above."""

    try:
        response = call_gemini(prompt, use_pro_model=False)
        data = parse_json_response(response)
        
        if not data:
            return {}
        
        results = {}
        for field_name, field_data in data.items():
            if field_data and isinstance(field_data, dict) and field_data.get("value"):
                value = field_data["value"]
                quote = field_data.get("quote", "")
                
                # Verify the quote exists in content
                verified, actual_quote = verify_content_match(content, quote)
                
                field = EnrichedField(value=value, confidence=0.0)
                field.add_source(SourceEvidence(
                    source_url=url,
                    source_type="website",
                    quote=actual_quote if verified else quote[:200],
                    verified=verified,
                    page_title=title
                ))
                results[field_name] = field
        
        return results
        
    except Exception as e:
        logger.error(f"Website extraction failed: {e}")
        return {}


# =============================================================================
# LINKEDIN CONTENT EXTRACTOR
# =============================================================================

def extract_from_linkedin(linkedin_url: str, company_name: str) -> Dict[str, EnrichedField]:
    """
    Extract structured data from LinkedIn company page via Tavily.
    
    Uses Tavily to get LinkedIn page content (we can't scrape directly).
    Extracts:
    - Employee count
    - Headquarters
    - Industry
    - Founded year
    - Company description
    """
    logger.info(f"📄 Extracting data from LinkedIn: {linkedin_url}")
    
    try:
        client = get_tavily_client()
        
        # Use Tavily to get LinkedIn page content
        results = client.search(
            query=f'site:linkedin.com "{company_name}" employees headquarters',
            search_depth="advanced",
            max_results=3,
            include_domains=["linkedin.com"]
        )
        
        if not results.get("results"):
            return {}
        
        # Combine content from LinkedIn results
        linkedin_content = ""
        for r in results["results"]:
            if "linkedin.com" in r.get("url", ""):
                linkedin_content += f"\n{r.get('title', '')}\n{r.get('content', '')}\n"
        
        if not linkedin_content:
            return {}
        
        # Use Gemini to extract structured data
        prompt = f"""Extract company information from this LinkedIn content.
Company name: {company_name}

LinkedIn Content:
{linkedin_content[:10000]}

Extract the following. For each field, provide the EXACT quote that supports it.

Return JSON:
{{
    "employee_count": {{
        "value": "number or range like '51-200'",
        "quote": "exact text mentioning employees"
    }},
    "location": {{
        "value": "headquarters city, country",
        "quote": "exact text mentioning location"
    }},
    "sector": {{
        "value": "industry",
        "quote": "exact text mentioning industry"
    }},
    "founded_year": {{
        "value": "year as string",
        "quote": "exact text mentioning founding"
    }},
    "description": {{
        "value": "company description",
        "quote": "exact text"
    }}
}}

Only include fields with clear evidence. Quote must be exact substring."""

        response = call_gemini(prompt, use_pro_model=False)
        data = parse_json_response(response)
        
        if not data:
            return {}
        
        results = {}
        for field_name, field_data in data.items():
            if field_data and isinstance(field_data, dict) and field_data.get("value"):
                value = field_data["value"]
                quote = field_data.get("quote", "")
                
                # Verify quote in content
                verified, actual_quote = verify_content_match(linkedin_content, quote)
                
                field = EnrichedField(value=value, confidence=0.0)
                field.add_source(SourceEvidence(
                    source_url=linkedin_url,
                    source_type="linkedin",
                    quote=actual_quote if verified else quote[:200],
                    verified=verified,
                    page_title=f"{company_name} LinkedIn"
                ))
                results[field_name] = field
        
        return results
        
    except Exception as e:
        logger.error(f"LinkedIn extraction failed: {e}")
        return {}


# =============================================================================
# FUNDING STAGE FINDER AGENT
# =============================================================================

def find_funding_stage(company_name: str, known_info: Dict = None) -> Optional[EnrichedField]:
    """
    Funding Stage Finder Agent — Search for company's funding stage.
    
    Searches Crunchbase, news articles, and funding databases to find:
    - Pre-seed, Seed, Series A, Series B, Series C, etc.
    
    Args:
        company_name: Name of the company
        known_info: Any known info (sector, location) to help disambiguate
    
    Returns:
        EnrichedField with verified funding stage, or None if not found
    """
    logger.info(f"🔍 Stage Finder: Searching for {company_name} funding stage")
    
    try:
        client = get_tavily_client()
        
        # Search for funding information
        query = f'"{company_name}" funding round series seed raised'
        if known_info:
            if known_info.get("location"):
                query += f' {known_info["location"]}'
        
        results = client.search(
            query=query,
            search_depth="advanced",
            max_results=5,
        )
        
        if not results.get("results"):
            logger.warning(f"No funding results for {company_name}")
            return None
        
        # Combine all content for analysis
        combined_content = ""
        source_urls = []
        for r in results["results"]:
            combined_content += f"\n{r.get('title', '')}\n{r.get('content', '')}\n"
            source_urls.append(r.get("url", ""))
        
        # Use Gemini to extract funding stage
        prompt = f"""Extract the funding stage for this company from the search results.
Company name: {company_name}

Search Results:
{combined_content[:10000]}

Identify the MOST RECENT funding stage. Look for terms like:
- Pre-seed, Seed, Angel
- Series A, Series B, Series C, Series D, Series E
- IPO, Public, Acquired

Return JSON:
{{
    "funding_stage": {{
        "value": "the stage (e.g., 'Series A', 'Seed', 'Series B')",
        "quote": "exact text mentioning the funding round",
        "amount": "funding amount if mentioned (e.g., '$5M')",
        "date": "when the round was announced if mentioned"
    }}
}}

If no funding information is found, return:
{{"funding_stage": null}}

IMPORTANT: The quote must be an EXACT substring from the content above."""

        response = call_gemini(prompt, use_pro_model=False)
        data = parse_json_response(response)
        
        if not data or not data.get("funding_stage"):
            return None
        
        stage_data = data["funding_stage"]
        value = stage_data.get("value", "")
        quote = stage_data.get("quote", "")
        
        if not value:
            return None
        
        # Normalize the stage value
        value_lower = value.lower().strip()
        normalized = None
        for stage in FUNDING_STAGES_ORDER:
            if stage in value_lower or value_lower in stage:
                normalized = stage.title()  # "series a" -> "Series A"
                break
        
        if not normalized:
            # Try to match common variations
            if "seed" in value_lower:
                normalized = "Seed"
            elif "pre-seed" in value_lower or "preseed" in value_lower:
                normalized = "Pre-Seed"
            elif "angel" in value_lower:
                normalized = "Seed"  # Treat angel as seed
            else:
                normalized = value  # Use as-is
        
        # Verify quote in content
        verified, actual_quote = verify_content_match(combined_content, quote)
        
        logger.info(f"✅ Found funding stage for {company_name}: {normalized}")
        
        field = EnrichedField(value=normalized, confidence=0.0)
        field.add_source(SourceEvidence(
            source_url=source_urls[0] if source_urls else "",
            source_type="news",
            quote=actual_quote if verified else quote[:200],
            verified=verified,
            page_title=f"{company_name} funding"
        ))
        
        # Add amount info to quote if available
        if stage_data.get("amount"):
            field.sources[0].quote += f" (Amount: {stage_data['amount']})"
        
        return field
        
    except Exception as e:
        logger.error(f"Stage finder failed for {company_name}: {e}")
        return None


def is_early_stage(funding_stage: str) -> bool:
    """
    Check if a funding stage is Series B or earlier.
    
    Returns True for: Pre-seed, Seed, Series A, Series B
    Returns False for: Series C, Series D, IPO, Public, etc.
    """
    if not funding_stage:
        return True  # Unknown stage passes filter (benefit of doubt)
    
    stage_lower = funding_stage.lower().strip()
    
    # Find position in order
    cutoff_idx = -1
    stage_idx = -1
    
    for i, stage in enumerate(FUNDING_STAGES_ORDER):
        if stage == EARLY_STAGE_CUTOFF:
            cutoff_idx = i
        if stage in stage_lower or stage_lower in stage:
            stage_idx = i
            break
    
    # If we can't determine the stage, pass the filter
    if stage_idx == -1:
        return True
    
    # Pass if stage is at or before cutoff
    return stage_idx <= cutoff_idx


# =============================================================================
# MAIN ENRICHMENT FUNCTION
# =============================================================================

def enrich_company(company_name: str, initial_data: Dict = None) -> CompanyEnrichment:
    """
    Full enrichment pipeline for a company.
    
    Runs 3 finder agents IN PARALLEL for speed:
    1. Website Finder Agent
    2. LinkedIn Finder Agent  
    3. Stage Finder Agent
    
    Then extracts data from found sources and merges with multi-source evidence.
    
    Args:
        company_name: Name of the company
        initial_data: Any initial data from search (sector, location hints)
    
    Returns:
        CompanyEnrichment with all verified data
    """
    logger.info(f"🚀 Starting parallel enrichment for: {company_name}")
    
    enrichment = CompanyEnrichment(company_name=company_name)
    initial_data = initial_data or {}
    
    # -------------------------------------------------------------------------
    # PARALLEL EXECUTION: Run all 3 finder agents simultaneously
    # This reduces enrichment time from ~9s (sequential) to ~3s (parallel)
    # -------------------------------------------------------------------------
    website_field = None
    linkedin_field = None
    stage_field = None
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        # Submit all 3 finder tasks
        futures = {
            executor.submit(find_company_website, company_name, initial_data): "website",
            executor.submit(find_company_linkedin, company_name, initial_data): "linkedin",
            executor.submit(find_funding_stage, company_name, initial_data): "stage",
        }
        
        # Collect results as they complete
        for future in as_completed(futures):
            agent_name = futures[future]
            try:
                result = future.result()
                if agent_name == "website":
                    website_field = result
                elif agent_name == "linkedin":
                    linkedin_field = result
                elif agent_name == "stage":
                    stage_field = result
                logger.info(f"  ✓ {agent_name} agent completed")
            except Exception as e:
                logger.error(f"  ✗ {agent_name} agent failed: {e}")
    
    # -------------------------------------------------------------------------
    # SEQUENTIAL: Extract data from found sources (depends on finder results)
    # -------------------------------------------------------------------------
    
    # Process website data
    if website_field:
        enrichment.website_url = website_field
        
        # Extract from website
        website_data = extract_from_website(website_field.value, company_name)
        
        # Store raw content for scoring
        success, content, _ = fetch_page_content(website_field.value)
        if success:
            enrichment.website_content = content
        
        # Merge website data
        for field_name, field_value in website_data.items():
            if hasattr(enrichment, field_name):
                existing = getattr(enrichment, field_name)
                if existing:
                    for source in field_value.sources:
                        existing.add_source(source)
                else:
                    setattr(enrichment, field_name, field_value)
    
    # Process LinkedIn data
    if linkedin_field:
        enrichment.linkedin_url = linkedin_field
        
        # Extract from LinkedIn
        linkedin_data = extract_from_linkedin(linkedin_field.value, company_name)
        
        # Store raw content for scoring
        enrichment.linkedin_content = str(linkedin_data)
        
        # Merge LinkedIn data (adds to existing fields)
        for field_name, field_value in linkedin_data.items():
            if hasattr(enrichment, field_name):
                existing = getattr(enrichment, field_name)
                if existing:
                    for source in field_value.sources:
                        existing.add_source(source)
                    if existing.value != field_value.value:
                        logger.info(f"Multi-source: {field_name} = '{existing.value}' (website) vs '{field_value.value}' (LinkedIn)")
                else:
                    setattr(enrichment, field_name, field_value)
    
    # Process funding stage
    if stage_field:
        enrichment.funding_stage = stage_field
    
    logger.info(f"✅ Enrichment complete for {company_name}")
    return enrichment


def enrich_search_results(
    search_results: List[SearchResult],
    max_employees: int = 100,
    mena_only: bool = True,
    early_stage_only: bool = True,
) -> Tuple[List[SearchResult], List[SearchResult], Dict[str, CompanyEnrichment]]:
    """
    Enrich all search results with website and LinkedIn data.
    
    Args:
        search_results: Companies from initial search
        max_employees: Maximum employee count filter
        mena_only: Only include MENA-headquartered companies
        early_stage_only: Only include Series B and earlier (default: True)
    
    Returns:
        (passed_filter, filtered_out, enrichments_dict)
    """
    # MENA_COUNTRIES is defined at module level
    
    passed = []
    filtered_out = []
    enrichments = {}
    
    for sr in search_results:
        logger.info(f"Enriching: {sr.name}")
        
        # Get initial hints from search result
        initial_data = {
            "sector": sr.sector if sr.sector != "Not Found" else None,
            "location": sr.location if sr.location != "Not Found" else None,
        }
        
        # Full enrichment
        enrichment = enrich_company(sr.name, initial_data)
        enrichments[sr.name] = enrichment
        
        # Update SearchResult with enriched data
        if enrichment.website_url:
            sr.website = enrichment.website_url.value
        
        if enrichment.location:
            sr.location = enrichment.location.value
        
        if enrichment.sector:
            sr.sector = enrichment.sector.value
        
        if enrichment.description:
            sr.description = enrichment.description.value
        
        if enrichment.founders and enrichment.founders.value:
            # Parse founders if it's a string
            founders_val = enrichment.founders.value
            if isinstance(founders_val, str):
                sr.founders = [f.strip() for f in founders_val.split(",")]
            elif isinstance(founders_val, list):
                sr.founders = founders_val
        
        # Store enrichment in grounded_evidence
        if not hasattr(sr, 'grounded_evidence') or sr.grounded_evidence is None:
            sr.grounded_evidence = {}
        sr.grounded_evidence["source_enrichment"] = enrichment.to_dict()
        
        # Apply filters
        passed_filters = True
        filter_reason = ""
        
        # Employee count filter
        if enrichment.employee_count:
            emp_val = enrichment.employee_count.value
            # Parse employee count
            emp_num = -1
            if isinstance(emp_val, int):
                emp_num = emp_val
            elif isinstance(emp_val, str):
                # Handle ranges like "51-200"
                numbers = re.findall(r'\d+', emp_val)
                if numbers:
                    emp_num = int(numbers[0])  # Use lower bound
            
            if emp_num > 0 and emp_num > max_employees:
                passed_filters = False
                filter_reason = f"Too large ({emp_num} employees > {max_employees})"
        
        # MENA location filter
        if mena_only and passed_filters:
            location = enrichment.location.value.lower() if enrichment.location else ""
            if location:
                is_mena = any(country in location for country in MENA_COUNTRIES)
                if not is_mena:
                    passed_filters = False
                    filter_reason = f"Not in MENA ({enrichment.location.value})"
        
        # Early stage filter (Series B and before)
        if early_stage_only and passed_filters:
            if enrichment.funding_stage:
                stage = enrichment.funding_stage.value
                if not is_early_stage(stage):
                    passed_filters = False
                    filter_reason = f"Too late stage ({stage} > Series B)"
        
        # Update SearchResult with funding stage
        if enrichment.funding_stage:
            sr.funding_stage = enrichment.funding_stage.value
        
        if passed_filters:
            passed.append(sr)
            logger.info(f"✓ {sr.name} passed filters")
        else:
            filtered_out.append(sr)
            logger.info(f"✗ {sr.name} filtered: {filter_reason}")
    
    logger.info(f"Enrichment complete: {len(passed)} passed, {len(filtered_out)} filtered")
    return passed, filtered_out, enrichments
