"""
Jasoor Alpha Scout — Streamlit UI

This is the main entry point. Run with: streamlit run app.py

Flow:
1. User selects a seed portfolio company
2. User configures search parameters and sources
3. System searches for similar companies via Tavily
4. System scores each company on 4 dimensions via Gemini
5. User views results on a 2x2 matrix and comparison table
6. User can export PDF or send email report
"""

import os
import logging
from typing import List

import streamlit as st
from dotenv import load_dotenv

# Load environment variables from .env file FIRST
# This must happen before importing other modules that use env vars
load_dotenv()

# For Streamlit Cloud: load secrets into environment variables
# Streamlit Cloud uses st.secrets, not .env files
try:
    import streamlit as st
    if hasattr(st, 'secrets'):
        for key in ['GEMINI_API_KEY', 'TAVILY_API_KEY', 'LANGFUSE_PUBLIC_KEY', 'LANGFUSE_SECRET_KEY', 'LANGFUSE_HOST']:
            if key in st.secrets:
                os.environ[key] = st.secrets[key]
except Exception:
    pass  # Not running in Streamlit yet

from config import PORTFOLIO_COMPANIES, SCORING_DIMENSIONS, DEFAULT_SOURCES, BENCHMARK_MENA_STARTUPS, SCOUT_MODES
from ingest import get_simulated_inbound, extract_company_from_website, extract_company_from_text
from models import ScoredCompany
from search import search_similar_companies  # Primary: Tavily with improved query
from source_enrichment import enrich_search_results, find_funding_stage, is_early_stage, fetch_website_content
from scorer import score_companies
from visualizer import create_matrix_plot, get_axis_options, AXIS_LABELS
from reporting import (
    generate_markdown_table,
    generate_detailed_report,
    generate_pdf_report,
    send_email_report,
)
from reviewer import run_full_review, ReviewResult
from tracing import flush_langfuse, evaluate_enrichment_batch, evaluate_with_llm_judge, create_trace
from persistence import (
    init_db, save_search, load_search, load_search_by_share_id, list_searches, delete_search,
    add_to_target_list, get_target_list, remove_from_target_list, is_in_target_list,
    schedule_search, get_scheduled_searches, delete_scheduled_search, toggle_scheduled_search,
    save_feedback, get_blacklist, get_blacklist_stats, remove_from_blacklist, clear_blacklist,
)
from vc_chat import chat_with_vc_analyst, get_suggested_prompts
from source_enrichment import enrich_search_results, CompanyEnrichment, DEFAULT_MAX_EMPLOYEES

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Generate a unique session ID for Langfuse tracking
import uuid
if "langfuse_session_id" not in st.session_state:
    st.session_state.langfuse_session_id = f"session_{uuid.uuid4().hex[:8]}"
if "langfuse_user_id" not in st.session_state:
    st.session_state.langfuse_user_id = f"user_{uuid.uuid4().hex[:8]}"

# ---------------------------------------------------------------------------
# Page Config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Alpha Scout — Jasoor Ventures",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Jasoor Brand Styling
# ---------------------------------------------------------------------------
# Colors from jasoor.vc: deep navy background, mint/teal accent

st.markdown("""
<style>
    /* Main background - deep navy like Jasoor */
    .stApp {
        background: #0f0f23 !important;
    }
    
    /* Sidebar styling - slightly lighter navy, wider by default */
    [data-testid="stSidebar"] {
        background: #12122a !important;
        border-right: 1px solid #2a2a4a;
        min-width: 380px !important;
        width: 380px !important;
    }
    
    /* Make sidebar content area wider */
    [data-testid="stSidebar"] > div:first-child {
        width: 380px !important;
    }
    
    /* All text white by default */
    .stApp, .stApp p, .stApp span, .stApp label {
        color: #ffffff !important;
    }
    
    /* Headers - white, clean */
    h1, h2, h3 {
        color: #ffffff !important;
        font-family: 'Georgia', serif;
        font-weight: 300;
    }
    
    /* Subheaders - mint accent */
    .stApp h2, .stApp h3 {
        color: #7dd3c0 !important;
    }
    
    /* Primary buttons - mint/teal rounded like Jasoor */
    .stButton > button[kind="primary"], 
    .stButton > button[data-testid="baseButton-primary"] {
        background: #7dd3c0 !important;
        color: #0f0f23 !important;
        border: none !important;
        border-radius: 25px !important;
        font-weight: 500;
        padding: 0.5rem 2rem;
    }
    
    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="baseButton-primary"]:hover {
        background: #9de4d4 !important;
        color: #0f0f23 !important;
    }
    
    /* Secondary buttons - outlined mint */
    .stButton > button {
        border: 1px solid #7dd3c0 !important;
        color: #7dd3c0 !important;
        background: transparent !important;
        border-radius: 25px !important;
    }
    
    .stButton > button:hover {
        background: rgba(125, 211, 192, 0.1) !important;
    }
    
    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #1a1a2e;
        border-radius: 8px;
        gap: 0;
    }
    
    .stTabs [data-baseweb="tab"] {
        color: #888 !important;
        background: transparent;
    }
    
    .stTabs [aria-selected="true"] {
        color: #7dd3c0 !important;
        border-bottom: 2px solid #7dd3c0 !important;
    }
    
    /* Expanders */
    .streamlit-expanderHeader {
        background-color: #1a1a2e !important;
        border: 1px solid #2a2a4a;
        border-radius: 8px;
        color: #ffffff !important;
    }
    
    /* Info/Alert boxes */
    [data-testid="stAlert"] {
        background-color: #1a1a2e !important;
        border: 1px solid #2a2a4a !important;
        color: #ffffff !important;
    }
    
    /* Sliders - mint accent with readable hover */
    .stSlider > div > div > div > div {
        background-color: #7dd3c0 !important;
    }
    
    /* Slider thumb hover - darker mint for readability */
    .stSlider [data-baseweb="slider"] [role="slider"]:hover,
    .stSlider [data-baseweb="slider"] [role="slider"]:focus {
        background-color: #5bc4ad !important;
        box-shadow: 0 0 0 4px rgba(125, 211, 192, 0.3) !important;
    }
    
    /* Slider value text - ensure readable */
    .stSlider [data-testid="stTickBarMin"],
    .stSlider [data-testid="stTickBarMax"],
    .stSlider [data-baseweb="slider"] div {
        color: #7dd3c0 !important;
    }
    
    /* Text inputs */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        background-color: #1a1a2e !important;
        border: 1px solid #2a2a4a !important;
        color: #ffffff !important;
    }
    
    /* Selectbox */
    .stSelectbox > div > div,
    [data-baseweb="select"] {
        background-color: #1a1a2e !important;
        border: 1px solid #2a2a4a !important;
    }
    
    [data-baseweb="select"] span {
        color: #ffffff !important;
    }
    
    /* Checkboxes - mint when checked */
    .stCheckbox label span {
        color: #cccccc !important;
    }
    
    [data-testid="stCheckbox"] svg {
        fill: #7dd3c0 !important;
    }
    
    /* Dividers */
    hr {
        border-color: #2a2a4a !important;
    }
    
    /* Caption text - muted */
    .stCaption, small {
        color: #888888 !important;
    }
    
    /* Status containers */
    [data-testid="stStatusWidget"] {
        background-color: #1a1a2e !important;
    }
    
    /* Metric values */
    [data-testid="stMetricValue"] {
        color: #7dd3c0 !important;
    }
    
    /* Success box */
    .element-container .stSuccess {
        background-color: rgba(125, 211, 192, 0.1) !important;
        border: 1px solid #7dd3c0 !important;
    }
    
    /* Warning box */
    .element-container .stWarning {
        background-color: rgba(255, 193, 7, 0.1) !important;
        border: 1px solid #ffc107 !important;
    }
    
    /* Jasoor title styling */
    .jasoor-title {
        font-family: 'Georgia', serif;
        font-size: 1.5rem;
        color: #7dd3c0 !important;
        font-weight: 300;
        letter-spacing: 3px;
        text-transform: uppercase;
    }
    
    .jasoor-subtitle {
        color: #888888 !important;
        font-size: 0.85rem;
        font-style: italic;
        font-family: 'Georgia', serif;
    }
    
    /* Mint highlight text */
    .mint-text {
        color: #7dd3c0 !important;
    }
    
    /* Plot backgrounds */
    .js-plotly-plot .plotly .bg {
        fill: #0f0f23 !important;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------------------------
# Streamlit reruns the script on every interaction. Session state persists
# data across reruns so we don't lose search results when the user clicks a button.

if "search_results" not in st.session_state:
    st.session_state.search_results = []

if "scored_companies" not in st.session_state:
    st.session_state.scored_companies = []

if "search_complete" not in st.session_state:
    st.session_state.search_complete = False

if "scoring_complete" not in st.session_state:
    st.session_state.scoring_complete = False

if "review_result" not in st.session_state:
    st.session_state.review_result = None

if "review_complete" not in st.session_state:
    st.session_state.review_complete = False

if "scout_mode" not in st.session_state:
    st.session_state.scout_mode = "portfolio"

if "current_search_id" not in st.session_state:
    st.session_state.current_search_id = None

# Initialize SQLite database (creates tables if they don't exist)
init_db()


# ---------------------------------------------------------------------------
# Sidebar — Configuration
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown('<p class="jasoor-title">ALPHA SCOUT</p>', unsafe_allow_html=True)
    st.markdown('<p class="jasoor-subtitle">For the courageous investor</p>', unsafe_allow_html=True)

    st.divider()
    
    # ── LOAD PREVIOUS SEARCH ──────────────────────────────────────────────────
    with st.expander("📂 Load Previous Search", expanded=False):
        st.caption("*Pick up where you left off*")
        
        recent_searches = list_searches(limit=10)
        if recent_searches:
            # Format search options for display
            search_options = {
                s["id"]: f"{s['benchmark_label']} — {s['num_results']} results ({s['created_at'][:10]})"
                for s in recent_searches
            }
            
            selected_search_id = st.selectbox(
                "Recent searches:",
                options=list(search_options.keys()),
                format_func=lambda x: search_options[x],
                key="load_search_select",
            )
            
            if st.button("📂 Load Search", key="load_search_btn", use_container_width=True):
                loaded = load_search(selected_search_id)
                if loaded:
                    st.session_state.search_results = loaded["search_results"]
                    st.session_state.scored_companies = loaded["scored_companies"]
                    st.session_state.current_search_id = selected_search_id
                    st.session_state.search_complete = True
                    st.toast(f"✅ Loaded: {loaded['metadata']['benchmark_label']}")
                    st.rerun()
                else:
                    st.error("Failed to load search")
        else:
            st.info("No previous searches yet. Run a search to save it.")
    
    st.divider()

    # ── MODE SELECTOR ──────────────────────────────────────────────────────
    # Primary choice: which pipeline to use. All modes share the same scorer.
    scout_mode = st.radio(
        "How are you sourcing deals?",
        options=list(SCOUT_MODES.keys()),
        format_func=lambda x: SCOUT_MODES[x]["label"],
        key="scout_mode_radio",
        help="All modes score companies on the same 4 dimensions.",
    )
    st.caption(f"*{SCOUT_MODES[scout_mode]['description']}*")

    st.divider()

    # Defaults for all modes — overridden in the blocks below
    benchmark_label = "Scouting"
    custom_attrs = None
    selected_criteria = []
    location = "MENA GCC"
    max_results = 5
    custom_sources = DEFAULT_SOURCES
    all_exclusions = []
    target_stage = "Before Series A"
    benchmark_company = list(BENCHMARK_MENA_STARTUPS.keys())[0]
    inbound_source = "demo"
    website_urls_text = ""
    # Enrichment defaults (overridden in search filters section)
    enrich_with_linkedin = False  # Disabled by default for Inbound mode
    enable_size_filter = False
    max_employees = DEFAULT_MAX_EMPLOYEES
    mena_only = True
    early_stage_only = True
    max_source_age = 180
    excluded_industries = []  # Industries to filter out
    pitchdeck_company_name = ""
    pitchdeck_text = ""

    # ── STEP 1 ─────────────────────────────────────────────────────────────
    st.subheader(SCOUT_MODES[scout_mode]["step1_title"])

    # --- Seed Company Selection ---
    if scout_mode == "portfolio":
        st.caption("*Find companies similar to your portfolio based on all 10 attributes*")

        seed_company = st.selectbox(
            "Portfolio company to benchmark against:",
            options=list(PORTFOLIO_COMPANIES.keys()),
            help="Select a Jasoor portfolio company as your reference point.",
        )
        benchmark_label = seed_company
    else:
        # For non-portfolio modes, seed_company will be set to benchmark_label later
        seed_company = None  # Will be set after benchmark selection

    # ── MODE 1: Portfolio Benchmark ────────────────────────────────────────
    if scout_mode == "portfolio":
        seed_data = PORTFOLIO_COMPANIES[seed_company]
        # 10 attribute keys: 6 core + 4 moat
        all_attr_keys = [
            "problem_statement", "target_clients", "industry_vertical",
            "technology", "location", "company_size",
            "tech_moat", "tech_stack", "offer_moat", "sales_distribution_moat",
        ]
        # Init session state with all 10 attributes from config
        if f"seed_attrs_{seed_company}" not in st.session_state:
            st.session_state[f"seed_attrs_{seed_company}"] = {
                k: seed_data.get(k, "") for k in all_attr_keys
            }
        with st.expander("📝 Edit Seed Attributes (10 attributes)", expanded=False):
            st.caption("*All 10 attributes drive the eligibility search.*")
            ea = st.session_state[f"seed_attrs_{seed_company}"]
            # Render text_area for long fields, text_input for short ones
            for key, label, height in [
                ("problem_statement", "Problem Statement", 60),
                ("target_clients", "Target Clients", 60),
                ("industry_vertical", "Industry Vertical", None),
                ("technology", "Technology", 60),
                ("location", "Location", None),
                ("company_size", "Company Size", None),
                ("tech_moat", "Tech Moat", 60),
                ("tech_stack", "Tech Stack", 60),
                ("offer_moat", "Offer Moat", 60),
                ("sales_distribution_moat", "Sales / Distribution Moat", 60),
            ]:
                if height:
                    ea[key] = st.text_area(
                        f"**{label}**", value=ea[key], height=height,
                        key=f"ea_{key}_{seed_company}",
                    )
                else:
                    ea[key] = st.text_input(
                        f"**{label}**", value=ea[key],
                        key=f"ea_{key}_{seed_company}",
                    )
            st.session_state[f"seed_attrs_{seed_company}"] = ea
        custom_attrs = st.session_state[f"seed_attrs_{seed_company}"]
        st.info(f"**Industry:** {custom_attrs.get('industry_vertical', 'N/A')}")

    # ── MODE 2: MENA Success Stories ───────────────────────────────────────
    elif scout_mode == "mena_success":
        st.caption("*Select proven MENA companies — find earlier-stage startups solving similar problems*")
        
        # Option to add custom company
        use_custom_company = st.checkbox("➕ Add a custom company (not in list)", value=False)
        
        if use_custom_company:
            # Custom company entry
            st.info("📝 **Add a custom benchmark company** — Please fill in all fields for accurate similarity search.")
            
            custom_company_name = st.text_input("Company name:", placeholder="e.g., Careem, Souq, Noon")
            
            if custom_company_name:
                # Initialize session state for custom company
                if f"custom_bm_{custom_company_name}" not in st.session_state:
                    st.session_state[f"custom_bm_{custom_company_name}"] = {
                        "description": "",
                        "problem_statement": "",
                        "target_clients": "",
                        "industry_vertical": "",
                        "technology": "",
                        "location": "MENA",
                        "company_size": "",
                    }
                
                custom_bm = st.session_state[f"custom_bm_{custom_company_name}"]
                
                with st.expander("📝 Fill in company details (required for similarity search)", expanded=True):
                    custom_bm["description"] = st.text_area(
                        "Description:", value=custom_bm["description"], height=60,
                        placeholder="One-line description of what the company does"
                    )
                    custom_bm["problem_statement"] = st.text_area(
                        "Problem Statement:", value=custom_bm["problem_statement"], height=60,
                        placeholder="What pain point does this company solve?"
                    )
                    custom_bm["target_clients"] = st.text_input(
                        "Target Clients:", value=custom_bm["target_clients"],
                        placeholder="B2B: enterprises, SMBs / B2C: consumers"
                    )
                    custom_bm["industry_vertical"] = st.text_input(
                        "Industry/Sector:", value=custom_bm["industry_vertical"],
                        placeholder="e.g., Fintech, HealthTech, E-commerce"
                    )
                    custom_bm["technology"] = st.text_area(
                        "Technology:", value=custom_bm["technology"], height=60,
                        placeholder="Key technologies, AI, APIs, platforms used"
                    )
                    custom_bm["location"] = st.text_input(
                        "Location:", value=custom_bm["location"],
                        placeholder="e.g., UAE / Saudi Arabia / GCC"
                    )
                    custom_bm["company_size"] = st.text_input(
                        "Company Size/Stage:", value=custom_bm["company_size"],
                        placeholder="e.g., Series C, 500+ employees"
                    )
                    
                    st.session_state[f"custom_bm_{custom_company_name}"] = custom_bm
                
                # Validate required fields
                required_fields = ["description", "problem_statement", "industry_vertical", "technology"]
                missing_fields = [f for f in required_fields if not custom_bm.get(f)]
                
                if missing_fields:
                    st.warning(f"⚠️ Please fill in: {', '.join(missing_fields)} for accurate similarity search.")
                else:
                    st.success(f"✅ **{custom_company_name}** is ready for similarity search!")
                
                selected_benchmarks = [custom_company_name]
                benchmark_label = custom_company_name
                bm_data = dict(custom_bm)
                custom_attrs = dict(bm_data)
            else:
                st.warning("Please enter a company name.")
                selected_benchmarks = [list(BENCHMARK_MENA_STARTUPS.keys())[0]]
                benchmark_label = selected_benchmarks[0]
                bm_data = dict(BENCHMARK_MENA_STARTUPS[selected_benchmarks[0]])
                custom_attrs = dict(bm_data)
        else:
            # Multi-select for benchmark companies (existing flow)
            selected_benchmarks = st.multiselect(
                "Benchmark MENA companies:",
                options=list(BENCHMARK_MENA_STARTUPS.keys()),
                default=[list(BENCHMARK_MENA_STARTUPS.keys())[0]],
                help="Select one or more successful MENA companies as templates.",
            )
            
            if not selected_benchmarks:
                st.warning("Please select at least one benchmark company.")
                selected_benchmarks = [list(BENCHMARK_MENA_STARTUPS.keys())[0]]
            
            benchmark_label = ", ".join(selected_benchmarks)
            
            # Show info for each selected benchmark
            for bm_name in selected_benchmarks:
                bm_info = BENCHMARK_MENA_STARTUPS[bm_name]
                st.info(
                    f"**{bm_name}** — {bm_info.get('achieved_stage', 'N/A')}\n\n"
                    f"{bm_info.get('description', '')}"
                )
        
        target_stage = st.selectbox(
            "Find companies at or below stage:",
            options=["Before Series A", "Before Series B", "Before Series C"],
            index=0,
            help="Alpha Scout targets companies earlier than this funding stage.",
        )
        
        # Override company_size to guide the search toward earlier-stage companies
        stage_hint = {
            "Before Series A": "pre-seed or seed stage, early traction only",
            "Before Series B": "pre-seed, seed, or Series A — early growth stage",
            "Before Series C": "seed to Series B — proven model, pre-scale",
        }
        
        # Only merge from predefined benchmarks if NOT using custom company
        if not use_custom_company:
            # Merge attributes from all selected benchmarks
            # Uses the first selected company as base, enriches with others
            bm_data = dict(BENCHMARK_MENA_STARTUPS[selected_benchmarks[0]])
            if len(selected_benchmarks) > 1:
                # Combine problem statements, target clients, etc. from all selected
                for key in ["problem_statement", "target_clients", "industry_vertical", "technology"]:
                    combined = "; ".join([
                        BENCHMARK_MENA_STARTUPS[bm].get(key, "") 
                        for bm in selected_benchmarks if BENCHMARK_MENA_STARTUPS[bm].get(key)
                    ])
                    bm_data[key] = combined
            custom_attrs = dict(bm_data)
        
        # Add stage hint to custom_attrs
        custom_attrs["company_size"] = stage_hint[target_stage]
        
        # Set seed_company to the selected benchmark for reports
        seed_company = benchmark_label

    # ── MODE 3: Inbound Candidates ─────────────────────────────────────────
    elif scout_mode == "inbound":
        benchmark_label = "Inbound Candidates"
        seed_company = "Inbound Candidates"  # For reports
        inbound_source = st.radio(
            "Candidate source:",
            options=["demo", "websites", "pitchdeck"],
            format_func=lambda x: {
                "demo": "📋 Use demo candidates (4 MENA startups)",
                "websites": "🌐 Enter company website URLs",
                "pitchdeck": "📄 Paste pitchdeck text",
            }[x],
            help="Choose how to load your inbound candidates.",
        )
        if inbound_source == "demo":
            st.success("**4 demo candidates loaded** — Halio, Carebot, Naqla, Tarbiyah")
            st.caption("*Simulated MENA startup pitches for demonstration.*")
        elif inbound_source == "websites":
            website_urls_text = st.text_area(
                "Company website URLs (one per line):",
                value="",
                height=100,
                placeholder="https://company1.com\nhttps://company2.io",
                help="Each URL will be crawled and structured by AI.",
            )
            n_urls = len([u for u in website_urls_text.split("\n") if u.strip()])
            if n_urls:
                st.info(f"**{n_urls} URL(s) to process**")
        elif inbound_source == "pitchdeck":
            pitchdeck_company_name = st.text_input(
                "Company name:", placeholder="e.g., MyStartup",
            )
            pitchdeck_text = st.text_area(
                "Paste pitchdeck or email pitch text:",
                value="",
                height=150,
                placeholder="Paste the pitch, executive summary, or key slide content here...",
                help="Gemini will extract structured data from this text.",
            )

    st.divider()

    # ── SEARCH FILTERS (Modes 1 & 2 only — inbound skips this) ─────────────
    if scout_mode in ["portfolio", "mena_success"]:
        st.markdown("**🎯 Similarity Filters**")
        st.caption("*Which dimensions must match for a company to be eligible?*")

        # 6 core attributes (selected by default)
        CORE_CRITERIA = {
            "problem_statement": "Problem Statement",
            "target_clients": "Target Clients",
            "industry_vertical": "Industry Vertical",
            "technology": "Technology",
            "location": "Location",
            "company_size": "Company Size",
        }
        # 4 moat attributes (unselected by default — advanced filters)
        MOAT_CRITERIA = {
            "tech_moat": "Tech Moat",
            "tech_stack": "Tech Stack",
            "offer_moat": "Offer Moat",
            "sales_distribution_moat": "Sales / Distribution Moat",
        }
        
        selected_criteria = []
        
        # Core attributes (2 columns, selected by default)
        cols = st.columns(2)
        for i, (key, label) in enumerate(CORE_CRITERIA.items()):
            with cols[i % 2]:
                if st.checkbox(label, value=True, key=f"criteria_{key}"):
                    selected_criteria.append(key)
        
        # Moat attributes (2 columns, unselected by default)
        st.caption("*Advanced moat filters (optional):*")
        cols2 = st.columns(2)
        for i, (key, label) in enumerate(MOAT_CRITERIA.items()):
            with cols2[i % 2]:
                if st.checkbox(label, value=False, key=f"criteria_{key}"):
                    selected_criteria.append(key)
        st.session_state.search_criteria = selected_criteria

        st.divider()

        # Location defaults from attributes for Mode 1, from benchmark for Mode 2
        default_location = "MENA GCC"
        if scout_mode == "portfolio" and f"seed_attrs_{seed_company}" in st.session_state:
            default_location = st.session_state[f"seed_attrs_{seed_company}"].get("location", "MENA GCC")
        elif scout_mode == "mena_success":
            default_location = bm_data.get("location", "MENA GCC")
    
        location = st.text_input(
            "Geographic focus:",
            value=default_location,
            help="Target region based on your market knowledge.",
        )
        max_results = st.slider(
            "Companies to analyze:",
            min_value=5, max_value=100, value=10,
        )

        with st.expander("🔍 Leverage Your Trusted Sources"):
            st.caption("*Add or remove sources based on your network and research channels*")
            sources_text = st.text_area(
                "Sources (one per line):",
                value="\n".join(DEFAULT_SOURCES),
                height=150,
            )
            custom_sources = [s.strip() for s in sources_text.split("\n") if s.strip()]

        with st.expander("📅 Source Freshness Filter"):
            st.caption("*Only include recent sources to avoid stale information*")
            max_source_age = st.slider(
                "Maximum source age (days):",
                min_value=7, max_value=365, value=180,
                help="Sources older than this will be filtered out. Default: 180 days (6 months)"
            )
            show_source_dates = st.checkbox("Show source dates in results", value=True)
        
        with st.expander("👥 Company Size Filter", expanded=True):
            st.caption("*Filter out large companies — we want early-stage startups*")
            enable_size_filter = st.checkbox(
                "Enable company size filter",
                value=True,
                help="Filter out companies with more than the specified number of employees"
            )
            max_employees = st.slider(
                "Maximum employees:",
                min_value=10, max_value=500, value=DEFAULT_MAX_EMPLOYEES,
                help="Companies larger than this will be filtered out. Default: 100",
                disabled=not enable_size_filter,
            )
            enrich_with_linkedin = st.checkbox(
                "Enrich with LinkedIn data",
                value=True,
                help="Search LinkedIn for verified employee count, location, and founders"
            )
            if enable_size_filter:
                st.info(f"⚠️ Companies with >{max_employees} employees will be filtered out")
        
        with st.expander("📍 MENA Location Filter", expanded=True):
            st.caption("*Only include companies headquartered in MENA region*")
            mena_only = st.checkbox(
                "MENA headquarters only",
                value=True,
                help="Filter out companies not headquartered in Middle East & North Africa"
            )
            if mena_only:
                st.info("⚠️ Only companies in UAE, Saudi Arabia, Egypt, Jordan, etc. will be included")
        
        with st.expander("🚀 Funding Stage Filter", expanded=True):
            st.caption("*Only include early-stage companies (Series B and before)*")
            early_stage_only = st.checkbox(
                "Series B and earlier only",
                value=True,
                help="Filter out Series C, D, E, IPO, and public companies"
            )
            if early_stage_only:
                st.info("⚠️ Only Pre-seed, Seed, Series A, Series B companies will be included")
        
        with st.expander("🚫 Exclude Companies"):
            st.caption("*Exclude specific companies from search results*")
            
            # Auto-populate with filtered-out companies from previous search
            filtered_out_names = []
            if "filtered_out" in st.session_state and st.session_state.filtered_out:
                filtered_out_names = [c.name for c in st.session_state.filtered_out]
                st.info(f"💡 {len(filtered_out_names)} companies were filtered out in last search")
            
            # Get blacklisted companies
            blacklist = get_blacklist()
            blacklist_names = [b["company_name"] for b in blacklist] if blacklist else []
            
            # Combine suggestions
            suggested_exclusions = list(set(filtered_out_names + blacklist_names))
            
            # Multi-select for excluded companies
            exclude_companies = st.multiselect(
                "Companies to exclude:",
                options=suggested_exclusions if suggested_exclusions else [],
                default=[],
                help="These companies will be skipped in search results"
            )
            
            # Manual entry for additional companies
            manual_exclude_text = st.text_area(
                "Additional companies to exclude (one per line):",
                value="",
                height=60,
            )
            manual_exclude = [c.strip() for c in manual_exclude_text.split("\n") if c.strip()]
            all_excluded_companies = list(set(exclude_companies + manual_exclude))
            
            if all_excluded_companies:
                st.warning(f"**Excluding {len(all_excluded_companies)} companies:** {', '.join(all_excluded_companies[:5])}{'...' if len(all_excluded_companies) > 5 else ''}")
        
        with st.expander("🚫 Information Exclusion"):
            st.caption("*Exclude news types that signal the opportunity is gone*")
            col1, col2 = st.columns(2)
            with col1:
                exclude_fundraising = st.checkbox("Exclude fundraising news", value=False)
            with col2:
                exclude_acquisitions = st.checkbox("Exclude acquisition news", value=False)
            preset_excl = []
            if exclude_fundraising:
                preset_excl.extend(["raises", "raised", "funding round", "secures funding", "closes round"])
            if exclude_acquisitions:
                preset_excl.extend(["acquired by", "acquisition", "merger", "bought by"])
            custom_excl_text = st.text_area("Custom keywords (one per line):", value="", height=60)
            custom_excl = [e.strip() for e in custom_excl_text.split("\n") if e.strip()]
            # Mode 2: automatically exclude advanced stages
            stage_excl = []
            if scout_mode == "mena_success":
                stage_map = {
                    "Before Series A": ["series b", "series c", "series d", "unicorn", "ipo"],
                    "Before Series B": ["series c", "series d", "series e", "unicorn"],
                    "Before Series C": ["series d", "series e", "unicorn", "late stage"],
                }
                stage_excl = stage_map.get(target_stage, [])
            all_exclusions = preset_excl + custom_excl + stage_excl
            if all_exclusions:
                st.info(f"**Active exclusions:** {', '.join(all_exclusions[:8])}{'...' if len(all_exclusions) > 8 else ''}")
        
        with st.expander("🏭 Industry Exclusion Filter"):
            st.caption("*Exclude companies in specific industries/sectors*")
            excluded_industries_text = st.text_area(
                "Industries to exclude (one per line):",
                value="",
                height=80,
                placeholder="e.g., Gambling\nCrypto\nAdult content\nTobacco",
                help="Companies in these industries will be filtered out after search"
            )
            excluded_industries = [i.strip().lower() for i in excluded_industries_text.split("\n") if i.strip()]
            if excluded_industries:
                st.warning(f"**Excluding industries:** {', '.join(excluded_industries)}")
    else:
        # Inbound mode: still allow industry exclusion
        excluded_industries = []
    
    # Global industry exclusion for ALL modes (including inbound)
    if scout_mode == "inbound":
        with st.expander("🏭 Industry Exclusion Filter"):
            st.caption("*Exclude companies in specific industries/sectors*")
            excluded_industries_text = st.text_area(
                "Industries to exclude (one per line):",
                value="",
                height=80,
                placeholder="e.g., Gambling\nCrypto\nAdult content\nTobacco",
                help="Companies in these industries will be filtered out",
                key="inbound_industry_exclusion"
            )
            excluded_industries = [i.strip().lower() for i in excluded_industries_text.split("\n") if i.strip()]
            if excluded_industries:
                st.warning(f"**Excluding industries:** {', '.join(excluded_industries)}")

    st.divider()

    # --- Scoring Weights & Criteria ---
    st.subheader("2. Import Your Brain")
    st.caption("*Define scoring criteria based on your investment expertise*")

    # Default criteria descriptions (editable)
    DEFAULT_CRITERIA_DESC = {
        "offer_power": "Value proposition strength using Hormozi equation (Dream Outcome × Perceived Likelihood) / (Time Delay × Effort)",
        "sales_ability": "Evidence of traction: revenue, users, partnerships, pilots",
        "tech_moat": "Defensibility: patents, proprietary tech, network effects, data moats",
        "founder_strength": "Track record: prior exits, domain expertise, team completeness",
    }

    weights = {}
    criteria_descriptions = {}

    with st.expander("📝 Customize Scoring Criteria", expanded=False):
        st.caption("*Modify what each dimension evaluates based on your expertise*")
        for dim_key, dim_config in SCORING_DIMENSIONS.items():
            criteria_descriptions[dim_key] = st.text_area(
                f"**{dim_config['label']}** criteria:",
                value=DEFAULT_CRITERIA_DESC.get(dim_key, dim_config.get("prompt_guidance", "")),
                height=80,
                key=f"criteria_desc_{dim_key}",
            )

    # Store custom criteria in session state for scorer
    st.session_state.custom_criteria = criteria_descriptions

    for dim_key, dim_config in SCORING_DIMENSIONS.items():
        weights[dim_key] = st.slider(
            dim_config["label"],
            min_value=0.0,
            max_value=1.0,
            value=dim_config["default_weight"],
            step=0.05,
            key=f"weight_{dim_key}",
        )

    # Normalize weights to sum to 1.0
    total_weight = sum(weights.values())
    if total_weight > 0:
        weights = {k: v / total_weight for k, v in weights.items()}

    st.divider()

    # --- Load Previous Search ---
    with st.expander("📂 Saved Searches", expanded=False):
        st.caption("*Resume a previous search session*")
        
        # Quick load by Share ID (from email link)
        st.markdown("##### 🔗 Load by Share ID")
        st.caption("Enter the Share ID from an email alert to load that search directly.")
        col_input, col_btn = st.columns([3, 1])
        with col_input:
            share_id_input = st.text_input(
                "Share ID",
                placeholder="e.g., AS-7F3K9X2M",
                label_visibility="collapsed",
                key="share_id_input"
            )
        with col_btn:
            if st.button("Load", key="load_by_share_id", use_container_width=True):
                if share_id_input:
                    loaded = load_search_by_share_id(share_id_input.strip())
                    if loaded:
                        st.session_state.search_results = loaded["search_results"]
                        st.session_state.scored_companies = loaded["scored_companies"]
                        st.session_state.scoring_complete = True
                        st.session_state.current_search_id = loaded["metadata"]["id"]
                        st.session_state.current_share_id = loaded["metadata"].get("share_id")
                        st.toast(f"✅ Loaded search: {loaded['metadata']['benchmark_label']}")
                        st.rerun()
                    else:
                        st.error(f"Share ID not found: {share_id_input}")
                else:
                    st.warning("Please enter a Share ID")
        
        st.divider()
        st.markdown("##### 📋 Recent Searches")
        past_searches = list_searches(limit=10)
        if past_searches:
            for ps in past_searches:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    mode_icon = {"portfolio": "📁", "mena_success": "🌟", "inbound": "📥"}.get(ps["scout_mode"], "📋")
                    share_badge = f"`{ps['share_id']}`" if ps.get('share_id') else ""
                    st.markdown(f"{mode_icon} **{ps['benchmark_label']}** — {ps['num_results']} results ({ps['grounding_score_avg']:.0%} grounded)")
                    st.caption(f"{share_badge} | {ps['created_at']}")
                with col2:
                    if st.button("Load", key=f"load_{ps['id']}", use_container_width=True):
                        loaded = load_search(ps["id"])
                        if loaded:
                            st.session_state.search_results = loaded["search_results"]
                            st.session_state.scored_companies = loaded["scored_companies"]
                            st.session_state.scoring_complete = True
                            st.session_state.current_search_id = ps["id"]
                            st.session_state.current_share_id = ps.get("share_id")
                            st.rerun()
                with col3:
                    if st.button("🗑️", key=f"del_search_{ps['id']}", help="Delete search"):
                        delete_search(ps["id"])
                        st.toast(f"Deleted search {ps['id']}")
                        st.rerun()
        else:
            st.info("No saved searches yet.")

    st.divider()
    
    # --- Scheduled Searches ---
    with st.expander("📅 Scheduled Searches", expanded=False):
        st.caption("*Automated searches with email reports*")
        st.warning("🚧 **Coming Soon** — Email scheduling will be enabled in the next release.")
        scheduled = get_scheduled_searches()
        if scheduled:
            for ss in scheduled:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    status_icon = "🟢" if ss["is_active"] else "⏸️"
                    st.markdown(f"{status_icon} **{ss['name']}**")
                    st.caption(f"{ss['schedule_time']} {ss['schedule_timezone']} | {ss['schedule_frequency']} | {ss['email_recipient']}")
                with col2:
                    if ss["is_active"]:
                        if st.button("⏸️", key=f"pause_sched_{ss['id']}", help="Pause"):
                            toggle_scheduled_search(ss["id"], False)
                            st.rerun()
                    else:
                        if st.button("▶️", key=f"resume_sched_{ss['id']}", help="Resume"):
                            toggle_scheduled_search(ss["id"], True)
                            st.rerun()
                with col3:
                    if st.button("🗑️", key=f"del_sched_{ss['id']}", help="Delete"):
                        delete_scheduled_search(ss["id"])
                        st.toast(f"Deleted schedule {ss['id']}")
                        st.rerun()
            st.markdown(f"**Total:** {len(scheduled)} scheduled")
        else:
            st.info("No scheduled searches. Run a search and schedule it!")

    st.divider()
    
    # --- Company Blacklist (Learning System) ---
    with st.expander("🧠 Learning System (Blacklist)", expanded=False):
        st.caption("*Companies that failed eligibility filters are skipped in future searches*")
        
        # Show stats
        stats = get_blacklist_stats()
        if stats["total"] > 0:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total", stats["total"])
            with col2:
                st.metric("Non-MENA", stats.get("non_mena", 0))
            with col3:
                st.metric("Too Large", stats.get("too_large", 0))
            with col4:
                st.metric("Late Stage", stats.get("late_stage", 0))
            
            st.markdown("---")
            st.markdown("**Blacklisted Companies:**")
            
            blacklist = get_blacklist()
            for entry in blacklist[:20]:  # Show first 20
                col1, col2, col3 = st.columns([3, 2, 1])
                with col1:
                    reason_emoji = {"non_mena": "🌍", "too_large": "👥", "late_stage": "📈"}.get(entry["reason"], "❌")
                    st.markdown(f"{reason_emoji} **{entry['company_name']}**")
                with col2:
                    st.caption(entry["details"] or entry["reason"])
                with col3:
                    if st.button("🔄", key=f"unblock_{entry['id']}", help="Remove from blacklist"):
                        remove_from_blacklist(entry["id"])
                        st.toast(f"Removed {entry['company_name']} from blacklist")
                        st.rerun()
            
            if len(blacklist) > 20:
                st.caption(f"*...and {len(blacklist) - 20} more*")
            
            st.markdown("---")
            if st.button("🗑️ Clear All Blacklist", type="secondary"):
                cleared = clear_blacklist()
                st.toast(f"Cleared {cleared} entries from blacklist")
                st.rerun()
        else:
            st.info("No companies blacklisted yet. The system will learn as you run searches.")

    st.divider()
    
    # --- Target List ---
    with st.expander("🎯 My Target List", expanded=False):
        st.caption("*Companies you're tracking — news alerts coming soon*")
        targets = get_target_list()
        if targets:
            for t in targets:
                col1, col2 = st.columns([4, 1])
                with col1:
                    priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(t["priority"], "⚪")
                    st.markdown(f"{priority_icon} **{t['name']}** — {t['sector'] or 'N/A'}")
                    st.caption(f"{t['location'] or 'N/A'} | {t['funding_stage'] or 'N/A'} | Added: {t['added_at'][:10]}")
                with col2:
                    if st.button("🗑️", key=f"rm_target_{t['id']}", help="Remove from list"):
                        remove_from_target_list(t["id"])
                        st.rerun()
            st.markdown(f"**Total:** {len(targets)} companies")
        else:
            st.info("No targets yet. Add companies from search results.")

    st.divider()

    # --- Action Buttons ---
    search_button = st.button("🎯 Scout & Analyze", type="primary", use_container_width=True)

    if st.session_state.scoring_complete:
        st.divider()
        st.subheader("4. Export")

        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Excel export - direct download button
            from reporting import generate_excel_export
            excel_data = generate_excel_export(
                benchmark_label,
                st.session_state.scored_companies,
            )
            st.download_button(
                "📊 Download Excel",
                data=excel_data,
                file_name=f"alpha_scout_{benchmark_label.replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        
        with col2:
            if st.button("📄 Download PDF", use_container_width=True):
                pdf_path = generate_pdf_report(
                    benchmark_label,
                    st.session_state.scored_companies,
                    top_n=3,
                )
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        "⬇️ Save PDF",
                        data=f.read(),
                        file_name="alpha_scout_report.pdf",
                        mime="application/pdf",
                    )
                os.remove(pdf_path)

        with col3:
            email_to = st.text_input("Email to:", placeholder="investor@jasoor.com")
            if st.button("📧 Send Email", use_container_width=True):
                if email_to:
                    with st.spinner("Sending..."):
                        success, message = send_email_report(
                            email_to,
                            benchmark_label,
                            st.session_state.scored_companies,
                            top_n=3,
                        )
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
                else:
                    st.warning("Enter an email address")


# ---------------------------------------------------------------------------
# Main Content Area
# ---------------------------------------------------------------------------

# Dynamic heading based on active mode
_mode_cfg = SCOUT_MODES[scout_mode]
if scout_mode == "portfolio":
    st.markdown(f"## {_mode_cfg['heading']}: **{benchmark_label}**")
elif scout_mode == "mena_success":
    st.markdown(f"## {_mode_cfg['heading']}: **{benchmark_label}** → {target_stage}")
else:
    st.markdown(f"## {_mode_cfg['heading']}")

# --- Search & Score Action ---
if search_button:
    # Reset state for a fresh run
    st.session_state.search_results = []
    st.session_state.scored_companies = []
    st.session_state.search_complete = False
    st.session_state.scoring_complete = False

    # ── STEP 1: Find / Load candidates ────────────────────────────────────
    # Modes 1 & 2 use Tavily search. Mode 3 ingests inbound pitches.

    if scout_mode in ["portfolio", "mena_success"]:
        # Search for companies similar to the benchmark using Tavily + Gemini
        with st.status("🔍 Searching for similar companies...", expanded=True) as status:
            st.write(f"Benchmark: **{benchmark_label}** | Location: {location}")
            try:
                # Pass custom_attrs as the seed (dict format) if user edited attributes
                # Otherwise pass the benchmark_label string for config lookup
                seed_input = custom_attrs if custom_attrs else benchmark_label
                
                # Determine target stage for search
                target_stage = "early-stage" if early_stage_only else "any"
                
                # PRIMARY: Tavily search with stage + MENA filters baked in
                # Searches ONLY the selected source domains
                if all_excluded_companies:
                    st.write(f"🚫 Excluding {len(all_excluded_companies)} companies from results")
                st.write(f"🔍 Searching {len(custom_sources)} sources for {target_stage} MENA startups (last {max_source_age} days)...")
                results = search_similar_companies(
                    seed=seed_input,
                    criteria=selected_criteria,
                    location=location,
                    sources=custom_sources,  # ONLY search these domains
                    exclusions=all_exclusions,
                    max_results=max_results,
                    target_stage=target_stage,
                    max_source_age_days=max_source_age,  # Source freshness filter
                    exclude_companies=all_excluded_companies,  # Exclude specific companies
                )
                
                # Step 1: Apply industry exclusion filter
                if excluded_industries and results:
                    st.write(f"🏭 Filtering by industry exclusions...")
                    before_count = len(results)
                    results = [
                        r for r in results 
                        if not any(excl in r.sector.lower() for excl in excluded_industries)
                    ]
                    excluded_by_industry = before_count - len(results)
                    if excluded_by_industry > 0:
                        st.write(f"⚠️ Excluded {excluded_by_industry} companies by industry filter")
                
                # Step 2: Enrichment - Website/LinkedIn verification + Stage verification
                filtered_out_companies = []
                enrichments = {}
                if enrich_with_linkedin and results:
                    st.write("🔗 Enriching with website, LinkedIn, and funding data...")
                    
                    # Create trace for Langfuse evaluation with user/session tracking
                    enrichment_trace = create_trace(
                        name="source_enrichment",
                        input_data={"company_count": len(results), "seed": benchmark_label},
                        metadata={"mode": scout_mode},
                        user_id=st.session_state.langfuse_user_id,
                        session_id=st.session_state.langfuse_session_id,
                    )
                    trace_id = enrichment_trace.id if enrichment_trace else None
                    
                    results, filtered_out_companies, enrichments = enrich_search_results(
                        results,
                        max_employees=max_employees if enable_size_filter else 9999,
                        mena_only=mena_only,
                        early_stage_only=early_stage_only,
                    )
                    
                    # Run Langfuse evaluations
                    if enrichments:
                        st.write("📊 Evaluating enrichment quality...")
                        metrics = evaluate_enrichment_batch(trace_id, enrichments, results)
                        st.session_state.enrichment_metrics = metrics
                    
                    if filtered_out_companies:
                        filter_reasons = []
                        if enable_size_filter:
                            filter_reasons.append(f">{max_employees} employees")
                        if mena_only:
                            filter_reasons.append("non-MENA HQ")
                        if early_stage_only:
                            filter_reasons.append("later than Series B")
                        st.write(f"⚠️ Filtered out {len(filtered_out_companies)} companies ({', '.join(filter_reasons)})")
                
                st.session_state.search_results = results
                st.session_state.filtered_out = filtered_out_companies
                st.session_state.search_complete = True
                status.update(label=f"✅ Found {len(results)} companies", state="complete")
            except Exception as e:
                status.update(label=f"❌ Search failed: {e}", state="error")
                st.error(f"Search error: {e}")
                st.stop()

    elif scout_mode == "inbound":
        # Load inbound candidates from selected source (no Tavily search needed)
        with st.status("📥 Loading inbound candidates...", expanded=True) as status:
            try:
                results = []
                if inbound_source == "demo":
                    # Use the 4 simulated MENA startup pitches
                    results = get_simulated_inbound()
                    st.write(f"Loaded {len(results)} demo candidates")

                elif inbound_source == "websites":
                    # Crawl each URL and extract structured data via Gemini
                    urls = [u.strip() for u in website_urls_text.split("\n") if u.strip()]
                    for url in urls:
                        st.write(f"Extracting: {url}...")
                        r = extract_company_from_website(url)
                        if r:
                            results.append(r)

                elif inbound_source == "pitchdeck":
                    # Extract from pasted pitchdeck text via Gemini
                    if pitchdeck_company_name and pitchdeck_text:
                        st.write(f"Extracting: {pitchdeck_company_name}...")
                        r = extract_company_from_text(pitchdeck_company_name, pitchdeck_text)
                        if r:
                            results.append(r)

                if results:
                    # Step 1: Apply industry exclusion filter first
                    if excluded_industries:
                        st.write(f"🏭 Filtering by industry exclusions...")
                        before_count = len(results)
                        results = [
                            r for r in results 
                            if not any(excl in r.sector.lower() for excl in excluded_industries)
                        ]
                        excluded_by_industry = before_count - len(results)
                        if excluded_by_industry > 0:
                            st.write(f"⚠️ Excluded {excluded_by_industry} companies by industry filter")
                    
                    # Step 2: ALWAYS verify via website and LinkedIn (core for inbound)
                    # Use data from documents first, then verify/enrich via external sources
                    st.write("🔗 Verifying via website and LinkedIn...")
                    
                    # Create trace for Langfuse evaluation with user/session tracking
                    enrichment_trace = create_trace(
                        name="source_enrichment",
                        input_data={"company_count": len(results), "source": inbound_source},
                        metadata={"mode": "inbound"},
                        user_id=st.session_state.langfuse_user_id,
                        session_id=st.session_state.langfuse_session_id,
                    )
                    trace_id = enrichment_trace.id if enrichment_trace else None
                    
                    # Enrich and verify - this fills in missing data from website/LinkedIn
                    # If location/stage/employees found in documents, they're preserved
                    # If not found, enrichment will try to get them from external sources
                    results, filtered_out_companies, enrichments = enrich_search_results(
                        results,
                        max_employees=max_employees if enable_size_filter else 9999,
                        mena_only=mena_only,
                        early_stage_only=early_stage_only,
                    )
                    
                    # Run Langfuse evaluations
                    if enrichments:
                        st.write("📊 Evaluating enrichment quality...")
                        metrics = evaluate_enrichment_batch(trace_id, enrichments, results)
                        st.session_state.enrichment_metrics = metrics
                    
                    if filtered_out_companies:
                        filter_reasons = []
                        if enable_size_filter:
                            filter_reasons.append(f">{max_employees} employees")
                        if mena_only:
                            filter_reasons.append("non-MENA HQ")
                        if early_stage_only:
                            filter_reasons.append("later than Series B")
                        st.write(f"⚠️ Filtered out {len(filtered_out_companies)} companies ({', '.join(filter_reasons)})")
                    
                    st.session_state.search_results = results
                    st.session_state.filtered_out = filtered_out_companies
                    st.session_state.search_complete = True
                    status.update(label=f"✅ Loaded {len(results)} candidates", state="complete")
                else:
                    status.update(label="❌ No candidates found — check your input", state="error")
                    st.stop()
            except Exception as e:
                status.update(label=f"❌ Failed: {e}", state="error")
                st.error(f"Error: {e}")
                st.stop()

    # ── STEP 2: Score (shared across all modes) ────────────────────────────
    # Same 4-dimension scoring pipeline regardless of how companies were found
    if st.session_state.search_complete and st.session_state.search_results:
        with st.status("🧠 Scoring companies with Gemini...", expanded=True) as status:
            st.write("Analyzing each company on 4 dimensions...")
            st.write("This may take 1-2 minutes (rate limits).")
            try:
                custom_criteria = st.session_state.get("custom_criteria", {})
                scored = score_companies(
                    st.session_state.search_results,
                    weights=weights,
                    custom_criteria=custom_criteria,
                )
                st.session_state.scored_companies = scored
                st.session_state.scoring_complete = True
                status.update(label=f"✅ Scored {len(scored)} companies", state="complete")
            except Exception as e:
                status.update(label=f"❌ Scoring failed: {e}", state="error")
                st.error(f"Scoring error: {e}")

    # ── STEP 3: Review (shared across all modes) ───────────────────────────
    # SKIP seed validation - it's slow and not needed (we know the seed from config)
    # Only validate found companies exist and match criteria
    if st.session_state.scoring_complete and st.session_state.scored_companies:
        with st.status("🔍 Reviewing results for accuracy...", expanded=True) as status:
            st.write("Checking for hallucinations...")
            try:
                review = run_full_review(
                    seed_company=benchmark_label,
                    search_results=st.session_state.search_results,
                    scored_companies=st.session_state.scored_companies,
                    criteria=selected_criteria,
                    skip_seed_validation=True,  # Skip slow seed validation
                )
                st.session_state.review_result = review
                st.session_state.review_complete = True
                status.update(
                    label=f"✅ Review complete — {review.overall_confidence:.0%} confidence",
                    state="complete"
                )
            except Exception as e:
                status.update(label=f"⚠️ Review failed: {e}", state="error")
                st.warning(f"Review error (results still available): {e}")
    
    # ── STEP 4: Save to SQLite for persistence ─────────────────────────────
    if st.session_state.scoring_complete and st.session_state.scored_companies:
        try:
            save_result = save_search(
                scout_mode=scout_mode,
                benchmark_label=benchmark_label,
                location=location if scout_mode != "inbound" else "N/A",
                criteria=selected_criteria,
                sources=custom_sources if scout_mode != "inbound" else [],
                exclusions=all_exclusions if scout_mode != "inbound" else [],
                search_results=st.session_state.search_results,
                scored_companies=st.session_state.scored_companies,
            )
            # save_search now returns {"search_id": int, "share_id": str}
            st.session_state.current_search_id = save_result["search_id"]
            st.session_state.current_share_id = save_result["share_id"]
            st.session_state.show_save_nudge = True
            st.toast(f"💾 Results saved — Share ID: `{save_result['share_id']}`")
        except Exception as e:
            logger.warning(f"Failed to save search: {e}")

    # Flush Langfuse observability events
    flush_langfuse()


# --- Display Results ---
if st.session_state.scoring_complete and st.session_state.scored_companies:
    scored_companies: List[ScoredCompany] = st.session_state.scored_companies
    
    # STRICT GROUNDING: Show grounding summary banner
    total_companies = len(scored_companies)
    grounded_companies = [c for c in scored_companies if getattr(c.search_result, 'grounding_score', 0) >= 0.5]
    ungrounded_count = total_companies - len(grounded_companies)
    
    if ungrounded_count > 0:
        st.warning(f"⚠️ **Grounding Notice:** {ungrounded_count}/{total_companies} companies have low grounding scores. Only showing verified data — ungrounded scores are nullified.")
    else:
        st.success(f"✅ **All {total_companies} companies are well-grounded** — data verified against sources.")
    
    # Show enrichment quality metrics (from Langfuse evaluations)
    if st.session_state.get("enrichment_metrics"):
        metrics = st.session_state.enrichment_metrics
        with st.expander("📊 Enrichment Quality Metrics (Langfuse)", expanded=False):
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("Valid Website", f"{metrics.get('valid_website', 0):.0%}")
            with col2:
                st.metric("Right Website", f"{metrics.get('right_website', 0):.0%}")
            with col3:
                st.metric("Employee Count", f"{metrics.get('employee_count_rate', 0):.0%}")
            with col4:
                st.metric("Stage Found", f"{metrics.get('stage_found_rate', 0):.0%}")
            with col5:
                st.metric("MENA Location", f"{metrics.get('location_mena_rate', 0):.0%}")
            st.caption("*These metrics are logged to Langfuse for tracking enrichment quality over time.*")

    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs([" Comparison Table", "📊 2x2 Matrix", "📝 Detailed Report", "📎 Appendix"])

    # --- Tab 1: Comparison Table ---
    with tab1:
        col_title, col_export = st.columns([3, 1])
        with col_title:
            st.subheader("Side-by-Side Comparison")
        with col_export:
            # Export to Excel button (placeholder for now)
            if st.button("📥 Export to Excel", key="export_excel", use_container_width=True):
                st.toast("📥 Excel export coming soon! For now, copy the table below.")
                st.info("**Coming soon:** Full Excel export with all company data, scores, and evidence.")

        markdown_table = generate_markdown_table(
            seed_company=seed_company,
            scored_companies=scored_companies,
            top_n=10,
        )
        st.markdown(markdown_table)
        
        # Quick links to company websites
        st.markdown("#### 🔗 Quick Links — Research Further")
        cols = st.columns(min(5, len(scored_companies)))
        for i, company in enumerate(scored_companies[:5]):
            with cols[i]:
                website = company.search_result.website
                if website and website != "Not Found":
                    st.link_button(
                        f"🌐 {company.search_result.name[:15]}...",
                        url=website,
                        use_container_width=True,
                    )
                else:
                    st.button(
                        f"❌ {company.search_result.name[:15]}...",
                        disabled=True,
                        use_container_width=True,
                    )

    # --- Tab 2: 2x2 Matrix ---
    with tab2:
        st.subheader("Company Positioning Matrix")

        # Axis selectors
        col1, col2 = st.columns(2)
        axis_options = get_axis_options()

        with col1:
            x_axis = st.selectbox(
                "X Axis:",
                options=[a[0] for a in axis_options],
                format_func=lambda x: AXIS_LABELS.get(x, x),
                index=2,  # Default: tech_moat
            )

        with col2:
            y_axis = st.selectbox(
                "Y Axis:",
                options=[a[0] for a in axis_options],
                format_func=lambda x: AXIS_LABELS.get(x, x),
                index=0,  # Default: offer_power
            )

        # Create and display the plot
        fig = create_matrix_plot(
            companies=scored_companies,
            x_axis=x_axis,
            y_axis=y_axis,
            title=f"{AXIS_LABELS.get(x_axis)} vs {AXIS_LABELS.get(y_axis)}",
        )
        st.plotly_chart(fig, use_container_width=True)

        # Legend
        st.caption(
            "💡 **Tip:** Hover over dots to see company details. "
            "Top-right quadrant = best on both axes. "
            "Dot color = average score across all dimensions."
        )

    # --- Shared section below tabs: Add to Target List ---
    st.markdown("---")
    st.markdown("### 🎯 Add to Target List")
    st.caption("*Save companies to track — news alerts coming soon*")
    
    for company in scored_companies:
        sr = company.search_result
        already_in_list = is_in_target_list(sr.name)
        
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            avg_score = sum(s.score for s in company.scores.values() if s.score) / max(len([s for s in company.scores.values() if s.score]), 1)
            
            # Build display string — only show location if it exists
            display_parts = [f"**{sr.name}**"]
            if sr.sector and sr.sector != "Not Found":
                display_parts.append(sr.sector)
            if sr.location and sr.location != "Not Found":
                display_parts.append(f"📍 {sr.location}")
            display_parts.append(f"Avg: {avg_score:.1f}/5")
            
            # Add source enrichment info if available
            source_data = sr.grounded_evidence.get("source_enrichment", {}) if hasattr(sr, 'grounded_evidence') else {}
            if source_data:
                emp_data = source_data.get("employee_count", {})
                if emp_data and emp_data.get("value"):
                    display_parts.append(f"👥 {emp_data['value']}")
                # Show source count for confidence
                source_count = sum(1 for k, v in source_data.items() if isinstance(v, dict) and v.get("source_count", 0) > 0)
                if source_count > 0:
                    display_parts.append(f"📚 {source_count} sources")
            
            st.markdown(" — ".join(display_parts))
        with col2:
            if already_in_list:
                st.success("✓ Saved", icon="✅")
            else:
                if st.button("➕ Add", key=f"add_target_{sr.name}", use_container_width=True):
                    add_to_target_list(company)
                    st.toast(f"🎯 Added {sr.name} to target list!")
                    st.rerun()
        with col3:
            if sr.website and sr.website != "Not Found":
                st.link_button("🌐", url=sr.website, use_container_width=True)
    
    # --- Feedback Buttons ---
    st.markdown("---")
    st.markdown("### 👍👎 Rate Results")
    st.caption("*Your feedback helps improve future searches*")
    
    for company in scored_companies:
        sr = company.search_result
        avg_score = sum(s.score for s in company.scores.values() if s.score) / max(len([s for s in company.scores.values() if s.score]), 1)
        
        # Website verification badge
        website_badge = ""
        if hasattr(sr, 'website_verified') and sr.website_verified:
            website_badge = "🔗✅"
        elif sr.website and sr.website != "Not Found":
            website_badge = "🔗⚠️"
        
        col1, col2, col3, col4 = st.columns([4, 1, 1, 1])
        with col1:
            st.markdown(f"**{sr.name}** {website_badge} — Score: {avg_score:.1f}/5")
        with col2:
            if st.button("👍", key=f"like_{sr.name}", help="Good result"):
                save_feedback(
                    feedback_type="company",
                    item_type="search_result",
                    is_positive=True,
                    item_id=sr.name,
                    item_content=sr.description,
                    search_id=st.session_state.get("current_search_id"),
                    company_name=sr.name,
                )
                st.toast(f"👍 Thanks for the feedback on {sr.name}!")
        with col3:
            if st.button("👎", key=f"dislike_{sr.name}", help="Bad result"):
                save_feedback(
                    feedback_type="company",
                    item_type="search_result",
                    is_positive=False,
                    item_id=sr.name,
                    item_content=sr.description,
                    search_id=st.session_state.get("current_search_id"),
                    company_name=sr.name,
                )
                st.toast(f"👎 Thanks — we'll improve!")
        with col4:
            # Source feedback
            if st.button("📰❌", key=f"bad_source_{sr.name}", help="Bad source"):
                save_feedback(
                    feedback_type="source",
                    item_type="source_url",
                    is_positive=False,
                    item_id=sr.source_url,
                    item_content=sr.source_snippet[:200],
                    search_id=st.session_state.get("current_search_id"),
                    company_name=sr.name,
                )
                st.toast(f"📰 Source flagged — thanks!")

    # ABSOLUTE GROUNDING: Expandable evidence section per company
    st.markdown("---")
    st.markdown("### 🔍 Grounded Evidence (Deterministic Proof)")
    st.caption("*Every claim below is validated via exact string matching — no AI interpretation.*")
    
    for company in scored_companies[:5]:
        sr = company.search_result
        grounding_score = getattr(sr, 'grounding_score', 0.0)
        grounding_icon = "✅" if grounding_score >= 0.7 else "⚠️" if grounding_score >= 0.4 else "❌"
        
        with st.expander(f"{grounding_icon} **{sr.name}** — Grounding: {grounding_score:.0%}"):
                # Grounding score banner
                score_color = "#d4edda" if grounding_score >= 0.7 else "#fff3cd" if grounding_score >= 0.4 else "#f8d7da"
                st.markdown(f"""
                <div style="padding: 0.5rem; background-color: {score_color}; border-radius: 0.3rem; margin-bottom: 0.5rem;">
                    <strong>Grounding Score: {grounding_score:.0%}</strong> — 
                    {"High confidence" if grounding_score >= 0.7 else "Medium confidence" if grounding_score >= 0.4 else "Low confidence — verify manually"}
                </div>
                """, unsafe_allow_html=True)
                
                # Source enrichment data (website + LinkedIn)
                source_data = sr.grounded_evidence.get("source_enrichment", {}) if hasattr(sr, 'grounded_evidence') else {}
                if source_data:
                    st.markdown("#### 📚 Multi-Source Enrichment")
                    
                    # Website
                    website_info = source_data.get("website_url", {})
                    if website_info and website_info.get("value"):
                        confidence = website_info.get("confidence", 0)
                        conf_icon = "✅" if confidence >= 0.7 else "⚠️" if confidence >= 0.4 else "❓"
                        st.markdown(f"- **Website:** {conf_icon} [{website_info['value'][:50]}...]({website_info['value']})")
                        # Show sources
                        for src in website_info.get("sources", [])[:2]:
                            verified = "✓" if src.get("verified") else "?"
                            st.markdown(f"  - Source [{verified}]: {src.get('quote', '')[:100]}...")
                    
                    # LinkedIn
                    linkedin_info = source_data.get("linkedin_url", {})
                    if linkedin_info and linkedin_info.get("value"):
                        st.markdown(f"- **LinkedIn:** [{linkedin_info['value'][:50]}...]({linkedin_info['value']})")
                    
                    # Employee count with sources
                    emp_info = source_data.get("employee_count", {})
                    if emp_info and emp_info.get("value"):
                        src_count = emp_info.get("source_count", 0)
                        st.markdown(f"- **Employees:** {emp_info['value']} ({src_count} source{'s' if src_count != 1 else ''})")
                    
                    # Location with sources
                    loc_info = source_data.get("location", {})
                    if loc_info and loc_info.get("value"):
                        src_count = loc_info.get("source_count", 0)
                        conf = loc_info.get("confidence", 0)
                        conf_icon = "✅" if conf >= 0.7 else "⚠️"
                        st.markdown(f"- **Location:** {conf_icon} {loc_info['value']} ({src_count} source{'s' if src_count != 1 else ''})")
                    
                    # Sector
                    sector_info = source_data.get("sector", {})
                    if sector_info and sector_info.get("value"):
                        st.markdown(f"- **Sector:** {sector_info['value']}")
                    
                    # Founders
                    founders_info = source_data.get("founders", {})
                    if founders_info and founders_info.get("value"):
                        st.markdown(f"- **Founders:** {founders_info['value']}")
                
                # Website validation
                st.markdown("#### 🌐 Website Validation")
                website_ev = sr.grounded_evidence.get("website", {}) if hasattr(sr, 'grounded_evidence') else {}
                http_verification = sr.grounded_evidence.get("website_http_verification", {}) if hasattr(sr, 'grounded_evidence') else {}
                
                st.markdown(f"- **Claimed:** `{sr.website}`")
                
                # HTTP verification (actual website fetch)
                if http_verification:
                    exists = http_verification.get("exists", False)
                    contains = http_verification.get("contains_company", False)
                    page_title = http_verification.get("page_title", "")
                    
                    if exists and contains:
                        st.markdown(f"- **HTTP Check:** ✅ Website exists and mentions company")
                        if page_title:
                            st.markdown(f"- **Page Title:** {page_title[:60]}...")
                    elif exists:
                        st.markdown(f"- **HTTP Check:** ⚠️ Website exists but doesn't mention '{sr.name}'")
                        if page_title:
                            st.markdown(f"- **Page Title:** {page_title[:60]}...")
                    else:
                        error = http_verification.get("error", "Unknown error")
                        st.markdown(f"- **HTTP Check:** ❌ Website not accessible — {error}")
                
                # Text-based grounding
                if website_ev:
                    is_valid = website_ev.get("is_grounded", False)
                    method = website_ev.get("validation_method", "unknown")
                    st.markdown(f"- **Source Grounding:** {'✅ GROUNDED' if is_valid else '❌ UNGROUNDED'} ({method})")
                    if website_ev.get("matched_text"):
                        st.code(f"Matched: {website_ev['matched_text']}", language=None)
                elif not http_verification:
                    st.markdown(f"- **Status:** No validation data")
                
                # Company name validation
                st.markdown("#### 🏢 Company Name Validation")
                name_ev = sr.grounded_evidence.get("name", {}) if hasattr(sr, 'grounded_evidence') else {}
                if name_ev:
                    is_grounded = name_ev.get("is_grounded", False)
                    match_type = name_ev.get("match_type", "none")
                    st.markdown(f"- **Status:** {'✅ GROUNDED' if is_grounded else '❌ UNGROUNDED'} ({match_type})")
                    if name_ev.get("context_before") or name_ev.get("context_after"):
                        ctx = f"...{name_ev.get('context_before', '')}[**{name_ev.get('matched_text', sr.name)}**]{name_ev.get('context_after', '')}..."
                        st.markdown(f"- **Proof snippet:** {ctx}")
                
                # Source URL
                st.markdown("#### 📄 Source")
                st.markdown(f"[{sr.source_url[:60]}...]({sr.source_url})" if sr.source_url else "No source URL")
                
                # Scoring evidence with grounding status
                st.markdown("#### 📊 Score Evidence")
                for dim_key, score in company.scores.items():
                    if score.score is not None:
                        is_grounded = getattr(score, 'is_grounded', False)
                        grounded_icon = "✅" if is_grounded else "⚠️"
                        st.markdown(f"**{SCORING_DIMENSIONS[dim_key]['label']}:** {score.score:.1f}/5 {grounded_icon}")
                        
                        # Show evidence quote with grounding status
                        if score.evidence_quote and score.evidence_quote != "N/A":
                            if is_grounded:
                                st.success(f"**Evidence (GROUNDED):** \"{score.evidence_quote[:200]}...\"")
                            else:
                                st.warning(f"**Evidence (UNGROUNDED):** \"{score.evidence_quote[:200]}...\"")
                                st.caption("⚠️ This quote was not found in the source text — may be paraphrased or hallucinated.")
                        
                        # Show grounded evidence details if available
                        if hasattr(score, 'grounded_evidence') and score.grounded_evidence:
                            ge = score.grounded_evidence
                            if ge.get("context_before") or ge.get("context_after"):
                                st.code(f"...{ge.get('context_before', '')}[MATCH]{ge.get('context_after', '')}...", language=None)
                        
                        if score.signals_detected:
                            st.markdown(f"- *Signals:* {', '.join(score.signals_detected[:5])}")
                
                st.divider()

    # --- Tab 3: Detailed Report ---
    with tab3:
        st.subheader("Investment Memo (Top 3)")

        detailed_report = generate_detailed_report(
            seed_company=seed_company,
            scored_companies=scored_companies,
            top_n=3,
        )
        st.markdown(detailed_report)

    # --- Tab 4: Appendix (Review Results) ---
    with tab4:
        st.subheader("📎 Appendix: Validation & Methodology")

        review: ReviewResult = st.session_state.review_result

        if review:
            # Overall confidence banner
            confidence_color = "green" if review.overall_confidence >= 0.7 else "orange" if review.overall_confidence >= 0.4 else "red"
            st.markdown(f"""
            <div style="padding: 1rem; background-color: {'#d4edda' if confidence_color == 'green' else '#fff3cd' if confidence_color == 'orange' else '#f8d7da'}; border-radius: 0.5rem; margin-bottom: 1rem;">
                <h3 style="margin: 0;">Overall Confidence: {review.overall_confidence:.0%}</h3>
                <p style="margin: 0.5rem 0 0 0;">{review.review_summary}</p>
            </div>
            """, unsafe_allow_html=True)

            # Hallucination flags
            if review.hallucination_flags:
                st.warning(f"⚠️ **Potential Issues Found:** {len(review.hallucination_flags)}")
                for flag in review.hallucination_flags:
                    st.markdown(f"- {flag}")
            else:
                st.success("✅ No hallucination flags detected")

            st.divider()

            # Section 1: Seed Company Validation
            st.markdown("### 1. Seed Company Profile Validation")
            st.caption(f"Validating our stored profile for **{review.seed_company}**")

            if review.seed_validations:
                for v in review.seed_validations:
                    status_icon = "✅" if v.status == "verified" else "⚠️" if v.status == "unverified" else "❌"
                    with st.expander(f"{status_icon} **{v.field.replace('_', ' ').title()}** — {v.status.upper()} ({v.confidence:.0%} confidence)"):
                        st.markdown(f"**Our Claim:** {v.original_value}")
                        st.markdown(f"**Evidence:** {v.evidence}")
                        st.markdown(f"**Source:** {v.source_url}")
            else:
                st.info("Seed validation not available")

            st.divider()

            # Section 2: Similar Companies Validation
            st.markdown("### 2. Similar Companies Validation")
            st.caption("Verifying that found companies exist and match criteria")

            if review.company_validations:
                for cv in review.company_validations:
                    exists_icon = "✅" if cv.exists else "❌"
                    similar_icon = "✅" if cv.similarity_valid else "⚠️"

                    with st.expander(f"{exists_icon} **{cv.company_name}** — Exists: {cv.exists}, Similar: {cv.similarity_valid}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("**Existence Check:**")
                            st.markdown(f"- Status: {'Verified' if cv.exists else 'Not Verified'}")
                            st.markdown(f"- Evidence: {cv.exists_evidence}")
                            st.markdown(f"- Source: {cv.exists_source}")
                        with col2:
                            st.markdown("**Similarity Check:**")
                            st.markdown(f"- Status: {'Valid' if cv.similarity_valid else 'Questionable'}")
                            st.markdown(f"- Reason: {cv.similarity_reason}")
            else:
                st.info("Company validation not available")

            st.divider()

            # Section 3: Scoring Methodology
            st.markdown("### 3. Scoring Methodology & Evidence")
            st.caption("How each score was calculated and what evidence was used")

            if review.scoring_explanations:
                for company_name, explanations in review.scoring_explanations.items():
                    with st.expander(f"📊 **{company_name}** — Scoring Breakdown"):
                        for exp in explanations:
                            grounding_icon = "🔗" if exp.grounding_check == "grounded" else "⚠️"
                            score_display = f"{exp.score}/5" if exp.score else "N/A"

                            st.markdown(f"**{exp.dimension}:** {score_display} {grounding_icon}")
                            st.markdown(f"- *Methodology:* {exp.methodology[:150]}...")
                            st.markdown(f"- *Evidence Used:* \"{exp.evidence_used[:200]}{'...' if len(exp.evidence_used) > 200 else ''}\"")
                            st.markdown(f"- *Source:* {exp.source_url}")
                            st.markdown(f"- *Grounding:* {exp.grounding_check.upper()}")
                            st.markdown("---")
            else:
                st.info("Scoring explanations not available")

            st.divider()

            # Section 4: Objective Signals Used
            st.markdown("### 4. Objective Signals Configuration")
            st.caption("Keywords and patterns used to detect signals in company data")
            
            from scoring_criteria import ALL_SCORING_DIMENSIONS, generate_appendix_markdown
            
            with st.expander("📋 View All Objective Signals (Configurable)", expanded=False):
                st.markdown(generate_appendix_markdown())
            
            # Show signals detected per company
            if scored_companies:
                st.markdown("#### Signals Detected Per Company")
                for company in scored_companies[:5]:
                    with st.expander(f"🔍 **{company.search_result.name}** — Detected Signals"):
                        for dim_key, score in company.scores.items():
                            if score.signals_detected:
                                st.markdown(f"**{SCORING_DIMENSIONS[dim_key]['label']}:** {', '.join(score.signals_detected)}")
                            if score.sub_scores:
                                st.markdown(f"  - Sub-scores: {score.sub_scores}")

        else:
            st.info("Review results will appear here after running a search.")

# ---------------------------------------------------------------------------
# Save / Schedule Search — Shows AFTER results are displayed
# ---------------------------------------------------------------------------
if st.session_state.get("show_save_nudge") and st.session_state.get("current_search_id"):
    st.divider()
    
    # Display Share ID prominently for email sharing
    share_id = st.session_state.get("current_share_id")
    if share_id:
        st.success(f"🔗 **Share ID: `{share_id}`** — Include this in email alerts so recipients can load results directly.")
    
    st.info("💡 **Want daily updates?** Schedule this search to run automatically and receive email reports.")
    
    with st.expander("📅 Schedule This Search", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            schedule_name = st.text_input(
                "Schedule name:",
                value=f"{benchmark_label} Daily Scout",
                key="schedule_name",
            )
            schedule_email = st.text_input(
                "Email for reports:",
                placeholder="analyst@jasoor.vc",
                key="schedule_email",
            )
        
        with col2:
            schedule_time = st.time_input(
                "Run at (UAE time):",
                value=None,
                key="schedule_time",
            )
            if schedule_time is None:
                schedule_time_str = "07:00"
            else:
                schedule_time_str = schedule_time.strftime("%H:%M")
            
            schedule_freq = st.selectbox(
                "Frequency:",
                options=["daily", "weekly", "monthly"],
                index=0,
                key="schedule_freq",
            )
        
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            if st.button("📅 Schedule Search", type="primary", use_container_width=True):
                if schedule_email:
                    schedule_search(
                        search_id=st.session_state.current_search_id,
                        name=schedule_name,
                        email_recipient=schedule_email,
                        schedule_time=schedule_time_str,
                        schedule_frequency=schedule_freq,
                    )
                    st.session_state.show_save_nudge = False
                    st.success(f"✅ Scheduled! You'll receive reports at {schedule_time_str} UAE time.")
                    st.rerun()
                else:
                    st.warning("Please enter an email address.")
        
        with col_b:
            if st.button("⏭️ Skip", use_container_width=True):
                st.session_state.show_save_nudge = False
                st.rerun()
        
        with col_c:
            st.caption(f"Search ID: {st.session_state.current_search_id}")

# ---------------------------------------------------------------------------
# VC Analyst Chat — Bonus Feature (Collapsed by Default)
# Only shows when user has target companies
# ---------------------------------------------------------------------------

targets = get_target_list()
if targets:
    st.divider()
    
    # Collapsed expander — VC Chat is a BONUS, not the main feature
    with st.expander("🧠 **Bonus: Ask the VC Analyst** — Get AI insights on the companies in your target list", expanded=False):
        st.caption("*Chat with a seasoned AI VC Analyst about your target companies*")
        st.markdown("🔒 *Local / Sovereign AI chat coming soon — fully protected, on-premise processing*")
        
        # Model selection: Fast (default) vs Thinking
        col_model1, col_model2, col_show = st.columns([2, 1, 1])
        with col_model2:
            use_thinking = st.toggle(
                "🧠 Thinking",
                value=False,
                help="Fast mode (default): Quick responses. Thinking mode: Slower but more thorough analysis."
            )
        with col_show:
            show_prompt = st.toggle(
                "📝 Show Prompt",
                value=False,
                help="Show the full prompt being sent to the AI"
            )
        with col_model1:
            if use_thinking:
                st.info("🧠 **Thinking Mode** — Deeper analysis")
            else:
                st.caption("⚡ **Fast Mode** — Quick responses")
        
        # Initialize chat history in session state
        if "vc_chat_history" not in st.session_state:
            st.session_state.vc_chat_history = []
        if "vc_last_prompt" not in st.session_state:
            st.session_state.vc_last_prompt = ""
        
        # Suggested prompts with descriptions
        st.markdown("**Quick analysis (grounded data only):**")
        suggested = get_suggested_prompts()
        cols = st.columns(3)
        for i, prompt_data in enumerate(suggested):
            with cols[i]:
                if st.button(
                    prompt_data["label"],
                    key=f"suggested_{i}",
                    help=f"{prompt_data['description']}\n\nPrompt: {prompt_data['prompt'][:100]}...",
                    use_container_width=True,
                ):
                    # Add user message and get response
                    user_msg = prompt_data["prompt"]
                    st.session_state.vc_chat_history.append({"role": "user", "content": user_msg})
                    
                    with st.spinner("🧠 Analyst is thinking..." if use_thinking else "⚡ Getting response..."):
                        response, full_prompt = chat_with_vc_analyst(
                            user_message=user_msg,
                            chat_history=st.session_state.vc_chat_history[:-1],
                            targets=targets,
                            use_thinking_model=use_thinking,
                            return_prompt=True,
                        )
                    st.session_state.vc_chat_history.append({"role": "assistant", "content": response})
                    st.session_state.vc_last_prompt = full_prompt
                    st.rerun()
        
        # Show prompt if toggled
        if show_prompt and st.session_state.vc_last_prompt:
            with st.expander("📝 Full Prompt Sent to AI", expanded=False):
                st.code(st.session_state.vc_last_prompt, language="markdown")
        
        # Chat history display
        if st.session_state.vc_chat_history:
            st.markdown("---")
            for msg in st.session_state.vc_chat_history:
                if msg["role"] == "user":
                    st.markdown(f"**You:** {msg['content']}")
                else:
                    st.markdown(f"**🧠 VC Analyst:**")
                    st.markdown(msg["content"])
                st.markdown("")
        
        # Chat input
        st.markdown("---")
        user_input = st.chat_input("Ask the VC Analyst about your target companies...")
        
        if user_input:
            st.session_state.vc_chat_history.append({"role": "user", "content": user_input})
            
            with st.spinner("🧠 Analyst is thinking..." if use_thinking else "⚡ Getting response..."):
                response, full_prompt = chat_with_vc_analyst(
                    user_message=user_input,
                    chat_history=st.session_state.vc_chat_history[:-1],
                    targets=targets,
                    use_thinking_model=use_thinking,
                    return_prompt=True,
                )
            st.session_state.vc_chat_history.append({"role": "assistant", "content": response})
            st.session_state.vc_last_prompt = full_prompt
            st.rerun()
        
        # Clear chat button
        if st.session_state.vc_chat_history:
            if st.button("🗑️ Clear Chat", key="clear_chat"):
                st.session_state.vc_chat_history = []
                st.session_state.vc_last_prompt = ""
                st.rerun()

else:
    # No results yet — show instructions
    st.info(
        "👈 **Get started:** Select a seed company in the sidebar and click "
        "'Search & Score' to find similar MENAT startups."
    )

    # Show what the tool does
    with st.expander("ℹ️ How Alpha Scout Works"):
        st.markdown("""
        1. **Select a Seed** — Choose a portfolio company or enter an inbound pitch
        2. **Search** — Tavily finds up to 100 similar companies from trusted MENA sources
        3. **Enrich** — 3 parallel agents find website, LinkedIn, and funding stage
        4. **Filter** — Auto-filter by employee count (<100), MENA HQ, and stage (≤Series B)
        5. **Score** — Gemini analyzes each company on 4 dimensions:
           - **Offer Power** (Hormozi's Value Equation)
           - **Sales Ability** (traction evidence)
           - **Tech Moat** (defensibility)
           - **Founder Strength** (track record)
        6. **Compare** — Side-by-side table with evidence quotes and source URLs
        7. **Visualize** — Interactive 2x2 matrix to spot outliers
        8. **VC Analyst** — AI chat with grounded analysis + VC interpretation
        9. **Export** — PDF report or add to target list

        **Grounding Guarantee:** Every score includes cited evidence. If data isn't
        available, the system returns "N/A" instead of guessing.
        """)


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.divider()
st.markdown("""
<div style="text-align: center; padding: 1rem;">
    <p style="color: #7dd3c0; font-family: Georgia, serif; font-size: 1rem; margin-bottom: 0.5rem; letter-spacing: 3px;">
        ALPHA SCOUT
    </p>
    <p style="color: #666666; font-size: 0.8rem;">
        Jasoor Ventures © 2026 | Powered by Gemini + Tavily | Observability via Langfuse
    </p>
    <p style="color: #7dd3c0; font-size: 0.75rem; font-style: italic; font-family: Georgia, serif;">
        For the courageous.
    </p>
</div>
""", unsafe_allow_html=True)
