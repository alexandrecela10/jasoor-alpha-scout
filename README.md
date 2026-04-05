# Alpha Scout — AI-Powered Startup Sourcing for MENA

> *"For the courageous investor"* — Jasoor Ventures

AI-powered tool that discovers, enriches, and scores early-stage startups in the **MENA** region using grounded real-time data.

---

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ALPHA SCOUT PIPELINE (v3 - Tavily)                      │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────────────────────┐
  │              🔍 TAVILY SMART SEARCH — Precise Company Discovery           │
  │                      search.py                                            │
  │                                                                           │
  │  Query has stage + MENA filters BAKED IN:                                │
  │  "early-stage startup seed series-A similar to Byanat fintech            │
  │   MENA UAE Saudi Arabia Egypt Jordan"                                    │
  │                                                                           │
  │  • Searches ONLY user-selected source domains                            │
  │  • Crunchbase, Magnitt, Wamda, TechCrunch, etc.                          │
  │  • Gemini extracts structured company data from results                  │
  │  • Blacklist skips previously filtered companies                         │
  └──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │              🔗 MULTI-SOURCE ENRICHMENT                                   │
  │                    source_enrichment.py                                   │
  │                                                                           │
  │  1. Website Finder Agent                                                 │
  │     • Search for official company website                                │
  │     • Verify URL exists (HEAD request)                                   │
  │     • Fetch content for scorer                                           │
  │                                                                           │
  │  2. LinkedIn Finder Agent                                                │
  │     • Search for company LinkedIn page                                   │
  │     • Extract employee count, HQ location                                │
  │     • Verify URL exists                                                  │
  │                                                                           │
  │  3. Stage Finder Agent (Tavily → News)                                   │
  │     • Search Crunchbase, TechCrunch for funding news                     │
  │     • Verify funding stage from recent articles                          │
  │     • Filter out late-stage companies (> Series B)                       │
  │                                                                           │
  │  All agents traced in Langfuse for observability                         │
  └──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │                         📈 SCORE & ANALYZE                                │
  │                                                                           │
  │  Scorer has access to:                                                   │
  │  • Website content (case studies, product descriptions)                  │
  │  • Verified funding stage (from Tavily news search)                      │
  │  • LinkedIn data (employee count, HQ)                                    │
  │  • All claims grounded with source URLs                                  │
  └──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  │   DISPLAY    │────▶│  VC ANALYST  │────▶│   EXPORT     │
  │   app.py     │     │  vc_chat.py  │     │              │
  │              │     │              │     │              │
  │ • Table +    │     │ • AI Analyst │     │ • Excel      │
  │   Evidence   │     │ • Grounded   │     │ • Target     │
  │ • 2x2 Matrix │     │   insights   │     │   List       │
  └──────────────┘     └──────────────┘     └──────────────┘
```

---

## User Stories

### 1. **Find Similar Companies** (Portfolio Mode)
> *"I want to find MENA startups similar to my portfolio companies"*

Select a seed company → Set criteria → Search returns matching startups with verified data.

### 1b. **Evaluate Inbound Pitches** (Inbound Mode)
> *"I received a pitchdeck and want to quickly evaluate this company"*

Paste pitchdeck text or company URLs → System enriches with **both document data AND online sources** (website, LinkedIn, funding news) → Score and compare against portfolio.

### 2. **Filter by Hard Criteria**
> *"I only want early-stage startups (<100 employees, Series B or earlier) in MENA"*

Hard filters automatically remove companies that don't meet size, location, or funding stage requirements.

### 3. **Score & Compare**
> *"I want to systematically evaluate companies on key dimensions"*

Each company scored on: **Offer Power**, **Sales Ability**, **Tech Moat**, **Founder Strength**.

### 4. **Get AI Insights**
> *"I want an AI analyst to help me understand the data"*

VC Analyst chat provides **dual output**:
- **📊 Grounded Analysis** — Only verified evidence, exact quotes
- **💡 VC Interpretation** — Pattern-matched insights from 15+ years experience

### 5. **Save & Continue Later**
> *"I want to pick up where I left off"*

Load previous searches, add companies to target list, export to Excel.

---

## Usage Guide

### Quick Start
```bash
# 1. Setup
cd alpha_scout
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Configure API keys
cp .env.example .env
# Edit .env with: GEMINI_API_KEY, TAVILY_API_KEY

# 3. Run
streamlit run app.py
```

### Basic Workflow
1. **Sidebar** → Select seed company or enter custom criteria
2. **Filters** → Set max employees, MENA only, Series B or earlier
3. **Search** → Click "Search & Score"
4. **Results** → View Comparison Table (with evidence), 2x2 Matrix, Detailed Report
5. **Target List** → Add promising companies
6. **VC Analyst** → Expand for AI-powered analysis

### Key Features
| Feature | Description |
|---------|-------------|
| **🔍 Tavily Smart Search** | Stage + MENA filters baked into query for precise results |
| **📂 Selected Sources Only** | Searches ONLY user-selected domains (Crunchbase, Magnitt, etc.) |
| **🔗 URL Verification** | HEAD requests verify website + LinkedIn URLs exist |
| **📊 Stage Finder Agent** | Tavily searches news to verify funding stage |
| **📄 Website Content** | Fetches website content (case studies, product info) for scorer |
| **🧠 Learning System** | Blacklists ineligible companies — search gets faster over time |
| **📈 Langfuse Tracing** | All agents traced for observability and debugging |
| **MENA Filter** | Only MENA-headquartered companies |
| **Size Filter** | Max 100 employees (tunable) |
| **Stage Filter** | Series B and earlier only (verified from news) |
| **Evidence in Table** | Each score shows quote + source URL |
| **VC Analyst Chat** | Dual output: grounded analysis + VC interpretation |

### 🧠 Learning System (Blacklist)

The search engine **learns over time** by maintaining a blacklist of companies that failed eligibility filters:

| Reason | Description |
|--------|-------------|
| `non_mena` | Company HQ is not in MENA region |
| `too_large` | Company has >100 employees |
| `late_stage` | Company is Series C or later |

**How it works:**
1. When a company fails a filter, it's added to the blacklist with the reason
2. Future searches automatically skip blacklisted companies
3. This saves API calls and makes searches faster over time
4. Users can view, edit, or clear the blacklist in the sidebar

### Performance
| Metric | Old (Tavily) | New (Gemini) |
|--------|--------------|--------------|
| **10 companies** | ~60s | **~15s** |
| **Search method** | Tavily + 3 agents | Single Gemini call |
| **Filtering** | Post-enrichment | Pre-filtered in query |
| **Learning speedup** | N/A | Skips blacklisted (0s) |

---

## Technical Guide

### Step-by-Step Function Flow

```
User clicks "Search & Score"
        │
        ▼
┌─ app.py ─────────────────────────────────────────────────────────────┐
│  search_similar_companies(seed, criteria, location, sources)         │
└──────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ search.py ──────────────────────────────────────────────────────────┐
│  1. _build_search_query() → Create Tavily search query               │
│  2. tavily.search() → Get raw results with source URLs               │
│  3. _extract_companies_from_results() → Gemini extracts structured   │
│  4. validate_all_fields() → Grounding checks (grounding.py)          │
│  5. verify_website_exists() → HTTP check if website is real          │
└──────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ source_enrichment.py ───────────────────────────────────────────────┐
│  enrich_search_results() → For each company:                         │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │           ⚡ PARALLEL EXECUTION (3x faster)                      │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                │ │
│  │  │  Website    │ │  LinkedIn   │ │   Stage     │                │ │
│  │  │  Finder     │ │  Finder     │ │   Finder    │                │ │
│  │  │  Agent      │ │  Agent      │ │   Agent     │                │ │
│  │  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘                │ │
│  │         │               │               │                        │ │
│  │         └───────────────┼───────────────┘                        │ │
│  │                         ▼                                        │ │
│  │              All 3 run simultaneously                            │ │
│  │              ~3s instead of ~9s                                  │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  AGENT 1: Website Finder                                              │
│     • Tavily search: "{company} official website"                     │
│     • Filter out social media, aggregators                            │
│     • Fetch page, verify company name appears                         │
│     • Extract: description, sector, location, tech stack              │
│                                                                       │
│  AGENT 2: LinkedIn Finder                                             │
│     • Tavily search: "site:linkedin.com/company {company}"            │
│     • Verify company name in page title                               │
│     • Extract: employee count, HQ, industry, founded year             │
│                                                                       │
│  AGENT 3: Stage Finder                                                │
│     • Tavily search: "{company} funding round series seed"            │
│     • Extract: Pre-seed, Seed, Series A/B/C, etc.                     │
│     • Verify quote in source content                                  │
│                                                                       │
│  FILTERS:                                                             │
│     • passes_size_filter() → Check <100 employees                     │
│     • is_in_mena() → Check HQ in MENA region                          │
│     • is_early_stage() → Check ≤Series B                              │
│                                                                       │
│  Return: (passed, filtered_out, enrichments)                          │
└──────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ scorer.py ──────────────────────────────────────────────────────────┐
│  score_companies(search_results) → For each company:                 │
│  1. Pass 1: detect_signals() → Keyword matching (fast, verifiable)   │
│  2. Pass 2: call_gemini() → LLM scoring with evidence quotes         │
│  3. validate_score_evidence() → Grounding check on quotes            │
│  4. Return: ScoredCompany with 4 dimension scores                    │
└──────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ app.py (display) ───────────────────────────────────────────────────┐
│  1. generate_markdown_table() → Comparison table                     │
│  2. create_matrix_plot() → Plotly 2x2 visualization                  │
│  3. Display grounded evidence per company                            │
└──────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ vc_chat.py ─────────────────────────────────────────────────────────┐
│  chat_with_vc_analyst(message, targets) →                            │
│  1. build_target_context() → Format company data for LLM             │
│  2. call_gemini() → Get AI response (fast or thinking model)         │
│  3. Return grounded analysis with table format                       │
└──────────────────────────────────────────────────────────────────────┘
```

### Key Files
| File | Purpose |
|------|---------|
| `app.py` | Streamlit UI, orchestrates pipeline |
| `search.py` | Tavily search + Gemini extraction |
| `source_enrichment.py` | **3 agents**: Website Finder, LinkedIn Finder, Stage Finder |
| `scorer.py` | Two-pass scoring (signals + LLM) |
| `reporting.py` | Comparison table with evidence, Excel export |
| `grounding.py` | Evidence validation, no hallucinations |
| `vc_chat.py` | AI analyst chat with grounded prompts |
| `persistence.py` | SQLite storage for searches, targets |
| `config.py` | Portfolio companies, scoring signals |

---

## Deployment (Google Cloud)

### Option 1: Cloud Run (Recommended)
```bash
# Build container
gcloud builds submit --tag gcr.io/PROJECT_ID/alpha-scout

# Deploy
gcloud run deploy alpha-scout \
  --image gcr.io/PROJECT_ID/alpha-scout \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars "GEMINI_API_KEY=xxx,TAVILY_API_KEY=xxx"
```

### Option 2: Compute Engine
```bash
# SSH into VM
gcloud compute ssh alpha-scout-vm

# Clone and run
git clone <repo>
cd alpha_scout
pip install -r requirements.txt
streamlit run app.py --server.port 8080
```

### Required Environment Variables
```
GEMINI_API_KEY=your_gemini_key
TAVILY_API_KEY=your_tavily_key
LANGFUSE_PUBLIC_KEY=optional
LANGFUSE_SECRET_KEY=optional
```

---

## Grounding Guarantee

Every piece of information is verified by **3 specialized agents**:

### Website Finder Agent
- ✅ Searches Tavily for official company website
- ✅ Filters out social media and aggregator sites
- ✅ Fetches actual page content via HTTP
- ✅ Verifies company name appears in page

### LinkedIn Finder Agent
- ✅ Searches for company LinkedIn page
- ✅ Extracts employee count, HQ, industry
- ✅ Verifies company name in page title

### Stage Finder Agent
- ✅ Searches for funding announcements
- ✅ Extracts funding stage (Seed, Series A/B/C)
- ✅ Verifies quote exists in source content

### Multi-Source Evidence
- ✅ Each data point can have multiple sources
- ✅ Confidence score increases with more verified sources
- ✅ Comparison table shows evidence quotes + source URLs
- ✅ VC Analyst uses only grounded data

**Zero hallucinations. Full auditability.**

---

## Observability & Continuous Improvement

Every LLM call is **traced and evaluated** via [Langfuse](https://langfuse.com), ensuring measurable improvement over time.

### What's Traced
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LANGFUSE OBSERVABILITY                               │
└─────────────────────────────────────────────────────────────────────────────┘

  Every LLM Call                    Every Enrichment Batch
  ─────────────                     ──────────────────────
  • Prompt sent                     • valid_website (% accessible)
  • Response received               • right_website (% name match)
  • Token count                     • employee_count_rate (% found)
  • Latency (ms)                    • stage_found_rate (% found)
  • Model used                      • location_mena_rate (% in MENA)
```

### Evaluation Metrics (Logged to Langfuse)

| Metric | Description | Target |
|--------|-------------|--------|
| `valid_website` | Website URL returns HTTP 200 | >90% |
| `right_website` | Page content contains company name | >85% |
| `employee_count_rate` | Employee count successfully extracted | >80% |
| `stage_found_rate` | Funding stage found in news/Crunchbase | >60% |
| `location_mena_rate` | Company HQ is in MENA region | 100% |
| `llm_judge_score` | LLM-as-a-Judge quality review | >0.7 |

### LLM-as-a-Judge

After scoring, an LLM reviews each company's enrichment quality:
- **Website Accuracy** — Is the URL plausible for this company?
- **Data Completeness** — Are key fields (employees, location, stage) filled?
- **Evidence Quality** — Are quotes and sources provided for claims?
- **Score Justification** — Do the scores have supporting evidence?

### Why This Matters

```
Week 1: valid_website = 75%  →  Identify failing patterns
Week 2: valid_website = 82%  →  Fix domain filtering
Week 3: valid_website = 91%  →  Continuous improvement ✓
```

All metrics are visible in the Langfuse dashboard, enabling:
- 📈 **Trend analysis** — Track quality over time
- 🔍 **Debugging** — Inspect failing LLM calls
- 💰 **Cost tracking** — Monitor token usage
- 🎯 **A/B testing** — Compare prompt variations
