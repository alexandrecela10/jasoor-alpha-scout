# Alpha Scout — Pipeline Architecture

## High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ALPHA SCOUT                                     │
│                     "For the courageous investor"                           │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           1. USER INPUT (app.py)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  • Select seed company (from Jasoor portfolio)                              │
│  • Define similarity criteria (problem, clients, industry, tech, etc.)      │
│  • Set geographic focus (MENA/GCC)                                          │
│  • Configure search sources                                                 │
│  • Adjust scoring weights                                                   │
│  • Customize scoring criteria descriptions                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         2. SEARCH (search.py)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────────────┐      │
│  │ Seed Company │ ───▶ │ Build Query  │ ───▶ │    Tavily Search     │      │
│  │   (config)   │      │  (criteria)  │      │   (web research)     │      │
│  └──────────────┘      └──────────────┘      └──────────────────────┘      │
│                                                       │                     │
│                                                       ▼                     │
│                              ┌────────────────────────────────────┐         │
│                              │   Gemini LLM Extraction            │         │
│                              │   • Extract company data           │         │
│                              │   • Validate against criteria      │         │
│                              │   • Return SearchResult objects    │         │
│                              └────────────────────────────────────┘         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         3. SCORING (scorer.py)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  For each company, score on 4 dimensions using Gemini:                      │
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │  Offer Power    │  │  Sales Ability  │  │   Tech Moat     │             │
│  │  (Hormozi eq.)  │  │   (traction)    │  │ (defensibility) │             │
│  │   1.0 - 5.0     │  │   1.0 - 5.0     │  │   1.0 - 5.0     │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │Founder Strength │  │  Expected CAC   │  │  Expected LTV   │             │
│  │ (track record)  │  │  (acquisition)  │  │   (lifetime)    │             │
│  │   1.0 - 5.0     │  │   1.0 - 5.0     │  │   1.0 - 5.0     │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                             │
│  GROUNDING RULE: Every score MUST have evidence_quote + source_url          │
│                  If no evidence → score = null (not guessed)                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        4. REVIEW (reviewer.py)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌────────────────────────┐    ┌────────────────────────────────┐          │
│  │ Validate Seed Company  │    │ Validate Similar Companies     │          │
│  │ • Problem statement    │    │ • Company exists?              │          │
│  │ • Tech edge accurate?  │    │ • Matches criteria?            │          │
│  │ • Target clients?      │    │ • No hallucinations?           │          │
│  └────────────────────────┘    └────────────────────────────────┘          │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────┐        │
│  │                    Explain Scoring                              │        │
│  │  • Why each score was given                                     │        │
│  │  • Evidence citations                                           │        │
│  │  • Confidence levels                                            │        │
│  └────────────────────────────────────────────────────────────────┘        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     5. VISUALIZATION (visualizer.py)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                    Expected LTV                                             │
│                        ▲                                                    │
│                    5.0 │  ┌─────────────┬─────────────┐                     │
│                        │  │ Low CAC     │ High CAC    │                     │
│                        │  │ High LTV    │ High LTV    │                     │
│                        │  │   ★ Best    │   ◆ Good    │                     │
│                    2.5 │──┼─────────────┼─────────────┤                     │
│                        │  │ Low CAC     │ High CAC    │                     │
│                        │  │ Low LTV     │ Low LTV     │                     │
│                        │  │   ○ OK      │   ✗ Avoid   │                     │
│                    1.0 │  └─────────────┴─────────────┘                     │
│                        └────────────────────────────────▶ Expected CAC      │
│                           1.0          2.5          5.0                     │
│                                                                             │
│  Interactive Plotly scatter plot with:                                      │
│  • Hover tooltips (dark theme, scores, summary)                             │
│  • Color by average score (Viridis colorscale)                              │
│  • Configurable X/Y axes                                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       6. EXPORT (reporting.py)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │    Excel     │    │     PDF      │    │    Email     │                  │
│  │  • Summary   │    │  • Details   │    │  • SMTP      │                  │
│  │  • Details   │    │  • Scores    │    │  • PDF att.  │                  │
│  │  • Evidence  │    │  • Founders  │    │  • Summary   │                  │
│  └──────────────┘    └──────────────┘    └──────────────┘                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘


## Data Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   config    │     │   search    │     │   scorer    │     │  reviewer   │
│    .py      │────▶│    .py      │────▶│    .py      │────▶│    .py      │
│             │     │             │     │             │     │             │
│ PORTFOLIO   │     │ SearchResult│     │ScoredCompany│     │ReviewResult │
│ COMPANIES   │     │  objects    │     │  objects    │     │  objects    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           │                   │                   │
                           │                   │                   │
                           ▼                   ▼                   ▼
                    ┌─────────────────────────────────────────────────┐
                    │                    app.py                        │
                    │              (Streamlit UI)                      │
                    │                                                  │
                    │  • Session state management                      │
                    │  • User configuration                            │
                    │  • Results display (tabs)                        │
                    │  • Export buttons                                │
                    └─────────────────────────────────────────────────┘
                                          │
                                          ▼
                    ┌─────────────────────────────────────────────────┐
                    │              visualizer.py                       │
                    │              reporting.py                        │
                    │                                                  │
                    │  • 2x2 Matrix (Plotly)                          │
                    │  • Excel/PDF/Email exports                       │
                    └─────────────────────────────────────────────────┘
```


## External Services

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          EXTERNAL SERVICES                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │   Gemini API    │    │   Tavily API    │    │    Langfuse     │         │
│  │  (Google AI)    │    │  (Web Search)   │    │ (Observability) │         │
│  ├─────────────────┤    ├─────────────────┤    ├─────────────────┤         │
│  │ • Extraction    │    │ • MENAT startup │    │ • Trace LLM     │         │
│  │ • Scoring       │    │   search        │    │   calls         │         │
│  │ • Summarization │    │ • Source URLs   │    │ • Debug errors  │         │
│  │ • Review        │    │ • Snippets      │    │ • Monitor costs │         │
│  │                 │    │                 │    │                 │         │
│  │ Model:          │    │ Max results: 10 │    │ Dashboard:      │         │
│  │ gemini-2.5-flash│    │                 │    │ cloud.langfuse  │         │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```


## File Structure

```
alpha_scout/
├── app.py              # Streamlit UI (main entry point)
├── config.py           # Portfolio companies, scoring dimensions, sources
├── models.py           # Data classes (SearchResult, ScoredCompany, etc.)
├── search.py           # Tavily search + Gemini extraction
├── scorer.py           # Multi-dimensional scoring with evidence
├── reviewer.py         # Validation agent (no hallucinations)
├── visualizer.py       # Plotly 2x2 matrix
├── reporting.py        # Excel, PDF, Email exports
├── llm_client.py       # Gemini API wrapper with grounding
├── tracing.py          # Langfuse observability
├── requirements.txt    # Python dependencies
├── .env                # API keys (not committed)
└── docs/
    └── architecture.md # This file
```


## Grounding Guarantee

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         GROUNDING RULE                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Every piece of information MUST be grounded in source data:                │
│                                                                             │
│  ✓ Score has evidence_quote from source                                     │
│  ✓ Score has source_url for verification                                    │
│  ✓ If no evidence exists → return "N/A" (never guess)                       │
│  ✓ Reviewer validates no hallucinations                                     │
│                                                                             │
│  This is enforced at:                                                       │
│  • llm_client.py — grounding instruction prepended to every prompt          │
│  • scorer.py — requires evidence for every score                            │
│  • reviewer.py — validates all outputs                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```
