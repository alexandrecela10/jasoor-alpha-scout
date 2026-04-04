"""
Reporting & Outreach — generates comparison tables, PDFs, Excel, and sends email reports.

Outputs:
1. Markdown table comparing seed company vs. target companies
2. PDF report with company details, scores, and founder contacts
3. Excel export of comparison table
4. Email sending via SMTP (Gmail-compatible)

All data in reports is grounded — if a field was "Not Found", it shows as such.
"""

import os
import io
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from typing import List, Optional
from datetime import datetime

from fpdf import FPDF
import pandas as pd

from models import ScoredCompany
from config import PORTFOLIO_COMPANIES, SCORING_DIMENSIONS

logger = logging.getLogger(__name__)


def generate_markdown_table(
    seed_company: str,
    scored_companies: List[ScoredCompany],
    top_n: int = 10,
) -> str:
    """
    Generate a Markdown comparison table: seed company vs. targets.

    Columns: Company | Location | Sector | Offer Power | Tech Moat | Sales | Founder | Website
    """
    # Header
    md = f"## Comparison: {seed_company} vs. Similar Companies\n\n"
    md += "| Company | Location | Sector | Offer | Tech | Sales | Founder | Website |\n"
    md += "|---------|----------|--------|-------|------|-------|---------|--------|\n"

    # Seed company row (from config)
    seed_data = PORTFOLIO_COMPANIES.get(seed_company, {})
    md += f"| **{seed_company}** (Seed) | {seed_data.get('location', 'N/A')} | "
    md += f"{seed_data.get('sector', 'N/A')} | — | — | — | — | "
    md += f"[Link]({seed_data.get('website', '#')}) |\n"

    # Target company rows
    for company in scored_companies[:top_n]:
        sr = company.search_result
        scores = company.scores

        # Get score values, display "—" if None
        offer = scores.get("offer_power")
        tech = scores.get("tech_moat")
        sales = scores.get("sales_ability")
        founder = scores.get("founder_strength")

        offer_str = f"{offer.score}/5" if offer and offer.score else "—"
        tech_str = f"{tech.score}/5" if tech and tech.score else "—"
        sales_str = f"{sales.score}/5" if sales and sales.score else "—"
        founder_str = f"{founder.score}/5" if founder and founder.score else "—"

        # Website link (handle "Not Found")
        website = sr.website if sr.website != "Not Found" else "#"
        website_link = f"[Link]({website})" if website != "#" else "N/A"

        md += f"| {sr.name} | {sr.location} | {sr.sector} | "
        md += f"{offer_str} | {tech_str} | {sales_str} | {founder_str} | {website_link} |\n"

    return md


def generate_excel_export(
    seed_company: str,
    scored_companies: List[ScoredCompany],
) -> bytes:
    """
    Generate an Excel file with comparison data.
    
    Returns bytes that can be used with st.download_button.
    
    Sheets:
    1. Summary — overview table with all companies and scores
    2. Details — full company details including evidence
    """
    # Build summary data
    summary_data = []
    
    # Add seed company row
    seed_data = PORTFOLIO_COMPANIES.get(seed_company, {})
    summary_data.append({
        "Company": f"{seed_company} (Seed)",
        "Location": seed_data.get("location", "N/A"),
        "Sector": seed_data.get("sector", "N/A"),
        "Description": seed_data.get("problem_statement", "N/A"),
        "Tech Edge": seed_data.get("tech_edge", "N/A"),
        "Offer Power": "—",
        "Tech Moat": "—",
        "Sales Ability": "—",
        "Founder Strength": "—",
        "Expected CAC": "—",
        "Expected LTV": "—",
        "Website": seed_data.get("website", "N/A"),
    })
    
    # Add scored companies
    for company in scored_companies:
        sr = company.search_result
        scores = company.scores
        
        # Get score values
        offer = scores.get("offer_power")
        tech = scores.get("tech_moat")
        sales = scores.get("sales_ability")
        founder = scores.get("founder_strength")
        
        summary_data.append({
            "Company": sr.name,
            "Location": sr.location,
            "Sector": sr.sector,
            "Description": sr.description,
            "Tech Edge": "N/A",  # Not extracted for found companies
            "Offer Power": f"{offer.score:.1f}" if offer and offer.score else "N/A",
            "Tech Moat": f"{tech.score:.1f}" if tech and tech.score else "N/A",
            "Sales Ability": f"{sales.score:.1f}" if sales and sales.score else "N/A",
            "Founder Strength": f"{founder.score:.1f}" if founder and founder.score else "N/A",
            "Expected CAC": f"{company.expected_cac:.1f}" if company.expected_cac else "N/A",
            "Expected LTV": f"{company.expected_ltv:.1f}" if company.expected_ltv else "N/A",
            "Website": sr.website if sr.website != "Not Found" else "N/A",
        })
    
    # Build details data (with evidence)
    details_data = []
    for company in scored_companies:
        sr = company.search_result
        scores = company.scores
        
        for dim_key, dim_score in scores.items():
            details_data.append({
                "Company": sr.name,
                "Dimension": SCORING_DIMENSIONS.get(dim_key, {}).get("label", dim_key),
                "Score": f"{dim_score.score:.1f}" if dim_score.score else "N/A",
                "Evidence": dim_score.evidence_quote if dim_score.evidence_quote else "N/A",
                "Source URL": dim_score.source_url if dim_score.source_url else "N/A",
                "Reasoning": dim_score.reasoning if dim_score.reasoning else "N/A",
            })
    
    # Create DataFrames
    summary_df = pd.DataFrame(summary_data)
    details_df = pd.DataFrame(details_data)
    
    # Write to Excel in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        details_df.to_excel(writer, sheet_name="Score Details", index=False)
    
    output.seek(0)
    return output.getvalue()


def generate_detailed_report(
    seed_company: str,
    scored_companies: List[ScoredCompany],
    top_n: int = 3,
) -> str:
    """
    Generate a detailed Markdown report for the top N companies.

    Includes: company overview, all scores with evidence, founder info, fit summary.
    """
    md = f"# Alpha Scout Report: Companies Similar to {seed_company}\n\n"
    md += f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n"
    md += "---\n\n"

    for i, company in enumerate(scored_companies[:top_n], 1):
        sr = company.search_result

        md += f"## {i}. {sr.name}\n\n"

        # Overview
        md += f"**Description:** {sr.description}\n\n"
        md += f"**Location:** {sr.location} | **Sector:** {sr.sector}\n\n"
        md += f"**Website:** {sr.website}\n\n"
        md += f"**Funding:** {sr.funding_stage} — {sr.funding_amount}\n\n"

        # Founders
        md += "### Founders\n\n"
        if sr.founders:
            for j, founder in enumerate(sr.founders):
                linkedin = sr.founders_linkedin[j] if j < len(sr.founders_linkedin) else "Not Found"
                md += f"- **{founder}** — [LinkedIn]({linkedin})\n"
        else:
            md += "- *Founder information not found in sources*\n"
        md += "\n"

        # Scores with evidence
        md += "### Scores\n\n"
        for dim_key, dim_config in SCORING_DIMENSIONS.items():
            score_obj = company.scores.get(dim_key)
            if score_obj:
                score_val = f"{score_obj.score}/5" if score_obj.score else "N/A"
                md += f"**{dim_config['label']}:** {score_val}\n\n"
                md += f"- *Evidence:* \"{score_obj.evidence_quote}\"\n"
                md += f"- *Source:* {score_obj.source_url}\n"
                md += f"- *Reasoning:* {score_obj.reasoning}\n\n"

        # Fit summary
        md += "### Why This Is A Fit\n\n"
        md += f"{company.ai_summary}\n\n"

        md += "---\n\n"

    # Source attribution
    md += "## Sources\n\n"
    md += "*All data is grounded in the following sources. Fields marked 'Not Found' "
    md += "indicate the information was not available in the source material.*\n\n"

    for company in scored_companies[:top_n]:
        if company.search_result.source_url:
            md += f"- {company.search_result.name}: {company.search_result.source_url}\n"

    return md


def generate_pdf_report(
    seed_company: str,
    scored_companies: List[ScoredCompany],
    output_path: str = "alpha_scout_report.pdf",
    top_n: int = 3,
) -> str:
    """
    Generate a PDF report for the top N companies.

    Uses fpdf2 for lightweight PDF generation (no system dependencies).
    Returns the path to the generated PDF.
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Title page
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 24)
    pdf.cell(0, 20, "Alpha Scout Report", ln=True, align="C")
    pdf.set_font("Helvetica", "", 14)
    pdf.cell(0, 10, f"Companies Similar to {seed_company}", ln=True, align="C")
    pdf.cell(0, 10, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True, align="C")
    pdf.ln(20)

    # Company pages
    for i, company in enumerate(scored_companies[:top_n], 1):
        sr = company.search_result

        pdf.add_page()
        pdf.set_font("Helvetica", "B", 18)
        pdf.cell(0, 10, f"{i}. {sr.name}", ln=True)
        pdf.ln(5)

        # Overview
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, f"Description: {sr.description[:300]}")
        pdf.ln(3)
        pdf.cell(0, 6, f"Location: {sr.location} | Sector: {sr.sector}", ln=True)
        pdf.cell(0, 6, f"Website: {sr.website}", ln=True)
        pdf.cell(0, 6, f"Funding: {sr.funding_stage} - {sr.funding_amount}", ln=True)
        pdf.ln(5)

        # Founders
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Founders:", ln=True)
        pdf.set_font("Helvetica", "", 11)
        if sr.founders:
            for j, founder in enumerate(sr.founders):
                linkedin = sr.founders_linkedin[j] if j < len(sr.founders_linkedin) else "Not Found"
                pdf.cell(0, 6, f"  - {founder} ({linkedin})", ln=True)
        else:
            pdf.cell(0, 6, "  - Founder information not found", ln=True)
        pdf.ln(5)

        # Scores
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Scores:", ln=True)
        pdf.set_font("Helvetica", "", 11)
        for dim_key, dim_config in SCORING_DIMENSIONS.items():
            score_obj = company.scores.get(dim_key)
            if score_obj:
                score_val = f"{score_obj.score}/5" if score_obj.score else "N/A"
                pdf.cell(0, 6, f"  {dim_config['label']}: {score_val}", ln=True)
        pdf.ln(5)

        # Fit summary
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Why This Is A Fit:", ln=True)
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, company.ai_summary[:500])

    # Save
    pdf.output(output_path)
    logger.info(f"PDF report saved to: {output_path}")
    return output_path


def send_email_report(
    to_email: str,
    seed_company: str,
    scored_companies: List[ScoredCompany],
    top_n: int = 3,
    attach_pdf: bool = True,
    share_id: str = None,
) -> tuple[bool, str]:
    """
    Send the report via email (SMTP).

    Requires env vars: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
    
    For Gmail: You need an App Password, not your regular password.
    Go to https://myaccount.google.com/apppasswords to generate one.
    
    Args:
        share_id: Optional share ID to include in email for direct access to results
    
    Returns tuple of (success: bool, message: str)
    """
    # Get SMTP settings from environment
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD")

    if not smtp_user or not smtp_password:
        msg = "SMTP credentials not set. Add SMTP_USER and SMTP_PASSWORD to .env"
        logger.error(msg)
        return False, msg

    try:
        # Create email
        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = to_email
        msg["Subject"] = f"Alpha Scout Report: Companies Similar to {seed_company}"

        # Body (plain text version)
        body = f"""Alpha Scout Report
==================

Companies similar to {seed_company}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
        # Include Share ID for direct access
        if share_id:
            body += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔗 QUICK ACCESS: Share ID {share_id}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
To view full results in Alpha Scout:
1. Open Alpha Scout
2. Go to "Saved Searches" in the sidebar
3. Enter Share ID: {share_id}
4. Click "Load"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        body += f"""
Top {top_n} Targets:
"""
        for i, company in enumerate(scored_companies[:top_n], 1):
            sr = company.search_result
            body += f"\n{i}. {sr.name}\n"
            body += f"   Location: {sr.location}\n"
            body += f"   Website: {sr.website}\n"
            body += f"   Summary: {company.ai_summary[:200]}...\n"

        body += "\n\nSee attached PDF for full details."

        msg.attach(MIMEText(body, "plain"))

        # Attach PDF if requested
        if attach_pdf:
            pdf_path = generate_pdf_report(seed_company, scored_companies, top_n=top_n)
            with open(pdf_path, "rb") as f:
                pdf_attachment = MIMEApplication(f.read(), _subtype="pdf")
                pdf_attachment.add_header(
                    "Content-Disposition", "attachment",
                    filename="alpha_scout_report.pdf"
                )
                msg.attach(pdf_attachment)
            # Clean up temp PDF
            os.remove(pdf_path)

        # Send with timeout
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)

        logger.info(f"Email sent to {to_email}")
        return True, "Email sent successfully!"

    except smtplib.SMTPAuthenticationError as e:
        # Most common issue: wrong password or need App Password for Gmail
        msg = "Authentication failed. For Gmail, use an App Password (not your regular password). Generate one at https://myaccount.google.com/apppasswords"
        logger.error(f"SMTP Auth Error: {e}")
        return False, msg
    
    except smtplib.SMTPConnectError as e:
        msg = f"Could not connect to {smtp_host}:{smtp_port}. Check your network and SMTP settings."
        logger.error(f"SMTP Connect Error: {e}")
        return False, msg
    
    except smtplib.SMTPException as e:
        msg = f"SMTP error: {str(e)}"
        logger.error(f"SMTP Error: {e}")
        return False, msg
    
    except Exception as e:
        msg = f"Failed to send email: {str(e)}"
        logger.error(msg)
        return False, msg
