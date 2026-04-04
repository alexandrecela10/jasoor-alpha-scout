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
SUGGESTED_PROMPTS = [
    {
        "label": "🔍 Due Diligence Priorities",
        "prompt": "Based on these target companies, what are the top 3 due diligence questions I should prioritize for each? What red flags should I watch for?",
        "description": "Get prioritized DD checklist",
    },
    {
        "label": "📊 Competitive Analysis",
        "prompt": "How do these companies compare to each other and to known players in their markets? Which has the strongest competitive moat and why?",
        "description": "Compare targets & market position",
    },
    {
        "label": "💰 Investment Thesis",
        "prompt": "If you had to pick ONE company from my target list to invest in today, which would it be and why? What's the bull case and bear case?",
        "description": "Get investment recommendation",
    },
]


def build_target_context(targets: List[Dict]) -> str:
    """
    Build a context string from target companies for the LLM.
    
    Includes all relevant data: scores, grounding, company info.
    """
    if not targets:
        return "No companies in target list yet."
    
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
) -> str:
    """
    Send a message to the VC Analyst and get a response.
    
    Args:
        user_message: The user's question or prompt
        chat_history: Previous messages in the conversation
        targets: Target companies (if None, fetches from database)
    
    Returns:
        The analyst's response as a string
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

Provide a thoughtful, specific response based on the target companies above. 
Be direct and actionable. Reference specific companies by name when relevant.
"""

    try:
        response = call_gemini(
            prompt=prompt,
            trace=None,
            span_name="vc_analyst_chat",
            metadata={"targets_count": len(targets)},
            use_pro_model=True,  # Use strongest model for quality advice
        )
        return response
    except Exception as e:
        logger.error(f"VC Analyst chat failed: {e}")
        return f"I apologize, but I encountered an error: {str(e)}. Please try again."


def get_suggested_prompts() -> List[Dict]:
    """
    Return the list of suggested prompts for the UI.
    """
    return SUGGESTED_PROMPTS
