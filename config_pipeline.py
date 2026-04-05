"""
Pipeline Configuration — Reusable scoring dimensions, signals, and defaults.

This module contains configuration that can be reused across different products:
- Due Diligence Tool
- Portfolio Augmentation
- Competitor Analysis
- Any other product using the search + score pipeline

Product-specific data (portfolio companies, MENA benchmarks) stays in config.py.

USAGE:
    from config_pipeline import SCORING_DIMENSIONS, OBJECTIVE_SIGNALS, DEFAULT_SOURCES
    
    # Or import specific dimension sets for different products:
    from config_pipeline import VC_DEAL_FLOW_DIMENSIONS, DUE_DILIGENCE_DIMENSIONS
"""

# ---------------------------------------------------------------------------
# Scoring Dimensions — VC Deal Flow (Default)
# ---------------------------------------------------------------------------
# These are the 4 axes we score each target company on (1-5 scale).
# The user can adjust the weights in the UI to prioritize what matters most.
#
# "prompt_guidance" tells Gemini what to look for when scoring each dimension.
# This keeps scoring consistent and grounded.

VC_DEAL_FLOW_DIMENSIONS = {
    "offer_power": {
        "label": "Offer Power",
        "description": "How compelling is the value proposition? Uses Hormozi's Value Equation.",
        "prompt_guidance": (
            "Score using Hormozi's Value Equation: "
            "Value = (Dream Outcome × Likelihood) / (Time × Effort). "
            "Score 5: High outcome + high likelihood + low time + low effort. "
            "Score 1: Low outcome or low likelihood or high time + high effort. "
            "Look for: clear pain point, measurable ROI, speed of deployment."
        ),
        "default_weight": 0.25,
    },
    "sales_ability": {
        "label": "Sales Ability",
        "description": "Evidence of traction, revenue, partnerships, or customer acquisition.",
        "prompt_guidance": (
            "Look for: paying customers, named partnerships, revenue figures, "
            "growth rate mentions, press coverage of deals, B2B vs B2C model. "
            "Score 5: Clear revenue traction + named enterprise customers. "
            "Score 1: No evidence of any customers or traction."
        ),
        "default_weight": 0.25,
    },
    "tech_moat": {
        "label": "Tech Moat",
        "description": "Defensibility of the technology — patents, proprietary data, network effects.",
        "prompt_guidance": (
            "Look for: patents, proprietary datasets, unique algorithms, "
            "network effects, high switching costs, regulatory moats. "
            "Score 5: Strong IP + proprietary data + high switching costs. "
            "Score 1: Easily replicable with off-the-shelf tools."
        ),
        "default_weight": 0.25,
    },
    "founder_strength": {
        "label": "Founder Strength",
        "description": "Founder's track record, domain expertise, and ability to execute.",
        "prompt_guidance": (
            "Look for: previous exits, years in industry, technical vs sales background, "
            "education, public speaking, advisor network, co-founder complement. "
            "Score 5: Serial entrepreneur with exits + deep domain expertise. "
            "Score 1: First-time founder with no visible domain experience. "
            "IMPORTANT: If founder info is not in the sources, return 'N/A'."
        ),
        "default_weight": 0.25,
    },
}

# Default scoring dimensions (alias for backward compatibility)
SCORING_DIMENSIONS = VC_DEAL_FLOW_DIMENSIONS


# ---------------------------------------------------------------------------
# Due Diligence Dimensions (Example for reuse)
# ---------------------------------------------------------------------------
# Different scoring dimensions for a due diligence product.
# Pass this to score_company(dimension_config=DUE_DILIGENCE_DIMENSIONS)

DUE_DILIGENCE_DIMENSIONS = {
    "team_background": {
        "label": "Team Background",
        "description": "Verification of founder claims, employment history, education.",
        "prompt_guidance": (
            "Verify: LinkedIn profiles match claims, employment dates, education credentials, "
            "previous company outcomes, any red flags or discrepancies. "
            "Score 5: All claims verified, strong track record. "
            "Score 1: Unverifiable claims or significant discrepancies."
        ),
        "default_weight": 0.30,
    },
    "ip_validation": {
        "label": "IP Validation",
        "description": "Patent filings, trademark registrations, technology ownership.",
        "prompt_guidance": (
            "Look for: USPTO/EPO patent filings, trademark registrations, "
            "open source dependencies, technology licensing agreements. "
            "Score 5: Strong IP portfolio with granted patents. "
            "Score 1: No IP protection, heavy reliance on open source."
        ),
        "default_weight": 0.25,
    },
    "customer_references": {
        "label": "Customer References",
        "description": "Quality and verifiability of customer claims.",
        "prompt_guidance": (
            "Verify: Named customers exist, contract values, customer testimonials, "
            "case studies with measurable outcomes, reference availability. "
            "Score 5: Multiple verifiable enterprise customers with case studies. "
            "Score 1: No verifiable customer references."
        ),
        "default_weight": 0.25,
    },
    "financial_health": {
        "label": "Financial Health",
        "description": "Runway, burn rate, revenue trajectory, cap table cleanliness.",
        "prompt_guidance": (
            "Look for: revenue figures, growth rate, burn rate, runway, "
            "previous funding rounds, investor quality, cap table structure. "
            "Score 5: Strong revenue growth, 18+ months runway, clean cap table. "
            "Score 1: High burn, short runway, messy cap table."
        ),
        "default_weight": 0.20,
    },
}


# ---------------------------------------------------------------------------
# 2x2 Matrix Axis Options
# ---------------------------------------------------------------------------
# These are the toggleable axes for the Plotly scatter plot.
# Users pick any two for X and Y to visualize the portfolio.

MATRIX_AXES = [
    "offer_power",
    "sales_ability",
    "tech_moat",
    "founder_strength",
    "expected_cac",   # Estimated Customer Acquisition Cost (from AI analysis)
    "expected_ltv",   # Estimated Lifetime Value (from AI analysis)
]


# ---------------------------------------------------------------------------
# Default Search Sources
# ---------------------------------------------------------------------------
# These are the websites we tell Tavily to prioritize when searching.
# The user can edit this list in the UI.
# Why these? They're the most reliable English-language sources for MENAT startups.

DEFAULT_SOURCES = [
    # MENA-specific startup sources (guaranteed MENA focus)
    "menabytes.com",        # MENA startup news (funding rounds, launches)
    "wamda.com",            # MENA entrepreneurship platform
    "magnitt.com",          # MENA & Africa startup data platform
    "zawya.com",            # MENA business intelligence
    "arabnet.me",           # Arab tech & startup ecosystem
    "forbesmiddleeast.com", # Forbes Middle East
    "gulfbusiness.com",     # Gulf business news
    "arabianbusiness.com",  # Arabian business news
    "thenationalnews.com",  # UAE national news (business section)
    # Crunchbase MENA hub (filtered to MENA HQ companies)
    "crunchbase.com/hub/middle-east-and-north-africa-startups",
]


# ---------------------------------------------------------------------------
# Default Exclusion Keywords
# ---------------------------------------------------------------------------
# Keywords to exclude from search results. VC analysts may want to avoid
# certain types of news (e.g., fundraising = opportunity already gone).

DEFAULT_EXCLUSIONS = [
    # Uncomment to exclude fundraising news by default
    # "raises", "raised", "funding round", "secures funding", "closes round",
]


# ---------------------------------------------------------------------------
# Objective Signals — Keywords for Two-Pass Scoring
# ---------------------------------------------------------------------------
# These are the keywords and patterns used in Pass 1 (signal detection).
# VC Analysts can adjust these over time to improve scoring accuracy.
#
# Structure: { dimension_key: { sub_component: { signal_name: [keywords] } } }
# - "weight": Relative importance of this signal (0.0 - 1.0)
# - "inverse": If True, presence is negative (e.g., "long timeline" is bad)

OBJECTIVE_SIGNALS = {
    # -------------------------------------------------------------------------
    # OFFER POWER — Hormozi Value Equation
    # -------------------------------------------------------------------------
    "offer_power": {
        "dream_outcome": {
            "transformation_claims": {
                "keywords": ["transform", "revolutionize", "eliminate", "automate 100%", "completely replace"],
                "weight": 1.0,
                "inverse": False,
                "description": "Claims of complete transformation",
            },
            "quantified_value": {
                "keywords": ["10x", "100x", "save $", "increase revenue by", "reduce cost by", "% improvement"],
                "weight": 1.0,
                "inverse": False,
                "description": "Specific quantified benefits",
            },
            "pain_elimination": {
                "keywords": ["no more", "never again", "eliminate", "remove friction", "solve"],
                "weight": 0.8,
                "inverse": False,
                "description": "Addresses significant pain points",
            },
        },
        "perceived_likelihood": {
            "case_studies": {
                "keywords": ["case study", "success story", "customer achieved", "results for"],
                "weight": 1.0,
                "inverse": False,
                "description": "Documented customer success",
            },
            "social_proof": {
                "keywords": ["testimonial", "review", "trusted by", "used by", "customers include"],
                "weight": 0.9,
                "inverse": False,
                "description": "Third-party validation",
            },
            "guarantees": {
                "keywords": ["guaranteed", "money back", "risk-free", "proven", "track record"],
                "weight": 0.8,
                "inverse": False,
                "description": "Risk reduction mechanisms",
            },
        },
        "time_delay": {
            "instant_value": {
                "keywords": ["instant", "immediate", "real-time", "same day", "within minutes"],
                "weight": 1.0,
                "inverse": False,
                "description": "Very fast time to value",
            },
            "quick_implementation": {
                "keywords": ["quick setup", "get started in", "onboarding in days", "within hours"],
                "weight": 0.8,
                "inverse": False,
                "description": "Fast implementation",
            },
            "long_timeline": {
                "keywords": ["6 months", "12 months", "multi-year", "long-term implementation"],
                "weight": 1.0,
                "inverse": True,
                "description": "Slow time to value",
            },
        },
        "effort_required": {
            "low_effort": {
                "keywords": ["no-code", "plug and play", "one-click", "fully managed", "turnkey", "zero config"],
                "weight": 1.0,
                "inverse": False,
                "description": "Minimal customer effort",
            },
            "self_service": {
                "keywords": ["self-service", "automated", "AI-powered", "hands-off"],
                "weight": 0.8,
                "inverse": False,
                "description": "Automated experience",
            },
            "high_effort": {
                "keywords": ["custom implementation", "requires integration", "professional services", "consulting required"],
                "weight": 1.0,
                "inverse": True,
                "description": "Significant customer effort",
            },
        },
    },
    
    # -------------------------------------------------------------------------
    # SALES ABILITY — Lead Generation + Conversion
    # -------------------------------------------------------------------------
    "sales_ability": {
        "inbound_lead_gen": {
            "content_marketing": {
                "keywords": ["blog", "content", "thought leadership", "whitepaper", "ebook", "webinar"],
                "weight": 0.8,
                "inverse": False,
                "description": "Content-driven lead gen",
            },
            "seo_organic": {
                "keywords": ["organic growth", "SEO", "search ranking", "inbound", "viral"],
                "weight": 0.9,
                "inverse": False,
                "description": "Search and organic traffic",
            },
            "community_social": {
                "keywords": ["community", "followers", "social media", "newsletter", "subscribers"],
                "weight": 0.7,
                "inverse": False,
                "description": "Community-driven growth",
            },
            "pr_media": {
                "keywords": ["featured in", "press coverage", "media mention", "podcast", "interview"],
                "weight": 0.8,
                "inverse": False,
                "description": "Earned media presence",
            },
        },
        "outbound_lead_gen": {
            "sales_team": {
                "keywords": ["sales team", "account executive", "SDR", "BDR", "sales force"],
                "weight": 1.0,
                "inverse": False,
                "description": "Dedicated sales organization",
            },
            "partnerships": {
                "keywords": ["partnership", "channel partner", "reseller", "distribution", "alliance"],
                "weight": 0.9,
                "inverse": False,
                "description": "Partner-driven sales",
            },
            "enterprise_sales": {
                "keywords": ["enterprise", "B2B", "Fortune 500", "large accounts", "strategic accounts"],
                "weight": 0.8,
                "inverse": False,
                "description": "Enterprise sales motion",
            },
        },
        "conversion_ability": {
            "named_customers": {
                "keywords": ["customers include", "trusted by", "used by", "client list"],
                "weight": 1.0,
                "inverse": False,
                "description": "Named customer references",
            },
            "revenue_evidence": {
                "keywords": ["revenue", "ARR", "MRR", "paying customers", "closed deal", "contract"],
                "weight": 1.0,
                "inverse": False,
                "description": "Revenue traction",
            },
            "conversion_metrics": {
                "keywords": ["conversion rate", "% conversion", "close rate", "win rate"],
                "weight": 0.9,
                "inverse": False,
                "description": "Conversion metrics",
            },
            "retention": {
                "keywords": ["retention", "churn", "NRR", "renewal", "expansion"],
                "weight": 0.8,
                "inverse": False,
                "description": "Customer retention evidence",
            },
        },
    },
    
    # -------------------------------------------------------------------------
    # TECH MOAT — Defensibility
    # -------------------------------------------------------------------------
    "tech_moat": {
        "patents_ip": {
            "patents": {
                "keywords": ["patent", "patented", "patent pending", "IP portfolio", "intellectual property"],
                "weight": 1.0,
                "inverse": False,
                "description": "Patent protection",
            },
            "trade_secrets": {
                "keywords": ["proprietary", "trade secret", "proprietary algorithm", "secret sauce"],
                "weight": 0.8,
                "inverse": False,
                "description": "Trade secret protection",
            },
        },
        "data_moat": {
            "proprietary_data": {
                "keywords": ["proprietary data", "unique dataset", "trained on", "data points", "data lake"],
                "weight": 1.0,
                "inverse": False,
                "description": "Unique data assets",
            },
            "data_flywheel": {
                "keywords": ["data flywheel", "more data", "improves with usage", "learning system", "gets smarter"],
                "weight": 1.0,
                "inverse": False,
                "description": "Self-improving data loop",
            },
            "user_generated_data": {
                "keywords": ["user-generated", "crowdsourced", "community data", "user contributions"],
                "weight": 0.7,
                "inverse": False,
                "description": "User-contributed data",
            },
        },
        "network_effects": {
            "platform_marketplace": {
                "keywords": ["marketplace", "platform", "two-sided", "multi-sided", "ecosystem"],
                "weight": 1.0,
                "inverse": False,
                "description": "Platform business model",
            },
            "network_effect_claims": {
                "keywords": ["network effect", "more users", "better with scale", "viral", "word of mouth"],
                "weight": 1.0,
                "inverse": False,
                "description": "Explicit network effects",
            },
            "community": {
                "keywords": ["community of", "user community", "developer community", "active users"],
                "weight": 0.7,
                "inverse": False,
                "description": "Community-driven growth",
            },
        },
        "switching_costs": {
            "integration_depth": {
                "keywords": ["integrated with", "API", "embedded", "workflow", "system of record"],
                "weight": 1.0,
                "inverse": False,
                "description": "Deep integration",
            },
            "migration_difficulty": {
                "keywords": ["migration", "switching cost", "lock-in", "data portability"],
                "weight": 0.8,
                "inverse": False,
                "description": "Hard to migrate away",
            },
            "training_adoption": {
                "keywords": ["training", "certification", "learning curve", "expertise required"],
                "weight": 0.6,
                "inverse": False,
                "description": "User expertise investment",
            },
        },
        "regulatory_moat": {
            "certifications": {
                "keywords": ["certified", "ISO", "SOC 2", "HIPAA", "GDPR compliant", "FDA approved"],
                "weight": 1.0,
                "inverse": False,
                "description": "Regulatory certifications",
            },
            "licenses": {
                "keywords": ["licensed", "regulatory approval", "government approved", "accredited"],
                "weight": 0.9,
                "inverse": False,
                "description": "Required licenses",
            },
        },
        "brand_trust": {
            "enterprise_trust": {
                "keywords": ["trusted by", "enterprise customers", "Fortune 500", "industry leader"],
                "weight": 1.0,
                "inverse": False,
                "description": "Enterprise credibility",
            },
            "awards_recognition": {
                "keywords": ["award", "recognized", "top", "best", "leader in"],
                "weight": 0.7,
                "inverse": False,
                "description": "Industry recognition",
            },
        },
        "technical_complexity": {
            "research_team": {
                "keywords": ["PhD", "research team", "published", "academic", "research lab"],
                "weight": 1.0,
                "inverse": False,
                "description": "Research-driven development",
            },
            "novel_technology": {
                "keywords": ["novel", "breakthrough", "first to", "pioneering", "invented"],
                "weight": 0.9,
                "inverse": False,
                "description": "Novel technical approach",
            },
            "years_of_rd": {
                "keywords": ["years of development", "R&D", "research", "developed over"],
                "weight": 0.7,
                "inverse": False,
                "description": "Significant R&D investment",
            },
        },
    },
    
    # -------------------------------------------------------------------------
    # FOUNDER STRENGTH — Track Record + Execution Ability
    # -------------------------------------------------------------------------
    "founder_strength": {
        "prior_exits": {
            "exits": {
                "keywords": ["exit", "acquired", "IPO", "sold company", "previous startup"],
                "weight": 1.0,
                "inverse": False,
                "description": "Previous successful exit",
            },
            "serial_entrepreneur": {
                "keywords": ["serial entrepreneur", "founded multiple", "second company", "third venture"],
                "weight": 1.0,
                "inverse": False,
                "description": "Multiple ventures",
            },
        },
        "domain_expertise": {
            "industry_experience": {
                "keywords": ["years in", "industry veteran", "former", "ex-", "worked at"],
                "weight": 1.0,
                "inverse": False,
                "description": "Deep industry experience",
            },
            "domain_expert": {
                "keywords": ["expert in", "specialist", "authority", "thought leader", "speaker"],
                "weight": 0.8,
                "inverse": False,
                "description": "Recognized domain expertise",
            },
        },
        "technical_depth": {
            "technical_founder": {
                "keywords": ["CTO", "technical founder", "engineer", "developer", "built"],
                "weight": 1.0,
                "inverse": False,
                "description": "Technical co-founder",
            },
            "education": {
                "keywords": ["PhD", "Stanford", "MIT", "Harvard", "Oxford", "Cambridge", "computer science"],
                "weight": 0.7,
                "inverse": False,
                "description": "Strong technical education",
            },
        },
        "network_access": {
            "investor_network": {
                "keywords": ["backed by", "investors include", "angel", "VC", "board member"],
                "weight": 0.9,
                "inverse": False,
                "description": "Strong investor network",
            },
            "advisor_network": {
                "keywords": ["advisor", "mentor", "board", "advisory board"],
                "weight": 0.7,
                "inverse": False,
                "description": "Quality advisors",
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Sub-Component Weights (for detailed scoring)
# ---------------------------------------------------------------------------
# These weights determine how sub-components contribute to dimension scores.

SUB_COMPONENT_WEIGHTS = {
    "offer_power": {
        "dream_outcome": 0.30,
        "perceived_likelihood": 0.30,
        "time_delay": 0.20,
        "effort_required": 0.20,
    },
    "sales_ability": {
        "inbound_lead_gen": 0.30,
        "outbound_lead_gen": 0.30,
        "conversion_ability": 0.40,
    },
    "tech_moat": {
        "patents_ip": 0.20,
        "data_moat": 0.25,
        "network_effects": 0.20,
        "switching_costs": 0.15,
        "regulatory_moat": 0.10,
        "brand_trust": 0.05,
        "technical_complexity": 0.05,
    },
    "founder_strength": {
        "prior_exits": 0.35,
        "domain_expertise": 0.30,
        "technical_depth": 0.20,
        "network_access": 0.15,
    },
}
