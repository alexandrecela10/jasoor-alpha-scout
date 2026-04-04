"""
Grounding Module — Deterministic validation for AI outputs.

This module provides 100% deterministic validation functions that verify
AI-generated claims against source data using exact string matching.
No LLM calls here — pure Python string operations.

Key principle: Every AI output must have PROOF from the source text.
If we can't find an exact match, the claim is flagged as "ungrounded".

Functions:
- find_exact_match: Find exact substring in source, return match + context
- validate_company_name: Verify company name appears in source
- validate_website_domain: Check if website domain matches company name
- validate_claim: Generic claim validation with exact match proof
- build_grounded_evidence: Create evidence object with deterministic proof
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class GroundedEvidence:
    """
    Proof that an AI claim is grounded in source data.
    
    This is the core data structure for absolute grounding.
    Every field extracted by AI should have one of these attached.
    
    match_type:
    - "exact": The exact string was found in the source
    - "partial": A significant portion was found (e.g., company name without suffix)
    - "none": No match found — this claim is UNGROUNDED
    
    The snippet fields show the ACTUAL text from the source,
    not what the AI claimed. This is the hard proof.
    """
    claim: str                          # What the AI claimed (e.g., "Byanat AI")
    claim_field: str                    # Which field this is (e.g., "company_name", "website")
    source_url: str                     # URL where we looked for evidence
    source_text: str                    # Full source text we searched in
    
    # Deterministic match results
    match_type: str = "none"            # "exact", "partial", "none"
    matched_text: str = ""              # The EXACT text found in source
    match_start: int = -1               # Character position where match starts
    match_end: int = -1                 # Character position where match ends
    
    # Context around the match (for display)
    context_before: str = ""            # 50 chars before the match
    context_after: str = ""             # 50 chars after the match
    
    # Validation result
    is_grounded: bool = False           # True only if match_type != "none"
    confidence: float = 0.0             # 1.0 for exact, 0.7 for partial, 0.0 for none
    validation_method: str = ""         # How we validated (e.g., "exact_substring_match")

    def to_dict(self) -> Dict:
        return {
            "claim": self.claim,
            "claim_field": self.claim_field,
            "source_url": self.source_url,
            "match_type": self.match_type,
            "matched_text": self.matched_text,
            "context_before": self.context_before,
            "context_after": self.context_after,
            "is_grounded": self.is_grounded,
            "confidence": self.confidence,
            "validation_method": self.validation_method,
        }

    def get_proof_snippet(self) -> str:
        """Return a formatted proof snippet showing the match in context."""
        if not self.is_grounded:
            return f"❌ NOT FOUND: '{self.claim}' not found in source"
        return f"✅ FOUND: ...{self.context_before}[{self.matched_text}]{self.context_after}..."


def find_exact_match(
    needle: str,
    haystack: str,
    case_sensitive: bool = False,
    context_chars: int = 50,
) -> Tuple[bool, str, int, int, str, str]:
    """
    Find exact substring match in text.
    
    Returns:
        (found, matched_text, start_pos, end_pos, context_before, context_after)
    
    This is the core deterministic function — no AI, just string search.
    """
    if not needle or not haystack:
        return (False, "", -1, -1, "", "")
    
    search_needle = needle if case_sensitive else needle.lower()
    search_haystack = haystack if case_sensitive else haystack.lower()
    
    pos = search_haystack.find(search_needle)
    
    if pos == -1:
        return (False, "", -1, -1, "", "")
    
    # Get the actual matched text (preserving original case)
    matched_text = haystack[pos:pos + len(needle)]
    
    # Get context
    context_start = max(0, pos - context_chars)
    context_end = min(len(haystack), pos + len(needle) + context_chars)
    
    context_before = haystack[context_start:pos].strip()
    context_after = haystack[pos + len(needle):context_end].strip()
    
    return (True, matched_text, pos, pos + len(needle), context_before, context_after)


def validate_company_name(
    company_name: str,
    source_text: str,
    source_url: str = "",
) -> GroundedEvidence:
    """
    Validate that a company name appears in the source text.
    
    Tries multiple matching strategies:
    1. Exact match (case-insensitive)
    2. First word match (for "Company AI" -> "Company")
    3. Without common suffixes (AI, Tech, Inc, etc.)
    
    Returns GroundedEvidence with deterministic proof.
    """
    evidence = GroundedEvidence(
        claim=company_name,
        claim_field="company_name",
        source_url=source_url,
        source_text=source_text[:500] if source_text else "",  # Truncate for storage
        validation_method="exact_substring_match",
    )
    
    if not company_name or not source_text:
        return evidence
    
    # Strategy 1: Exact match
    found, matched, start, end, before, after = find_exact_match(company_name, source_text)
    if found:
        evidence.match_type = "exact"
        evidence.matched_text = matched
        evidence.match_start = start
        evidence.match_end = end
        evidence.context_before = before
        evidence.context_after = after
        evidence.is_grounded = True
        evidence.confidence = 1.0
        return evidence
    
    # Strategy 2: First word match (for multi-word names)
    words = company_name.split()
    if len(words) > 1:
        first_word = words[0]
        if len(first_word) >= 3:  # Avoid matching short words like "AI"
            found, matched, start, end, before, after = find_exact_match(first_word, source_text)
            if found:
                evidence.match_type = "partial"
                evidence.matched_text = matched
                evidence.match_start = start
                evidence.match_end = end
                evidence.context_before = before
                evidence.context_after = after
                evidence.is_grounded = True
                evidence.confidence = 0.7
                evidence.validation_method = "first_word_match"
                return evidence
    
    # Strategy 3: Without common suffixes
    suffixes = [" ai", " tech", " inc", " ltd", " llc", " co", " labs", " io"]
    clean_name = company_name.lower()
    for suffix in suffixes:
        if clean_name.endswith(suffix):
            clean_name = clean_name[:-len(suffix)].strip()
            break
    
    if clean_name and len(clean_name) >= 3 and clean_name != company_name.lower():
        found, matched, start, end, before, after = find_exact_match(clean_name, source_text)
        if found:
            evidence.match_type = "partial"
            evidence.matched_text = matched
            evidence.match_start = start
            evidence.match_end = end
            evidence.context_before = before
            evidence.context_after = after
            evidence.is_grounded = True
            evidence.confidence = 0.6
            evidence.validation_method = "suffix_removed_match"
            return evidence
    
    # No match found
    evidence.match_type = "none"
    evidence.is_grounded = False
    evidence.confidence = 0.0
    return evidence


def validate_website_domain(
    claimed_website: str,
    company_name: str,
    source_text: str = "",
    source_url: str = "",
) -> GroundedEvidence:
    """
    Validate that a website URL is plausibly correct for a company.
    
    Checks:
    1. Domain contains company name (or variation)
    2. Website URL appears in source text
    3. Domain is not a generic site (linkedin, crunchbase, etc.)
    
    Returns GroundedEvidence with deterministic proof.
    """
    evidence = GroundedEvidence(
        claim=claimed_website,
        claim_field="website",
        source_url=source_url,
        source_text=source_text[:500] if source_text else "",
        validation_method="domain_validation",
    )
    
    if not claimed_website or claimed_website == "Not Found":
        evidence.match_type = "none"
        return evidence
    
    # Parse the domain
    try:
        parsed = urlparse(claimed_website)
        domain = parsed.netloc.lower().replace("www.", "")
    except Exception:
        evidence.match_type = "none"
        return evidence
    
    # Check for generic domains (these are NOT company websites)
    generic_domains = [
        "linkedin.com", "crunchbase.com", "twitter.com", "facebook.com",
        "instagram.com", "youtube.com", "medium.com", "github.com",
        "techcrunch.com", "forbes.com", "bloomberg.com", "reuters.com",
        "wamda.com", "magnitt.com", "zawya.com",
    ]
    if any(generic in domain for generic in generic_domains):
        evidence.match_type = "none"
        evidence.is_grounded = False
        evidence.confidence = 0.0
        evidence.validation_method = "rejected_generic_domain"
        return evidence
    
    # Check 1: Does the domain contain the company name?
    company_clean = re.sub(r'[^a-z0-9]', '', company_name.lower())
    domain_clean = re.sub(r'[^a-z0-9]', '', domain)
    
    if company_clean and len(company_clean) >= 3:
        # Check if company name is in domain
        if company_clean in domain_clean:
            evidence.match_type = "exact"
            evidence.matched_text = domain
            evidence.is_grounded = True
            evidence.confidence = 0.9
            evidence.validation_method = "company_name_in_domain"
            return evidence
        
        # Check first word of company name
        first_word = re.sub(r'[^a-z0-9]', '', company_name.split()[0].lower())
        if first_word and len(first_word) >= 3 and first_word in domain_clean:
            evidence.match_type = "partial"
            evidence.matched_text = domain
            evidence.is_grounded = True
            evidence.confidence = 0.7
            evidence.validation_method = "company_first_word_in_domain"
            return evidence
    
    # Check 2: Does the website URL appear in the source text?
    if source_text:
        # Try full URL
        found, matched, start, end, before, after = find_exact_match(claimed_website, source_text)
        if found:
            evidence.match_type = "exact"
            evidence.matched_text = matched
            evidence.match_start = start
            evidence.match_end = end
            evidence.context_before = before
            evidence.context_after = after
            evidence.is_grounded = True
            evidence.confidence = 1.0
            evidence.validation_method = "url_found_in_source"
            return evidence
        
        # Try just the domain
        found, matched, start, end, before, after = find_exact_match(domain, source_text)
        if found:
            evidence.match_type = "partial"
            evidence.matched_text = matched
            evidence.match_start = start
            evidence.match_end = end
            evidence.context_before = before
            evidence.context_after = after
            evidence.is_grounded = True
            evidence.confidence = 0.8
            evidence.validation_method = "domain_found_in_source"
            return evidence
    
    # No validation possible
    evidence.match_type = "none"
    evidence.is_grounded = False
    evidence.confidence = 0.0
    evidence.validation_method = "no_validation_possible"
    return evidence


def validate_claim(
    claim: str,
    claim_field: str,
    source_text: str,
    source_url: str = "",
) -> GroundedEvidence:
    """
    Generic claim validation — find exact match of claim in source.
    
    Use this for any AI-generated text that should appear in the source:
    - Descriptions
    - Founder names
    - Funding amounts
    - Locations
    - etc.
    """
    evidence = GroundedEvidence(
        claim=claim,
        claim_field=claim_field,
        source_url=source_url,
        source_text=source_text[:500] if source_text else "",
        validation_method="exact_substring_match",
    )
    
    if not claim or not source_text or claim in ["Not Found", "N/A", ""]:
        evidence.match_type = "none"
        return evidence
    
    # Try exact match
    found, matched, start, end, before, after = find_exact_match(claim, source_text)
    if found:
        evidence.match_type = "exact"
        evidence.matched_text = matched
        evidence.match_start = start
        evidence.match_end = end
        evidence.context_before = before
        evidence.context_after = after
        evidence.is_grounded = True
        evidence.confidence = 1.0
        return evidence
    
    # Try matching key phrases (for longer claims)
    if len(claim) > 20:
        # Extract key phrases (words 4+ chars)
        words = [w for w in claim.split() if len(w) >= 4]
        matches_found = 0
        for word in words[:5]:  # Check first 5 significant words
            if word.lower() in source_text.lower():
                matches_found += 1
        
        if matches_found >= 2:
            evidence.match_type = "partial"
            evidence.matched_text = f"{matches_found} key words found"
            evidence.is_grounded = True
            evidence.confidence = min(0.5 + (matches_found * 0.1), 0.8)
            evidence.validation_method = "key_phrase_match"
            return evidence
    
    # No match
    evidence.match_type = "none"
    evidence.is_grounded = False
    evidence.confidence = 0.0
    return evidence


def validate_all_fields(
    extracted_data: Dict,
    source_text: str,
    source_url: str = "",
) -> Dict[str, GroundedEvidence]:
    """
    Validate all fields in an extracted company record.
    
    Returns a dict mapping field names to their GroundedEvidence.
    """
    evidence_map = {}
    
    # Company name — special handling
    if "name" in extracted_data:
        evidence_map["name"] = validate_company_name(
            extracted_data["name"], source_text, source_url
        )
    
    # Website — special handling
    if "website" in extracted_data:
        evidence_map["website"] = validate_website_domain(
            extracted_data["website"],
            extracted_data.get("name", ""),
            source_text,
            source_url,
        )
    
    # All other fields — generic validation
    for field_name in ["description", "location", "sector", "funding_stage", "funding_amount"]:
        if field_name in extracted_data:
            evidence_map[field_name] = validate_claim(
                str(extracted_data[field_name]),
                field_name,
                source_text,
                source_url,
            )
    
    # Founders — validate each name
    if "founders" in extracted_data and isinstance(extracted_data["founders"], list):
        founder_evidences = []
        for founder in extracted_data["founders"]:
            ev = validate_claim(founder, "founder_name", source_text, source_url)
            founder_evidences.append(ev)
        # Aggregate: grounded if at least one founder is found
        if founder_evidences:
            best = max(founder_evidences, key=lambda e: e.confidence)
            evidence_map["founders"] = best
    
    return evidence_map


def compute_grounding_score(evidence_map: Dict[str, GroundedEvidence]) -> float:
    """
    Compute overall grounding score for a company.
    
    Returns 0.0 to 1.0 based on how many fields are grounded.
    Critical fields (name, website) are weighted higher.
    """
    if not evidence_map:
        return 0.0
    
    weights = {
        "name": 3.0,        # Critical — must be grounded
        "website": 2.0,     # Important — often wrong
        "description": 1.0,
        "location": 1.0,
        "sector": 1.0,
        "funding_stage": 0.5,
        "funding_amount": 0.5,
        "founders": 1.0,
    }
    
    total_weight = 0.0
    weighted_score = 0.0
    
    for field, evidence in evidence_map.items():
        weight = weights.get(field, 1.0)
        total_weight += weight
        weighted_score += weight * evidence.confidence
    
    return weighted_score / total_weight if total_weight > 0 else 0.0
