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

from config import PORTFOLIO_COMPANIES, SCORING_DIMENSIONS, DEFAULT_SOURCES, BENCHMARK_MENA_STARTUPS, SCOUT_MODES
from ingest import get_simulated_inbound, extract_company_from_website, extract_company_from_text
from models import ScoredCompany
from search import search_similar_companies
from scorer import score_companies
from visualizer import create_matrix_plot, get_axis_options, AXIS_LABELS
from reporting import (
    generate_markdown_table,
    generate_detailed_report,
    generate_pdf_report,
    send_email_report,
)
from reviewer import run_full_review, ReviewResult
from tracing import flush_langfuse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    
    /* Sidebar styling - slightly lighter navy */
    [data-testid="stSidebar"] {
        background: #12122a !important;
        border-right: 1px solid #2a2a4a;
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


# ---------------------------------------------------------------------------
# Sidebar — Configuration
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown('<p class="jasoor-title">ALPHA SCOUT</p>', unsafe_allow_html=True)
    st.markdown('<p class="jasoor-subtitle">For the courageous investor</p>', unsafe_allow_html=True)

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
        seed_company = list(PORTFOLIO_COMPANIES.keys())[0]  # default to avoid NameError

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
        
        # Multi-select for benchmark companies
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
        
        # Override company_size to guide the search toward earlier-stage companies
        stage_hint = {
            "Before Series A": "pre-seed or seed stage, early traction only",
            "Before Series B": "pre-seed, seed, or Series A — early growth stage",
            "Before Series C": "seed to Series B — proven model, pre-scale",
        }
        custom_attrs = dict(bm_data)
        custom_attrs["company_size"] = stage_hint[target_stage]

    # ── MODE 3: Inbound Candidates ─────────────────────────────────────────
    elif scout_mode == "inbound":
        benchmark_label = "Inbound Candidates"
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
            min_value=3, max_value=10, value=5,
        )

        with st.expander("🔍 Leverage Your Trusted Sources"):
            st.caption("*Add or remove sources based on your network and research channels*")
            sources_text = st.text_area(
                "Sources (one per line):",
                value="\n".join(DEFAULT_SOURCES),
                height=150,
            )
            custom_sources = [s.strip() for s in sources_text.split("\n") if s.strip()]

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
            st.write(f"Sources: {', '.join(custom_sources[:3])}...")
            try:
                results = search_similar_companies(
                    seed_company=benchmark_label,
                    criteria=selected_criteria,
                    location=location,
                    sources=custom_sources,
                    exclusions=all_exclusions,
                    custom_attrs=custom_attrs,
                    max_results=max_results,
                )
                st.session_state.search_results = results
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
                    st.session_state.search_results = results
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
    if st.session_state.scoring_complete and st.session_state.scored_companies:
        with st.status("🔍 Reviewing results for accuracy...", expanded=True) as status:
            st.write("Validating companies exist and match criteria...")
            st.write("Checking for hallucinations...")
            try:
                review = run_full_review(
                    seed_company=benchmark_label,
                    search_results=st.session_state.search_results,
                    scored_companies=st.session_state.scored_companies,
                    criteria=selected_criteria,
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

    # Flush Langfuse observability events
    flush_langfuse()


# --- Display Results ---
if st.session_state.scoring_complete and st.session_state.scored_companies:
    scored_companies: List[ScoredCompany] = st.session_state.scored_companies

    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["📊 2x2 Matrix", "📋 Comparison Table", "📝 Detailed Report", "📎 Appendix"])

    # --- Tab 1: 2x2 Matrix ---
    with tab1:
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

    # --- Tab 2: Comparison Table ---
    with tab2:
        st.subheader("Side-by-Side Comparison")

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

        # ABSOLUTE GROUNDING: Expandable evidence section per company
        st.markdown("---")
        st.markdown("### � Grounded Evidence (Deterministic Proof)")
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
                
                # Website validation
                st.markdown("#### 🌐 Website Validation")
                website_ev = sr.grounded_evidence.get("website", {}) if hasattr(sr, 'grounded_evidence') else {}
                if website_ev:
                    is_valid = website_ev.get("is_grounded", False)
                    method = website_ev.get("validation_method", "unknown")
                    st.markdown(f"- **Claimed:** `{sr.website}`")
                    st.markdown(f"- **Status:** {'✅ GROUNDED' if is_valid else '❌ UNGROUNDED'}")
                    st.markdown(f"- **Method:** {method}")
                    if website_ev.get("matched_text"):
                        st.code(f"Matched: {website_ev['matched_text']}", language=None)
                else:
                    st.markdown(f"- **Website:** `{sr.website}` (no validation data)")
                
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

else:
    # No results yet — show instructions
    st.info(
        "👈 **Get started:** Select a seed company in the sidebar and click "
        "'Search & Score' to find similar MENAT startups."
    )

    # Show what the tool does
    with st.expander("ℹ️ How Alpha Scout Works"):
        st.markdown("""
        1. **Select a Seed** — Choose a Jasoor portfolio company (e.g., Byanat AI)
        2. **Search** — Tavily finds 10 similar companies from trusted MENAT sources
        3. **Score** — Gemini analyzes each company on 4 dimensions:
           - **Offer Power** (Hormozi's Value Equation)
           - **Sales Ability** (traction evidence)
           - **Tech Moat** (defensibility)
           - **Founder Strength** (track record)
        4. **Visualize** — Interactive 2x2 matrix to compare companies
        5. **Export** — PDF report or email to your team

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
