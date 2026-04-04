# Jasoor "Alpha Scout" — AI Sourcing & Scoring Engine

> *"For the courageous investor"*

An AI-powered tool that identifies, benchmarks, and scores early-stage startups in the **MENAT** region, using grounded real-time data to mirror the success of Jasoor's current portfolio.

## Pipeline Overview & User Journey

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  1. INPUT    │───▶│  2. SEARCH   │───▶│  3. SCORE    │───▶│  4. REVIEW   │
│   (app.py)   │    │ (search.py)  │    │ (scorer.py)  │    │(reviewer.py) │
│              │    │              │    │              │    │              │
│ • Seed co.   │    │ • Tavily API │    │ • 4 dims     │    │ • Validate   │
│ • Criteria   │    │ • Gemini     │    │ • Evidence   │    │ • No halluc. │
│ • Weights    │    │   extraction │    │ • 1.0-5.0    │    │ • Explain    │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                                                                    │
                    ┌───────────────────────────────────────────────┘
                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        5. VISUALIZE & EXPORT                              │
├──────────────────────────────────────────────────────────────────────────┤
│  visualizer.py          │  reporting.py                                  │
│  • 2x2 Matrix (Plotly)  │  • Excel (Summary + Details)                   │
│  • Dark theme           │  • PDF report                                  │
│  • Hover tooltips       │  • Email (SMTP)                                │
└──────────────────────────────────────────────────────────────────────────┘
```

## Jobs to Be Done (User Stories)

### Step 1: **Eligibility Criteria** (Find Similar Companies)
> *"I want to find companies similar enough based on demographics & problem angle"*

**When I** select a seed company from Jasoor's portfolio  
**And** define eligibility filters (problem statement, target clients, industry, tech, location, size)  
**Then** the system searches for companies that match my demographic and problem criteria.

**Model Used:** `gemini-2.5-flash` (fast, efficient for search)

---

### Step 2: **Import Your Brain** (Score & Triage)
> *"I want to apply my investment expertise to systematically evaluate companies"*

**When I** review the eligible companies  
**Then** I can customize scoring criteria based on my expertise  
**And** each company is scored using **two-pass analysis**:

#### Two-Pass Scoring Architecture:
1. **Pass 1: Objective Signal Detection** — Keywords and patterns (fast, verifiable)
2. **Pass 2: LLM Interpretation** — Contextual reasoning (powerful model)

#### Scoring Dimensions (Modular Sub-components):

| Dimension | Sub-components |
|-----------|----------------|
| **Offer Power** | Dream Outcome, Perceived Likelihood, Time Delay, Effort Required |
| **Sales Ability** | Inbound Lead Gen, Outbound Lead Gen, Conversion Ability |
| **Tech Moat** | Patents/IP, Data Moat, Network Effects, Switching Costs, Regulatory, Brand, Complexity, Cost |
| **Founder Strength** | Prior Exits, Domain Expertise, Technical Depth, Network/Advisors |

**Model Used:** `gemini-2.5-pro` (powerful reasoning for scoring)

---

### Step 3: **Research & Navigate**
> *"I need to dig deeper into promising companies"*

**When I** view the scored companies  
**Then** I can click through to company websites  
**And** see all detected objective signals  
**And** view evidence quotes with source URLs  
**And** navigate to startup forums for more grounded information.

---

### Step 4: **Validate Results**
> *"I need confidence that the data is real and companies actually exist"*

**When I** review the Appendix  
**Then** the reviewer agent validates:
- Seed company profile accuracy
- Found companies actually exist (no hallucinations)
- Companies match the similarity criteria  
**And** shows all objective signals used (configurable)  
**And** explains why each score was given.

---

### Step 5: **Visualize & Compare**
> *"I want to quickly compare companies to identify the most promising opportunities"*

**When I** view the 2x2 matrix  
**Then** I can toggle axes between any scoring dimensions or CAC/LTV  
**And** hover to see company details, scores, and summaries  
**And** the plot uses decimal scores (1.0-5.0) for better spread and differentiation.

---

### Step 6: **Export & Share**
> *"I need to share findings with my team and follow up with promising companies"*

**When I** complete my analysis  
**Then** I can export:
- **Excel** with summary table and detailed score evidence  
- **PDF** report with company profiles and founder contacts
- **Email** directly to team members with PDF attached

**Appendix included:** All objective signals configuration for transparency.

## Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **LLM (Search)** | Gemini 2.5 Flash | Fast extraction for eligibility search |
| **LLM (Scoring)** | Gemini 2.5 Pro | Powerful reasoning for two-pass scoring |
| **Search** | Tavily API | MENAT startup discovery with source URLs |
| **UI** | Streamlit | Dark-themed web interface |
| **Visualization** | Plotly | Interactive 2x2 matrix with hover tooltips |
| **Observability** | Langfuse | Trace every LLM call, monitor costs |
| **Data** | Pandas + openpyxl | Excel export functionality |
| **Reporting** | fpdf2 | PDF generation for reports |

## Key Features

### 🎯 **Grounded Intelligence**
- Every score includes evidence_quote + source_url
- No hallucinations — returns "N/A" if no evidence
- Reviewer agent validates all outputs

### 🎨 **Jasoor Branding**
- Dark navy theme with mint accents
- "For the courageous investor" tagline
- Professional VC analyst experience

### 📊 **Interactive Analysis**
- Decimal scoring (1.0-5.0) for better company differentiation
- Configurable similarity criteria
- Customizable scoring dimensions
- 2x2 matrix with toggleable axes

### 📤 **Multiple Export Formats**
- **Excel**: Summary + detailed evidence sheets
- **PDF**: Professional report with founder contacts
- **Email**: SMTP integration with PDF attachment

## Quick Start

```bash
# 1. Clone and enter the project
cd alpha_scout

# 2. Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up your API keys
cp .env.example .env
# Edit .env with your real keys

# 5. Run the app
streamlit run app.py
```

## Required API Keys

| Key | Where to get it |
|-----|----------------|
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey |
| `TAVILY_API_KEY` | https://tavily.com |
| `LANGFUSE_PUBLIC_KEY` | https://cloud.langfuse.com → Settings → API Keys |
| `LANGFUSE_SECRET_KEY` | https://cloud.langfuse.com → Settings → API Keys |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` | For email export (Gmail requires App Password) |

### Email Setup (Optional)
For Gmail, generate an App Password at https://myaccount.google.com/apppasswords  
Regular passwords won't work with SMTP.

## Project Structure

```
alpha_scout/
├── app.py              # Streamlit UI (main entry point)
├── config.py           # ⭐ MAIN CONFIG: Portfolio, signals, weights (edit this!)
├── scoring_criteria.py # Helper functions that build from config.py
├── models.py           # Data classes (SearchResult, ScoredCompany, etc.)
├── search.py           # Tavily search + Gemini extraction
├── scorer.py           # Two-pass scoring (signals + LLM)
├── reviewer.py         # Validation agent (no hallucinations)
├── visualizer.py       # Plotly 2x2 matrix
├── reporting.py        # Excel, PDF, Email exports
├── llm_client.py       # Gemini API wrapper with grounding
├── tracing.py          # Langfuse observability
├── .env.example        # API keys template
├── requirements.txt    # Python dependencies
├── README.md           # This file
└── docs/
    └── architecture.md  # Detailed pipeline diagram
```

## Customizing Objective Signals

VC Analysts can adjust scoring signals in **`config.py`**:

```python
# Example: Add a new keyword to Tech Moat → Patents
OBJECTIVE_SIGNALS["tech_moat"]["patents_ip"]["patents"]["keywords"].append("trademark")

# Example: Change weight of a signal
OBJECTIVE_SIGNALS["sales_ability"]["conversion_ability"]["revenue_evidence"]["weight"] = 1.5

# Example: Add inverse signal (presence is negative)
OBJECTIVE_SIGNALS["offer_power"]["effort_required"]["high_effort"]["inverse"] = True
```

### Signal Structure:
```
OBJECTIVE_SIGNALS = {
    "dimension_key": {
        "sub_component": {
            "signal_name": {
                "keywords": ["keyword1", "keyword2"],
                "weight": 1.0,
                "inverse": False,
                "description": "What this signal indicates"
            }
        }
    }
}
```

## Grounding Guarantee

**Every piece of information MUST be grounded in source data:**

- ✅ Score has `evidence_quote` from source
- ✅ Score has `source_url` for verification  
- ✅ If no evidence exists → return "N/A" (never guess)
- ✅ Reviewer validates no hallucinations
- ✅ Langfuse traces every LLM call for auditability

This ensures **zero hallucinations** and **full auditability** for VC-grade diligence.
