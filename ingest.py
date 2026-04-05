"""
Ingest Module — Mode 3: Score inbound startup candidates.

This module handles extracting structured company data from:
1. Simulated pitchdeck/website data (for demo purposes)
2. Company website URL (crawled by Tavily, extracted by Gemini)
3. Raw pitchdeck text pasted by user

Later, this module will connect directly to the VC fund's deal filing system.
The SearchResult objects it produces feed directly into the same scoring pipeline
used by Modes 1 and 2 — no changes needed downstream.
"""

import logging
import os
from typing import List, Optional

from tavily import TavilyClient

from models import SearchResult
from llm_client import call_gemini, parse_json_response
from tracing import create_trace

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Simulated Inbound Companies
# ---------------------------------------------------------------------------
# These 4 companies represent realistic MENA startup pitches.
# Labelled as SIMULATED so the analyst knows they are demo data.
# A real integration with the fund's filing system will replace this.

SIMULATED_INBOUND: List[SearchResult] = [
    SearchResult(
        name="Halio",
        description="AI-powered energy management platform that reduces commercial building energy costs by 30% using machine learning and IoT sensors",
        website="https://halio.io",
        source_url="SIMULATED — pitchdeck submission",
        source_snippet=(
            "Halio uses machine learning to reduce energy costs by 30% for commercial buildings. "
            "Deployed in 12 buildings across Dubai and Riyadh. "
            "Current ARR: $180K, target $1M by end of year. "
            "Founder: Ahmed Al-Rashid, ex-Siemens energy systems engineer (8 years)."
        ),
        location="UAE / Saudi Arabia / GCC",
        sector="Climate Tech / PropTech / AI",
        founders=["Ahmed Al-Rashid", "Sarah Chen"],
        founders_linkedin=[
            "https://linkedin.com/in/ahmed-al-rashid",
            "https://linkedin.com/in/sarah-chen",
        ],
        funding_stage="Pre-seed",
        funding_amount="$500K",
    ),
    SearchResult(
        name="Carebot",
        description="AI-powered patient triage and remote monitoring platform for clinics in Saudi Arabia, reducing wait times by 40%",
        website="https://carebot.sa",
        source_url="SIMULATED — pitchdeck submission",
        source_snippet=(
            "Carebot reduces patient wait times by 40% using AI triage. "
            "Pilots with 3 clinics in Riyadh, 1,200 patients served monthly. "
            "SaaS model: $800/clinic/month. Founder: Dr. Khalid Al-Otaibi, "
            "ex-Johns Hopkins trained physician with 10 years clinical experience."
        ),
        location="Saudi Arabia / GCC",
        sector="HealthTech / AI",
        founders=["Dr. Khalid Al-Otaibi"],
        founders_linkedin=["https://linkedin.com/in/khalid-al-otaibi"],
        funding_stage="Pre-seed",
        funding_amount="$300K",
    ),
    SearchResult(
        name="Naqla",
        description="B2B last-mile logistics marketplace connecting SMEs to verified freight carriers across Egypt and Saudi Arabia",
        website="https://naqla.io",
        source_url="SIMULATED — pitchdeck submission",
        source_snippet=(
            "Naqla connects 500+ SMEs with 200+ verified freight carriers. "
            "$2M GMV in first 6 months of operations. "
            "Expanding from Egypt to Saudi Arabia Q3 2026. "
            "Founders: Omar Farouk (ex-Aramex logistics ops) and Nadia Hassan (ex-Uber Eats MENA)."
        ),
        location="Egypt / Saudi Arabia / MENA",
        sector="Logistics / B2B Marketplace",
        founders=["Omar Farouk", "Nadia Hassan"],
        founders_linkedin=[
            "https://linkedin.com/in/omar-farouk-logistics",
            "https://linkedin.com/in/nadia-hassan-mena",
        ],
        funding_stage="Seed",
        funding_amount="$1.5M",
    ),
    SearchResult(
        name="Tarbiyah",
        description="AI-adaptive Arabic-language K-12 EdTech platform with 85% student retention and 3x improvement in test scores",
        website="https://tarbiyah.ai",
        source_url="SIMULATED — pitchdeck submission",
        source_snippet=(
            "Tarbiyah serves 15,000 students across GCC with AI-powered Arabic curriculum. "
            "85% retention rate, 3x improvement in standardised test scores. "
            "B2B2C: sold to schools, used by students and parents. "
            "Founders: Lina Al-Sabah (ex-Google Education) and Majed Nasser (PhD in NLP, Arabic AI)."
        ),
        location="Saudi Arabia / UAE / GCC",
        sector="EdTech / AI",
        founders=["Lina Al-Sabah", "Majed Nasser"],
        founders_linkedin=[
            "https://linkedin.com/in/lina-al-sabah",
            "https://linkedin.com/in/majed-nasser-nlp",
        ],
        funding_stage="Seed",
        funding_amount="$2M",
    ),
]


def get_simulated_inbound() -> List[SearchResult]:
    """Return the simulated inbound candidates for demo purposes."""
    return list(SIMULATED_INBOUND)


def extract_company_from_website(url: str, trace=None) -> Optional[SearchResult]:
    """
    Crawl a company's website using Tavily and extract structured data via Gemini.

    This is the same extraction approach used in the main search pipeline,
    applied to a specific website URL provided by the analyst.

    Returns None if extraction fails or URL is unreachable.
    """
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        logger.error("TAVILY_API_KEY not set")
        return None

    try:
        # Step 1: Use Tavily to crawl the website
        client = TavilyClient(api_key=api_key)
        result = client.search(
            query=f"company information about {url}",
            search_depth="advanced",
            max_results=3,
            include_domains=[url.replace("https://", "").replace("http://", "").split("/")[0]],
        )
        raw_results = result.get("results", [])
        if not raw_results:
            logger.warning(f"No content found for {url}")
            return None

        # Combine snippets from the crawl
        content = "\n\n".join([
            f"URL: {r.get('url', '')}\nTitle: {r.get('title', '')}\nContent: {r.get('content', '')[:1000]}"
            for r in raw_results
        ])

        # Step 2: Use Gemini to extract structured company data
        prompt = f"""Extract structured company data from this website content.

WEBSITE: {url}
CONTENT:
{content}

Extract the following and return as JSON:
{{
  "name": "Company name",
  "description": "One-line company description",
  "website": "{url}",
  "source_url": "{url}",
  "source_snippet": "Most relevant quote about what the company does",
  "location": "Country or region (e.g., UAE, Saudi Arabia, Egypt)",
  "sector": "Industry sector",
  "founders": ["Founder name 1", "Founder name 2"],
  "founders_linkedin": [],
  "funding_stage": "Seed / Series A / Pre-seed / etc. or Not Found",
  "funding_amount": "$X million or Not Found",
  "employee_count": "Number of employees if mentioned, else Not Found"
}}

RULES:
- Only extract what is explicitly stated on the website.
- If a field is not found, use "Not Found".
- Do NOT invent founder names or funding data.

Return ONLY the JSON object, no other text."""

        response = call_gemini(
            prompt=prompt,
            trace=trace,
            span_name="extract_from_website",
            metadata={"url": url},
            use_pro_model=True,
        )
        data = parse_json_response(response)
        if not isinstance(data, dict) or "name" not in data:
            logger.warning(f"Unexpected extraction result for {url}: {data}")
            return None

        return SearchResult(
            name=data.get("name", "Unknown"),
            description=data.get("description", "Not Found"),
            website=data.get("website", url),
            source_url=data.get("source_url", url),
            source_snippet=data.get("source_snippet", ""),
            location=data.get("location", "Not Found"),
            sector=data.get("sector", "Not Found"),
            founders=data.get("founders", []),
            founders_linkedin=data.get("founders_linkedin", []),
            funding_stage=data.get("funding_stage", "Not Found"),
            funding_amount=data.get("funding_amount", "Not Found"),
            employee_count=data.get("employee_count", "Not Found"),
        )

    except Exception as e:
        logger.error(f"Website extraction failed for {url}: {e}")
        return None


def extract_company_from_text(company_name: str, pitchdeck_text: str, trace=None) -> Optional[SearchResult]:
    """
    Extract structured company data from pasted pitchdeck text using Gemini.

    The analyst pastes raw text from a pitchdeck or email pitch.
    Gemini extracts structured data for the scoring pipeline.
    """
    if not pitchdeck_text.strip():
        return None

    prompt = f"""Extract structured company data from this pitchdeck or pitch text.

COMPANY NAME: {company_name}
PITCH TEXT:
{pitchdeck_text[:3000]}

Extract the following and return as JSON:
{{
  "name": "{company_name}",
  "description": "One-line company description based on the pitch",
  "website": "Company website if mentioned, else Not Found",
  "source_url": "INBOUND — pitchdeck",
  "source_snippet": "Most important quote from the pitch about what they do",
  "location": "Country or region (e.g., UAE, Saudi Arabia, Egypt)",
  "sector": "Industry sector",
  "founders": ["Founder name 1", "Founder name 2"],
  "founders_linkedin": [],
  "funding_stage": "Seed / Series A / Pre-seed or Not Found",
  "funding_amount": "$X million or Not Found",
  "employee_count": "Number of employees/team size if mentioned, else Not Found"
}}

RULES:
- Only extract what is explicitly stated in the pitch text.
- If a field is not found, use "Not Found".
- Do NOT invent information not in the text.

Return ONLY the JSON object, no other text."""

    try:
        response = call_gemini(
            prompt=prompt,
            trace=trace,
            span_name="extract_from_pitchdeck",
            metadata={"company": company_name},
            use_pro_model=True,
        )
        data = parse_json_response(response)
        if not isinstance(data, dict):
            return None

        return SearchResult(
            name=data.get("name", company_name),
            description=data.get("description", "Not Found"),
            website=data.get("website", "Not Found"),
            source_url=data.get("source_url", "INBOUND — pitchdeck"),
            source_snippet=data.get("source_snippet", pitchdeck_text[:200]),
            location=data.get("location", "Not Found"),
            sector=data.get("sector", "Not Found"),
            founders=data.get("founders", []),
            founders_linkedin=data.get("founders_linkedin", []),
            funding_stage=data.get("funding_stage", "Not Found"),
            funding_amount=data.get("funding_amount", "Not Found"),
            employee_count=data.get("employee_count", "Not Found"),
        )

    except Exception as e:
        logger.error(f"Pitchdeck extraction failed for {company_name}: {e}")
        return None
