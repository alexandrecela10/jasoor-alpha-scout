"""
Configuration — Alpha Scout Product-Specific Data.

This module contains PRODUCT-SPECIFIC configuration for Alpha Scout:
1. PORTFOLIO_COMPANIES — Jasoor's current investments (seeds for similarity search)
2. BENCHMARK_MENA_STARTUPS — Proven MENA companies for benchmarking
3. SCOUT_MODES — Deal sourcing pipeline definitions

REUSABLE pipeline configuration (scoring dimensions, signals, defaults) is in:
    config_pipeline.py

Why this split?
- config.py = Product-specific data (Jasoor portfolio, MENA benchmarks)
- config_pipeline.py = Reusable pipeline config (scoring, signals, sources)

Other products (due diligence, portfolio augmentation) can import from
config_pipeline.py without needing Jasoor-specific data.
"""

# Import reusable pipeline configuration
from config_pipeline import (
    SCORING_DIMENSIONS,
    OBJECTIVE_SIGNALS,
    SUB_COMPONENT_WEIGHTS,
    DEFAULT_SOURCES,
    DEFAULT_EXCLUSIONS,
    MATRIX_AXES,
    # Alternative dimension sets for other products
    VC_DEAL_FLOW_DIMENSIONS,
    DUE_DILIGENCE_DIMENSIONS,
)

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
# NOTE: Scoring Dimensions, Signals, Sources, etc. are now imported from
# config_pipeline.py at the top of this file. This keeps product-specific
# data (portfolio, benchmarks) separate from reusable pipeline config.
# ---------------------------------------------------------------------------
