"""
VC Analyst Chat — AI-powered investment advisor for target companies.

This module provides a chat interface with a seasoned VC Analyst persona
powered by Gemini Pro. The analyst has access to:
- Target list companies and their scores
- Grounding evidence and validation data
- Investment criteria and scoring methodology

The chat is contextual — it knows about the specific companies the user
has added to their target list and can provide tailored advice.
"""

import logging
from typing import List, Dict, Optional

from llm_client import call_gemini
from persistence import get_target_list

logger = logging.getLogger(__name__)

# System prompt that defines the VC Analyst persona
VC_ANALYST_SYSTEM_PROMPT = """You are a seasoned Venture Capital Analyst and Investor with 15+ years of experience 
investing in MENA region startups. You have:

- Led investments in 50+ companies across Series A to Series C
- Seen 8 successful exits (3 IPOs, 5 acquisitions)
- Deep expertise in fintech, healthtech, logistics, and enterprise SaaS
- Strong network across GCC, Egypt, and North Africa startup ecosystems
- Pattern recognition from evaluating 1000+ pitch decks

Your communication style:
- Direct and honest — you don't sugarcoat, but you're constructive
- Data-driven — you reference specific metrics and benchmarks
- Strategic — you think about market timing, competitive dynamics, moats
- Practical — you give actionable advice, not just theory
- Experienced — you share relevant anecdotes and pattern matches

When analyzing companies, you consider:
1. **Market**: TAM/SAM/SOM, timing, regulatory environment
2. **Product**: Differentiation, defensibility, product-market fit signals
3. **Team**: Founder-market fit, execution track record, completeness
4. **Traction**: Revenue, growth rate, unit economics, retention
5. **Deal**: Valuation, terms, competitive dynamics in the round

You are helping a VC analyst evaluate companies they've added to their target list.
Be specific to the companies provided — don't give generic advice.
"""

# Suggested prompts that reflect common VC analyst questions
# Each prompt asks for BOTH grounded analysis AND VC interpretation
SUGGESTED_PROMPTS = [
    {
        "label": "🏰 Moat Analysis",
        "prompt": "Analyze the competitive moat of each target company. In the GROUNDED section, create a table with columns: Company | Moat Type | Evidence Quote | Score (1-5). In the VC INTERPRETATION section, share your pattern-matched insights on which moats are likely to hold up and why.",
        "description": "Grounded + VC intuition on moats",
    },
    {
        "label": "📊 Due Diligence Ranking",
        "prompt": "Rank these companies by investment readiness. In the GROUNDED section, show verified data: Company | Employees | Stage | Location | Scores. In the VC INTERPRETATION section, tell me which company you'd prioritize for DD and what questions you'd ask founders.",
        "description": "Data + experienced DD prioritization",
    },
    {
        "label": "💰 Investment Thesis",
        "prompt": "Which company has the strongest investment case? In the GROUNDED section, compare: Company | Bull Case (from evidence) | Bear Case (from evidence). In the VC INTERPRETATION section, give me your gut feeling — which would you back and why?",
        "description": "Evidence + VC conviction",
    },
]


def build_target_context(targets: List[Dict]) -> str:
    """
    Build a context string from target companies for the LLM.
    
    Includes all relevant data: scores, grounding, company info.
    """
    if not targets:
        return """No companies in target list yet.

IMPORTANT: The user has not added any companies to their target list.
You cannot analyze companies that don't exist. Please tell the user:
"I don't have any companies to analyze yet. Please add companies to your target list first by clicking the '➕ Add' button next to companies in your search results."

Do NOT create empty tables or make up company data."""
    
    context = f"## Target List ({len(targets)} companies)\n\n"
    
    for i, t in enumerate(targets, 1):
        context += f"### {i}. {t['name']}\n"
        context += f"- **Sector:** {t.get('sector', 'N/A')}\n"
        context += f"- **Location:** {t.get('location', 'N/A')}\n"
        context += f"- **Funding Stage:** {t.get('funding_stage', 'N/A')}\n"
        context += f"- **Website:** {t.get('website', 'N/A')}\n"
        context += f"- **Description:** {t.get('description', 'N/A')}\n"
        context += f"- **Grounding Score:** {t.get('grounding_score', 0):.0%}\n"
        
        # Add scores if available
        scores = t.get('scores', {})
        if scores:
            context += "- **Scores:**\n"
            for dim_key, dim_data in scores.items():
                score_val = dim_data.get('score', 'N/A')
                if score_val is not None:
                    context += f"  - {dim_key}: {score_val}/5\n"
                    if dim_data.get('reasoning'):
                        context += f"    - Reasoning: {dim_data['reasoning'][:200]}...\n"
        
        context += f"- **Priority:** {t.get('priority', 'medium')}\n"
        context += f"- **Notes:** {t.get('notes', 'None')}\n"
        context += "\n"
    
    return context


def chat_with_vc_analyst(
    user_message: str,
    chat_history: List[Dict] = None,
    targets: List[Dict] = None,
    use_thinking_model: bool = False,
    return_prompt: bool = False,
) -> str:
    """
    Send a message to the VC Analyst and get a response.
    
    Args:
        user_message: The user's question or prompt
        chat_history: Previous messages in the conversation
        targets: Target companies (if None, fetches from database)
        use_thinking_model: If True, use slower but more thorough model
        return_prompt: If True, return (response, full_prompt) tuple
    
    Returns:
        The analyst's response as a string, or (response, prompt) if return_prompt=True
    """
    if targets is None:
        targets = get_target_list()
    
    if chat_history is None:
        chat_history = []
    
    # Build the full prompt with context
    target_context = build_target_context(targets)
    
    # Build conversation history
    history_text = ""
    if chat_history:
        history_text = "\n## Previous Conversation\n"
        for msg in chat_history[-6:]:  # Last 6 messages for context
            role = "User" if msg["role"] == "user" else "VC Analyst"
            history_text += f"**{role}:** {msg['content']}\n\n"
    
    prompt = f"""{VC_ANALYST_SYSTEM_PROMPT}

{target_context}

{history_text}

## Current Question
**User:** {user_message}

## Response Guidelines

Your response MUST have TWO clearly separated sections:

### 📊 SECTION 1: GROUNDED ANALYSIS
Based ONLY on the verified data and evidence provided above.
- Only cite facts that appear in the grounded evidence
- Use exact quotes when available
- If data is missing, say "No grounded data available"
- Be conservative — don't extrapolate beyond the evidence

### 💡 SECTION 2: VC INTERPRETATION (Ungrounded)
Your expert opinion as a seasoned VC with 15+ years experience.
- Pattern matching from your experience with similar companies
- Market intuition and timing insights
- Red flags or opportunities you'd investigate further
- What you'd ask in a founder meeting
- Gut feeling on the opportunity

**IMPORTANT: Always clearly label which section is which.**
Use these exact headers:
- "## 📊 Grounded Analysis" 
- "## 💡 VC Interpretation"

## ⚠️ MANDATORY: USE TABLES FOR EVERYTHING

**YOU MUST USE MARKDOWN TABLES IN BOTH SECTIONS. THIS IS NOT OPTIONAL.**

Tables are required for:
- Comparing companies (ALWAYS)
- Listing strengths/weaknesses
- Showing scores or rankings
- Summarizing findings
- Due diligence items
- Risk assessment
- Any list of 2+ items

**EVERY response should have at least one table per section.**

Example table formats to use:

**For Grounded Analysis:**
| Company | Employees | Stage | Location | Evidence Quote |
|---------|-----------|-------|----------|----------------|
| Company A | 45 | Series A | Dubai | "raised $5M in 2024" |

**For VC Interpretation:**
| Company | My Take | Risk Level | Action |
|---------|---------|------------|--------|
| Company A | Strong PMF signals | Medium | Priority DD |

**For Rankings:**
| Rank | Company | Score | Key Reason |
|------|---------|-------|------------|
| 1 | Company A | 4.2/5 | Best moat |

**For Due Diligence:**
| Company | Question to Ask | Why It Matters |
|---------|-----------------|----------------|
| Company A | Unit economics? | Validate margins |

Tables make your analysis scannable, actionable, and professional.
Do NOT write long paragraphs when a table would be clearer.
"""

    try:
        # Fast model (default): Quick responses for simple questions
        # Thinking model: Slower but more thorough analysis
        response = call_gemini(
            prompt=prompt,
            trace=None,
            span_name="vc_analyst_chat",
            metadata={"targets_count": len(targets), "model_type": "thinking" if use_thinking_model else "fast"},
            use_pro_model=use_thinking_model,  # Pro model for thinking, Flash for fast
        )
        if return_prompt:
            return response, prompt
        return response
    except Exception as e:
        logger.error(f"VC Analyst chat failed: {e}")
        error_msg = f"I apologize, but I encountered an error: {str(e)}. Please try again."
        if return_prompt:
            return error_msg, prompt
        return error_msg


def get_suggested_prompts() -> List[Dict]:
    """
    Return the list of suggested prompts for the UI.
    """
    return SUGGESTED_PROMPTS
