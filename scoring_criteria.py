"""
Modular Scoring Criteria — helper functions for two-pass scoring.

This module provides helper functions for the two-pass scoring system.
The actual signal definitions are in config.py for easy adjustment.

Architecture:
1. config.py — OBJECTIVE_SIGNALS dict (keywords, weights, descriptions)
2. scoring_criteria.py — Helper functions to work with signals
3. scorer.py — Uses both for two-pass scoring

VC Analysts can modify signals in config.py over time.
All signals used are shown in the Appendix for transparency.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from config import OBJECTIVE_SIGNALS, SUB_COMPONENT_WEIGHTS, SCORING_DIMENSIONS


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class SignalDefinition:
    """
    A single objective signal that can be detected in company data.
    Built from config.py OBJECTIVE_SIGNALS dict.
    """
    name: str                           # Human-readable name
    keywords: List[str]                 # Keywords to search for (case-insensitive)
    weight: float = 1.0                 # Relative importance (0.0 - 1.0)
    description: str = ""               # What this signal indicates
    inverse: bool = False               # If True, presence is negative (e.g., "time delay")


@dataclass
class SubComponent:
    """
    A sub-component of a scoring dimension.
    Example: "Dream Outcome" is a sub-component of "Offer Power".
    """
    name: str                           # Human-readable name
    description: str                    # What this measures
    signals: List[SignalDefinition]     # Objective signals to detect
    weight: float = 1.0                 # Weight within parent dimension
    llm_prompt: str = ""                # Prompt for LLM interpretation


@dataclass
class ScoringDimension:
    """
    A full scoring dimension with sub-components.
    Example: "Offer Power" with Dream Outcome, Likelihood, Time, Effort.
    """
    key: str                            # Internal key (e.g., "offer_power")
    label: str                          # Display label
    description: str                    # What this dimension measures
    sub_components: List[SubComponent]  # Breakdown into parts
    formula: str = ""                   # How to combine sub-components


# ---------------------------------------------------------------------------
# Build Scoring Dimensions from config.py
# ---------------------------------------------------------------------------
# Instead of hardcoding signals here, we build from OBJECTIVE_SIGNALS in config.
# This makes it easy for VC Analysts to adjust signals over time.

def _build_signal_definition(signal_name: str, signal_config: dict) -> SignalDefinition:
    """Build a SignalDefinition from config dict."""
    return SignalDefinition(
        name=signal_name.replace("_", " ").title(),
        keywords=signal_config.get("keywords", []),
        weight=signal_config.get("weight", 1.0),
        description=signal_config.get("description", ""),
        inverse=signal_config.get("inverse", False),
    )


def _build_sub_component(sub_name: str, signals_config: dict, weight: float) -> SubComponent:
    """Build a SubComponent from config dict."""
    signals = [
        _build_signal_definition(sig_name, sig_config)
        for sig_name, sig_config in signals_config.items()
    ]
    return SubComponent(
        name=sub_name.replace("_", " ").title(),
        description=f"Evaluates {sub_name.replace('_', ' ')}",
        signals=signals,
        weight=weight,
        llm_prompt=f"Evaluate {sub_name.replace('_', ' ')} based on available evidence.",
    )


def _build_scoring_dimension(dim_key: str) -> ScoringDimension:
    """Build a ScoringDimension from config.py OBJECTIVE_SIGNALS."""
    dim_config = SCORING_DIMENSIONS.get(dim_key, {})
    signals_config = OBJECTIVE_SIGNALS.get(dim_key, {})
    weights_config = SUB_COMPONENT_WEIGHTS.get(dim_key, {})
    
    sub_components = [
        _build_sub_component(sub_name, sub_signals, weights_config.get(sub_name, 0.25))
        for sub_name, sub_signals in signals_config.items()
    ]
    
    return ScoringDimension(
        key=dim_key,
        label=dim_config.get("label", dim_key.replace("_", " ").title()),
        description=dim_config.get("description", ""),
        sub_components=sub_components,
        formula=f"weighted_sum({', '.join(signals_config.keys())})",
    )


# Build all dimensions from config
ALL_SCORING_DIMENSIONS: Dict[str, ScoringDimension] = {
    dim_key: _build_scoring_dimension(dim_key)
    for dim_key in OBJECTIVE_SIGNALS.keys()
}


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def get_all_signals_for_dimension(dimension_key: str) -> List[SignalDefinition]:
    """
    Get all signals for a dimension (flattened from sub-components).
    Useful for displaying in Appendix.
    """
    dimension = ALL_SCORING_DIMENSIONS.get(dimension_key)
    if not dimension:
        return []
    
    signals = []
    for sub in dimension.sub_components:
        signals.extend(sub.signals)
    return signals


def get_dimension_summary(dimension_key: str) -> Dict:
    """
    Get a summary of a dimension for display.
    Returns dict with label, description, sub-components, and signal count.
    """
    dimension = ALL_SCORING_DIMENSIONS.get(dimension_key)
    if not dimension:
        return {}
    
    return {
        "key": dimension.key,
        "label": dimension.label,
        "description": dimension.description,
        "formula": dimension.formula,
        "sub_components": [
            {
                "name": sub.name,
                "description": sub.description,
                "weight": sub.weight,
                "signal_count": len(sub.signals),
            }
            for sub in dimension.sub_components
        ],
        "total_signals": sum(len(sub.signals) for sub in dimension.sub_components),
    }


def generate_appendix_markdown() -> str:
    """
    Generate Markdown for the Appendix showing all objective signals.
    This allows VC Analysts to see exactly what signals are being used.
    
    Note: Signals are defined in config.py OBJECTIVE_SIGNALS and can be
    adjusted over time without changing this code.
    """
    md = "# Scoring Criteria — Objective Signals\n\n"
    md += "*These are the keywords and patterns used to detect objective signals in company data.*\n\n"
    md += "*To modify these signals, edit `OBJECTIVE_SIGNALS` in `config.py`.*\n\n"
    
    for dim_key, dimension in ALL_SCORING_DIMENSIONS.items():
        md += f"## {dimension.label}\n\n"
        md += f"*{dimension.description}*\n\n"
        md += f"**Formula:** `{dimension.formula}`\n\n"
        
        for sub in dimension.sub_components:
            md += f"### {sub.name} (Weight: {sub.weight:.0%})\n\n"
            md += f"{sub.description}\n\n"
            md += "| Signal | Keywords | Weight | Inverse |\n"
            md += "|--------|----------|--------|--------|\n"
            
            for signal in sub.signals:
                keywords_str = ", ".join(signal.keywords[:5])
                if len(signal.keywords) > 5:
                    keywords_str += f" (+{len(signal.keywords) - 5} more)"
                inverse_str = "Yes ❌" if signal.inverse else "No ✓"
                md += f"| {signal.name} | {keywords_str} | {signal.weight:.0%} | {inverse_str} |\n"
            
            md += "\n"
        
        md += "---\n\n"
    
    return md
