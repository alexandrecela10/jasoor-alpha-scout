"""
Plotly 2x2 Matrix Visualization — interactive scatter plot for comparing companies.

Users can toggle X and Y axes between:
- offer_power, sales_ability, tech_moat, founder_strength
- expected_cac, expected_ltv

Hovering over a dot shows the company's AI summary.
Companies with N/A scores on the selected axes are excluded from the plot.
"""

import logging
from typing import List, Tuple

import plotly.graph_objects as go

from models import ScoredCompany
from config import SCORING_DIMENSIONS, MATRIX_AXES

logger = logging.getLogger(__name__)

# Human-readable labels for each axis
AXIS_LABELS = {
    "offer_power": "Offer Power",
    "sales_ability": "Sales Ability",
    "tech_moat": "Tech Moat",
    "founder_strength": "Founder Strength",
    "expected_cac": "Expected CAC",
    "expected_ltv": "Expected LTV",
}


def create_matrix_plot(
    companies: List[ScoredCompany],
    x_axis: str = "tech_moat",
    y_axis: str = "offer_power",
    title: str = "Company Comparison Matrix",
) -> go.Figure:
    """
    Create an interactive 2x2 scatter plot.

    Args:
        companies: List of ScoredCompany objects to plot
        x_axis:    Dimension for X axis (e.g., "tech_moat")
        y_axis:    Dimension for Y axis (e.g., "offer_power")
        title:     Chart title

    Returns:
        Plotly Figure object (render with st.plotly_chart in Streamlit)
    """
    # Filter companies that have valid scores for both axes
    # Why filter? A company with N/A on an axis can't be plotted there.
    valid_companies = []
    x_values = []
    y_values = []

    for company in companies:
        x_val = company.get_score_value(x_axis)
        y_val = company.get_score_value(y_axis)

        # Both must be valid numbers (not None)
        if x_val is not None and y_val is not None:
            valid_companies.append(company)
            x_values.append(x_val)
            y_values.append(y_val)

    if not valid_companies:
        # Return empty figure with message
        fig = go.Figure()
        fig.add_annotation(
            text="No companies have valid scores for both selected axes",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="gray"),
        )
        fig.update_layout(title=title)
        return fig

    # Build hover text — shows company name + key info in readable format
    hover_texts = []
    for company in valid_companies:
        # Truncate summary for hover (full summary in sidebar)
        summary = company.ai_summary[:150] + "..." if len(company.ai_summary) > 150 else company.ai_summary
        
        # Get score values for display
        x_score = company.get_score_value(x_axis)
        y_score = company.get_score_value(y_axis)
        
        hover_texts.append(
            f"<b style='font-size:14px'>{company.search_result.name}</b><br>"
            f"<span style='color:#7dd3c0'>{company.search_result.sector}</span><br>"
            f"━━━━━━━━━━━━━━━━━━━━<br>"
            f"<b>{AXIS_LABELS.get(x_axis, x_axis)}:</b> {x_score:.1f}<br>"
            f"<b>{AXIS_LABELS.get(y_axis, y_axis)}:</b> {y_score:.1f}<br>"
            f"━━━━━━━━━━━━━━━━━━━━<br>"
            f"<span style='font-size:11px'>{summary}</span>"
        )

    # Create the scatter plot
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=x_values,
        y=y_values,
        mode="markers+text",
        marker=dict(
            size=20,
            color=_calculate_colors(valid_companies),  # Color by average score
            colorscale="Viridis",
            showscale=True,
            colorbar=dict(title="Avg Score"),
        ),
        text=[c.search_result.name for c in valid_companies],
        textposition="top center",
        textfont=dict(size=10),
        hovertext=hover_texts,
        hoverinfo="text",
        hoverlabel=dict(
            bgcolor="#1a1a2e",
            bordercolor="#7dd3c0",
            font=dict(
                size=12,
                family="Arial",
                color="#ffffff",
            ),
        ),
    ))

    # Add quadrant lines at the midpoint (2.5 on a 1-5 scale)
    # This creates the classic "2x2 matrix" look
    fig.add_hline(y=2.5, line_dash="dash", line_color="lightgray")
    fig.add_vline(x=2.5, line_dash="dash", line_color="lightgray")

    # Add quadrant labels
    _add_quadrant_labels(fig, x_axis, y_axis)

    # Layout - Jasoor dark theme
    fig.update_layout(
        title=dict(text=title, font=dict(size=18, color="#ffffff")),
        xaxis=dict(
            title=dict(text=AXIS_LABELS.get(x_axis, x_axis), font=dict(color="#7dd3c0")),
            range=[0.5, 5.5],  # Pad the 1-5 scale
            tickvals=[1, 2, 3, 4, 5],
            tickfont=dict(color="#888888"),
            gridcolor="#2a2a4a",
        ),
        yaxis=dict(
            title=dict(text=AXIS_LABELS.get(y_axis, y_axis), font=dict(color="#7dd3c0")),
            range=[0.5, 5.5],
            tickvals=[1, 2, 3, 4, 5],
            tickfont=dict(color="#888888"),
            gridcolor="#2a2a4a",
        ),
        plot_bgcolor="#0f0f23",
        paper_bgcolor="#0f0f23",
        hoverlabel=dict(align="left"),
        height=600,
        font=dict(color="#ffffff"),
    )

    return fig


def _calculate_colors(companies: List[ScoredCompany]) -> List[float]:
    """
    Calculate color values based on average score across all dimensions.

    Higher average = brighter color (more promising company).
    This gives a quick visual indicator of overall quality.
    """
    colors = []
    for company in companies:
        valid_scores = [
            v.score for v in company.scores.values()
            if v.score is not None
        ]
        avg = sum(valid_scores) / len(valid_scores) if valid_scores else 2.5
        colors.append(avg)
    return colors


def _add_quadrant_labels(fig: go.Figure, x_axis: str, y_axis: str):
    """
    Add labels to each quadrant explaining what it means.

    Top-right = best (high on both axes)
    Bottom-left = worst (low on both axes)
    """
    x_label = AXIS_LABELS.get(x_axis, x_axis)
    y_label = AXIS_LABELS.get(y_axis, y_axis)

    # Top-right: High X, High Y (best quadrant)
    fig.add_annotation(
        x=4.5, y=4.5,
        text=f"High {x_label}<br>High {y_label}",
        showarrow=False,
        font=dict(size=10, color="green"),
        opacity=0.7,
    )

    # Bottom-left: Low X, Low Y (worst quadrant)
    fig.add_annotation(
        x=1.5, y=1.5,
        text=f"Low {x_label}<br>Low {y_label}",
        showarrow=False,
        font=dict(size=10, color="red"),
        opacity=0.7,
    )

    # Top-left: Low X, High Y
    fig.add_annotation(
        x=1.5, y=4.5,
        text=f"Low {x_label}<br>High {y_label}",
        showarrow=False,
        font=dict(size=10, color="gray"),
        opacity=0.7,
    )

    # Bottom-right: High X, Low Y
    fig.add_annotation(
        x=4.5, y=1.5,
        text=f"High {x_label}<br>Low {y_label}",
        showarrow=False,
        font=dict(size=10, color="gray"),
        opacity=0.7,
    )


def get_axis_options() -> List[Tuple[str, str]]:
    """
    Return list of (value, label) tuples for axis dropdown menus.

    Used by Streamlit to populate the X/Y axis selectors.
    """
    return [(axis, AXIS_LABELS.get(axis, axis)) for axis in MATRIX_AXES]
