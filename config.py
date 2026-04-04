"""
Configuration — Portfolio seed data, scoring dimensions, and default sources.

This is the "knowledge base" of Alpha Scout. It contains:
1. PORTFOLIO_COMPANIES — Jasoor's current investments with their key attributes.
   These are used as "seeds" to find similar startups.
2. SCORING_DIMENSIONS — The 4 axes we score companies on.
3. DEFAULT_SOURCES — Websites to prioritize when searching for MENAT startups.

Why hardcode portfolio companies? Because this is internal data that doesn't
exist on the public internet. Jasoor's team knows their own portfolio best.
"""

# ---------------------------------------------------------------------------
# Jasoor Portfolio Companies (Seeds)
# ---------------------------------------------------------------------------
# Each company has 6 structured attributes used for eligibility search:
# 1. problem_statement - What pain point does the company solve?
# 2. target_clients - Who are the ideal customers? (B2B, B2C, enterprise, SMB)
# 3. industry_vertical - Which sector/industry do they operate in?
# 4. technology - What tech stack or innovation do they use?
# 5. location - Where are they based? (country/region)
# 6. company_size - What stage are they at? (seed, series A, team size)
#
# These attributes are editable in the UI and drive the similarity search.

PORTFOLIO_COMPANIES = {
    "4401 Earth": {
        "description": "Carbon removal technology using mineralisation to permanently store CO₂ in rocks",
        "website": "https://www.4401.earth",
        # 6 Eligibility Attributes
        "problem_statement": "Climate change requires permanent carbon removal solutions that are safe, scalable, and affordable",
        "target_clients": "B2B: Corporations seeking carbon credits, energy companies, governments, ESG-focused enterprises",
        "industry_vertical": "Climate Tech / Carbon Removal",
        "technology": "CO₂ mineralisation, peridotite rock injection, carbon capture and storage (CCS)",
        "location": "Oman / GCC / MENA",
        "company_size": "Growth stage, 50-100 employees, Series B funded",
        # 4 Moat Attributes
        "tech_moat": "Proprietary mineralisation process patents, first-mover in Oman's peridotite geology",
        "tech_stack": "Geochemical monitoring systems, environmental sensors, carbon accounting software",
        "offer_moat": "Permanent carbon removal (not offset) at competitive cost — only solution using natural rock chemistry",
        "sales_distribution_moat": "Direct enterprise contracts, government partnerships, carbon credit registry integrations",
    },
    "Byanat AI": {
        "description": "Unified AI platform for optimising digital infrastructure across telecoms and data centres",
        "website": "https://www.byanat.ai",
        # 6 Eligibility Attributes
        "problem_statement": "Telecoms and data centres lack visibility into infrastructure performance, leading to inefficiencies and revenue leaks",
        "target_clients": "B2B: Telecom operators, data centre providers, utilities, defence, smart city operators",
        "industry_vertical": "Deep Tech / AI / Infrastructure 4.0",
        "technology": "Predictive AI analytics, autonomous networks, low-code console, multi-vendor integration, API automation",
        "location": "Oman / Bahrain / GCC",
        "company_size": "Growth stage, award-winning, established leadership in smart city infrastructure",
        # 4 Moat Attributes
        "tech_moat": "Proprietary AI models trained on telecom network data, multi-vendor integrations with high switching costs",
        "tech_stack": "Machine learning, big data pipelines, REST APIs, low-code console, real-time monitoring",
        "offer_moat": "Single platform replacing multiple point solutions — engineers save hours daily with AI automation",
        "sales_distribution_moat": "Direct enterprise sales to tier-1 telecoms, government contracts, GCC channel partners",
    },
    "Tabsense": {
        "description": "Smart restaurant management platform with AI-powered POS and operations automation",
        "website": "https://tabsense.com",
        # 6 Eligibility Attributes
        "problem_statement": "Restaurants struggle with fragmented operations, manual processes, and lack of data-driven insights",
        "target_clients": "B2B: Restaurants, cafes, F&B chains, hospitality groups, QSR franchises",
        "industry_vertical": "FoodTech / Restaurant SaaS",
        "technology": "AI-powered POS, operations automation, inventory management, analytics dashboard",
        "location": "UAE / GCC",
        "company_size": "Early-stage, seed/Series A, 10-30 employees",
        # 4 Moat Attributes
        "tech_moat": "Integrated POS + inventory + analytics creates data lock-in, switching costs are high",
        "tech_stack": "Cloud SaaS, mobile POS, IoT integrations, real-time analytics, payment processing APIs",
        "offer_moat": "All-in-one Arabic-native restaurant OS replacing 3-4 separate tools at lower total cost",
        "sales_distribution_moat": "Direct SMB and enterprise sales in GCC, F&B association partnerships",
    },
    "Kitchenomiks": {
        "description": "Smart cloud kitchen platform enabling F&B businesses to scale through delivery",
        "website": "https://kitchenomiks.com",
        # 6 Eligibility Attributes
        "problem_statement": "F&B businesses want to expand geographically but lack kitchen infrastructure and delivery capabilities",
        "target_clients": "B2B: Restaurant brands, food entrepreneurs, F&B franchises wanting delivery expansion",
        "industry_vertical": "FoodTech / Cloud Kitchens",
        "technology": "Smart kitchen platform, multi-aggregator order management, supply chain automation, last-mile delivery integration",
        "location": "Saudi Arabia / UAE / GCC",
        "company_size": "Early-stage, seed funded, 20-50 employees",
        # 4 Moat Attributes
        "tech_moat": "Physical kitchen infrastructure + software platform creates high switching costs for tenants",
        "tech_stack": "Order management system, aggregator APIs (Talabat, Deliveroo, Jahez), supply chain software",
        "offer_moat": "Launch a delivery brand in 30 days with no CAPEX — kitchen, staff, supply chain included",
        "sales_distribution_moat": "Aggregator partnerships, F&B brand network effects, geographic kitchen expansion",
    },
}


# ---------------------------------------------------------------------------
# Scout Modes — 3 deal sourcing pipelines
# ---------------------------------------------------------------------------
# Each mode defines how Alpha Scout finds companies to score.
# All modes feed into the same scoring pipeline.

SCOUT_MODES = {
    "portfolio": {
        "label": "📁  Portfolio Benchmark",
        "description": "Find early-stage startups similar to your existing portfolio companies",
        "heading": "Scouting via Portfolio Benchmark",
        "step1_title": "1. Select Portfolio Company",
    },
    "mena_success": {
        "label": "🌟  MENA Success Stories",
        "description": "Find pre-Series A startups similar to proven MENA companies (Series C+, IPO, M&A)",
        "heading": "Scouting via MENA Success Stories",
        "step1_title": "1. Select MENA Benchmark",
    },
    "inbound": {
        "label": "📥  Inbound Candidates",
        "description": "Score and rank startups that pitched to you — from website or pitchdeck",
        "heading": "Scoring Inbound Candidates",
        "step1_title": "1. Add Candidate Companies",
    },
}


# ---------------------------------------------------------------------------
# Benchmark MENA Startups — Successful companies used as reference points
# ---------------------------------------------------------------------------
# These are proven MENA startups (Series C+, IPO, or M&A) used in Mode 2.
# Alpha Scout finds EARLIER-STAGE companies solving similar problems.
# Source: public information from company websites and press releases.

BENCHMARK_MENA_STARTUPS = {
    "Tabby": {
        "description": "Buy Now Pay Later (BNPL) platform enabling flexible payments for shoppers in MENA",
        "website": "https://tabby.ai",
        "achieved_stage": "Series D (~$6.5B valuation)",
        # 6 Eligibility Attributes
        "problem_statement": "Consumers in MENA lack access to flexible credit and instalment payment options at checkout",
        "target_clients": "B2C: Online and in-store shoppers; B2B: E-commerce merchants and retailers",
        "industry_vertical": "Fintech / BNPL / Consumer Credit",
        "technology": "AI-powered credit scoring, BNPL payment infrastructure, merchant checkout APIs",
        "location": "UAE / Saudi Arabia / GCC",
        "company_size": "Series D, 1000+ employees, operational in UAE, KSA, Kuwait, Bahrain",
        # 4 Moat Attributes
        "tech_moat": "Proprietary MENA credit scoring model, 10M+ consumer data points, regulatory licenses",
        "tech_stack": "Machine learning credit models, real-time risk engine, merchant payment SDKs",
        "offer_moat": "0% interest split payments with instant approval — no bank account required",
        "sales_distribution_moat": "2000+ merchant integrations, embedded at checkout on major MENA platforms",
    },
    "foodics": {
        "description": "All-in-one restaurant management platform: POS, inventory, HR, and analytics for F&B",
        "website": "https://foodics.com",
        "achieved_stage": "Series C ($170M raised)",
        # 6 Eligibility Attributes
        "problem_statement": "F&B businesses in MENA use fragmented, outdated systems for operations, costing time and revenue",
        "target_clients": "B2B: Restaurants, cafes, cloud kitchens, food courts, QSR franchises in MENA",
        "industry_vertical": "FoodTech / Restaurant SaaS",
        "technology": "Cloud POS, inventory management, kitchen display systems, HR, and financial analytics",
        "location": "Saudi Arabia / UAE / GCC / MENA",
        "company_size": "Series C, 600+ employees, 30,000+ businesses on platform",
        # 4 Moat Attributes
        "tech_moat": "Deep MENA market integrations, Arabic-native UX, local payment gateway lock-in",
        "tech_stack": "Cloud SaaS, IoT kitchen displays, multi-vendor API integrations, analytics engine",
        "offer_moat": "One subscription replaces POS + inventory + HR + analytics tools at lower total cost",
        "sales_distribution_moat": "Channel partner network across GCC, enterprise direct sales, 5-star support reputation",
    },
    "Vezeeta": {
        "description": "Digital health platform connecting patients to doctors and clinics across MENA",
        "website": "https://vezeeta.com",
        "achieved_stage": "Series D ($40M+ raised)",
        # 6 Eligibility Attributes
        "problem_statement": "Healthcare access in MENA is fragmented — patients struggle to find, book, and pay for healthcare",
        "target_clients": "B2C: Patients; B2B: Clinics, hospitals, pharmacies, insurance companies",
        "industry_vertical": "HealthTech / Digital Health",
        "technology": "Doctor discovery, appointment booking, telemedicine, EHR integration, insurance APIs",
        "location": "Egypt / Saudi Arabia / UAE / Jordan / Lebanon",
        "company_size": "Series D, 5M+ patients, 50,000+ doctors on platform",
        # 4 Moat Attributes
        "tech_moat": "Largest verified doctor database in MENA, patient data network effects, clinic software dependency",
        "tech_stack": "Mobile-first platform, telemedicine infrastructure, EHR APIs, insurance claims processing",
        "offer_moat": "Free for patients, subscription for clinics — creates two-sided marketplace with strong retention",
        "sales_distribution_moat": "3,500+ clinic partnerships, insurance integrations, telehealth partnerships",
    },
    "Sary": {
        "description": "B2B wholesale marketplace connecting small retailers to FMCG suppliers in Saudi Arabia",
        "website": "https://sary.com",
        "achieved_stage": "Series C ($75M raised)",
        # 6 Eligibility Attributes
        "problem_statement": "Small retailers in KSA pay inflated prices for stock and waste hours managing fragmented suppliers",
        "target_clients": "B2B: Small and medium retailers (baqalas), FMCG brands and distributors",
        "industry_vertical": "B2B Commerce / Supply Chain / FMCG",
        "technology": "B2B marketplace platform, last-mile delivery logistics, credit financing for retailers",
        "location": "Saudi Arabia / GCC",
        "company_size": "Series C, 200+ employees, 100,000+ retailers served",
        # 4 Moat Attributes
        "tech_moat": "Supplier data and pricing intelligence, proprietary logistics network, retailer financial data",
        "tech_stack": "Mobile-first marketplace, route optimization, inventory forecasting, BNPL for SMBs",
        "offer_moat": "10-30% cheaper prices, next-day delivery, embedded credit — all from one app",
        "sales_distribution_moat": "Direct supplier contracts, field sales in major KSA cities, strong brand in baqala community",
    },
    "Unifonic": {
        "description": "Cloud communications platform (CPaaS) enabling businesses to communicate via SMS, WhatsApp, voice",
        "website": "https://unifonic.com",
        "achieved_stage": "Series B ($125M raised)",
        # 6 Eligibility Attributes
        "problem_statement": "Businesses in MENA lack reliable, unified customer communication infrastructure (SMS, WhatsApp, voice)",
        "target_clients": "B2B: Enterprises, banks, telecom, retail, healthcare needing customer communication APIs",
        "industry_vertical": "SaaS / CPaaS / Communications",
        "technology": "SMS API, WhatsApp Business API, voice calls, chatbots, customer journey automation",
        "location": "Saudi Arabia / UAE / GCC / MENA",
        "company_size": "Series B, 500+ employees, 1000+ enterprise customers",
        # 4 Moat Attributes
        "tech_moat": "Direct telecom carrier agreements, WhatsApp Business Solution Provider license, regulatory approvals",
        "tech_stack": "CPaaS infrastructure, REST APIs, no-code journey builder, analytics dashboard",
        "offer_moat": "Single API for all channels (SMS + WhatsApp + voice) with MENA-specific compliance built-in",
        "sales_distribution_moat": "Enterprise direct sales, SI partnerships, carrier relationships across 160+ countries",
    },
    "Lean Technologies": {
        "description": "Open banking API infrastructure connecting apps to bank accounts across MENA",
        "website": "https://leantech.me",
        "achieved_stage": "Series B ($33M raised)",
        # 6 Eligibility Attributes
        "problem_statement": "Fintech apps in MENA cannot easily connect to bank accounts for payments, data, and identity verification",
        "target_clients": "B2B: Fintech startups, neobanks, lenders, accounting platforms needing bank connectivity",
        "industry_vertical": "Fintech / Open Banking / API Infrastructure",
        "technology": "Open banking APIs, account-to-account payments, financial data aggregation, identity verification",
        "location": "UAE / Saudi Arabia / Bahrain / GCC",
        "company_size": "Series B, 50+ employees, connected to 60+ banks",
        # 4 Moat Attributes
        "tech_moat": "Bank integration agreements, regulatory sandbox licenses, first-mover in GCC open banking",
        "tech_stack": "Banking APIs, OAuth flows, real-time payment rails, data normalization layer",
        "offer_moat": "One API to connect to all MENA banks — replaces months of individual bank integrations",
        "sales_distribution_moat": "Direct developer adoption, fintech community, Saudi SAMA and UAE CBUAE regulatory partnerships",
    },
}

# ---------------------------------------------------------------------------
# Scoring Dimensions
# ---------------------------------------------------------------------------
# These are the 4 axes we score each target company on (1-5 scale).
# The user can adjust the weights in the UI to prioritize what matters most.
#
# "prompt_guidance" tells Gemini what to look for when scoring each dimension.
# This keeps scoring consistent and grounded.

SCORING_DIMENSIONS = {
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
    "google.com",           # General search (always useful)
    "menabytes.com",        # MENA startup news (funding rounds, launches)
    "wamda.com",            # MENA entrepreneurship platform
    "magnitt.com",          # MENA & Africa startup data platform
    "zawya.com",            # MENA business intelligence
    "crunchbase.com",       # Funding data and company profiles
    "producthunt.com",      # Global product launches (many MENA founders post here)
    # LinkedIn MENA Startup Channels
    "linkedin.com/company/maborco",          # MENA Business Review
    "linkedin.com/company/flat6labs",        # Flat6Labs accelerator
    "linkedin.com/company/500-global",       # 500 Global (active in MENA)
    "linkedin.com/company/startupbootcamp",  # Startup Bootcamp
    "linkedin.com/company/techstars",        # Techstars
    "linkedin.com/company/antler",           # Antler (active in MENA)
    "linkedin.com/company/seedstars",        # Seedstars
    "linkedin.com",                          # General LinkedIn
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
                "inverse": False,  # Fast = good
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
                "inverse": True,  # Slow = bad
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
                "inverse": True,  # High effort = bad
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
        "cost_advantage": {
            "cost_leadership": {
                "keywords": ["10x cheaper", "fraction of the cost", "affordable", "low cost"],
                "weight": 1.0,
                "inverse": False,
                "description": "Significant cost advantage",
            },
            "economies_of_scale": {
                "keywords": ["economies of scale", "unit economics", "marginal cost", "scale advantage"],
                "weight": 0.8,
                "inverse": False,
                "description": "Scale-driven cost reduction",
            },
        },
    },
    
    # -------------------------------------------------------------------------
    # FOUNDER STRENGTH — Track Record & Execution
    # -------------------------------------------------------------------------
    "founder_strength": {
        "prior_exits": {
            "exits": {
                "keywords": ["exited", "acquired by", "sold to", "IPO", "exit to"],
                "weight": 1.0,
                "inverse": False,
                "description": "Previous exits",
            },
            "serial_entrepreneur": {
                "keywords": ["serial entrepreneur", "founded multiple", "previous company", "second venture"],
                "weight": 0.9,
                "inverse": False,
                "description": "Multiple ventures",
            },
        },
        "domain_expertise": {
            "industry_experience": {
                "keywords": ["years in", "industry veteran", "former", "ex-", "worked at"],
                "weight": 1.0,
                "inverse": False,
                "description": "Industry background",
            },
            "executive_experience": {
                "keywords": ["VP", "Director", "Head of", "C-level", "executive", "led"],
                "weight": 0.9,
                "inverse": False,
                "description": "Leadership experience",
            },
            "domain_expert": {
                "keywords": ["expert in", "specialist", "authority", "thought leader"],
                "weight": 0.8,
                "inverse": False,
                "description": "Recognized expertise",
            },
        },
        "technical_depth": {
            "technical_background": {
                "keywords": ["engineer", "developer", "CTO", "technical founder", "built"],
                "weight": 1.0,
                "inverse": False,
                "description": "Technical founder",
            },
            "academic_credentials": {
                "keywords": ["PhD", "Masters", "Stanford", "MIT", "published", "research"],
                "weight": 0.8,
                "inverse": False,
                "description": "Academic background",
            },
            "patents_authored": {
                "keywords": ["inventor", "patent author", "patented by"],
                "weight": 0.7,
                "inverse": False,
                "description": "Technical innovation",
            },
        },
        "network_advisors": {
            "top_investors": {
                "keywords": ["backed by", "invested by", "Sequoia", "a16z", "YC", "Techstars", "500"],
                "weight": 1.0,
                "inverse": False,
                "description": "Top-tier investors",
            },
            "advisors": {
                "keywords": ["advised by", "advisor", "board member", "mentor"],
                "weight": 0.8,
                "inverse": False,
                "description": "Advisory network",
            },
            "industry_connections": {
                "keywords": ["connected to", "network", "relationships", "partnerships"],
                "weight": 0.6,
                "inverse": False,
                "description": "Industry relationships",
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Sub-Component Weights — How much each sub-component contributes to dimension
# ---------------------------------------------------------------------------
# These weights determine how sub-components are combined into the final score.
# VC Analysts can adjust these to prioritize different aspects.

SUB_COMPONENT_WEIGHTS = {
    "offer_power": {
        "dream_outcome": 0.30,
        "perceived_likelihood": 0.30,
        "time_delay": 0.20,
        "effort_required": 0.20,
    },
    "sales_ability": {
        "inbound_lead_gen": 0.35,
        "outbound_lead_gen": 0.30,
        "conversion_ability": 0.35,
    },
    "tech_moat": {
        "patents_ip": 0.20,
        "data_moat": 0.20,
        "network_effects": 0.20,
        "switching_costs": 0.15,
        "regulatory_moat": 0.10,
        "brand_trust": 0.05,
        "technical_complexity": 0.05,
        "cost_advantage": 0.05,
    },
    "founder_strength": {
        "prior_exits": 0.30,
        "domain_expertise": 0.30,
        "technical_depth": 0.20,
        "network_advisors": 0.20,
    },
}
