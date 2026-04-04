"""
SQLite Persistence — stores search results and scored companies for later retrieval.

This module provides persistent storage so users can:
1. Close the browser and come back later to see their results
2. View historical searches and compare across sessions
3. Export past results without re-running searches

Tables:
- searches: Metadata about each search (timestamp, mode, seed company, etc.)
- search_results: Raw company data from Tavily
- scored_companies: Companies with scores attached

Why SQLite? 
- Zero setup (no server needed)
- File-based (easy to backup, move, delete)
- Fast enough for single-user Streamlit apps
"""

import os
import json
import sqlite3
import logging
import uuid
import hashlib
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import asdict

from models import SearchResult, ScoredCompany, DimensionScore

logger = logging.getLogger(__name__)

# Database file location (same directory as app)
DB_PATH = os.path.join(os.path.dirname(__file__), "alpha_scout.db")


def generate_share_id() -> str:
    """
    Generate a short, unique share ID for a search.
    
    Format: 8-character alphanumeric code (e.g., "AS-7F3K9X2M")
    - Easy to copy/paste from email
    - Human-readable (no confusing characters like 0/O, 1/l)
    """
    # Generate UUID and take first 8 chars of hex (uppercase)
    raw_id = uuid.uuid4().hex[:8].upper()
    return f"AS-{raw_id}"


def get_connection() -> sqlite3.Connection:
    """
    Get a connection to the SQLite database.
    Creates the database file if it doesn't exist.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Return rows as dicts
    return conn


def init_db():
    """
    Initialize the database schema.
    Called once at app startup — safe to call multiple times (uses IF NOT EXISTS).
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Table 1: Search sessions (one row per "Search & Score" click)
    # share_id is a short unique code for sharing via email links
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            share_id TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            scout_mode TEXT NOT NULL,
            benchmark_label TEXT NOT NULL,
            location TEXT,
            criteria TEXT,
            sources TEXT,
            exclusions TEXT,
            num_results INTEGER,
            grounding_score_avg REAL
        )
    """)
    
    # Table for Target List — companies the VC analyst wants to track
    # This is separate from search results — curated list of high-interest targets
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS target_companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            name TEXT NOT NULL,
            website TEXT,
            description TEXT,
            location TEXT,
            sector TEXT,
            funding_stage TEXT,
            source_url TEXT,
            notes TEXT,
            status TEXT DEFAULT 'watching',
            priority TEXT DEFAULT 'medium',
            scores TEXT,
            grounding_score REAL,
            news_alerts_enabled INTEGER DEFAULT 0
        )
    """)
    
    # Table for Scheduled Searches — recurring search jobs with email reports
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            search_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            schedule_time TEXT DEFAULT '07:00',
            schedule_timezone TEXT DEFAULT 'Asia/Dubai',
            schedule_frequency TEXT DEFAULT 'daily',
            email_recipient TEXT,
            is_active INTEGER DEFAULT 1,
            last_run_at TIMESTAMP,
            next_run_at TIMESTAMP,
            run_count INTEGER DEFAULT 0,
            FOREIGN KEY (search_id) REFERENCES searches(id)
        )
    """)
    
    # Table 2: Search results (raw company data from Tavily)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            website TEXT,
            source_url TEXT,
            source_snippet TEXT,
            location TEXT,
            sector TEXT,
            founders TEXT,
            funding_stage TEXT,
            funding_amount TEXT,
            grounded_evidence TEXT,
            grounding_score REAL,
            raw_source_text TEXT,
            FOREIGN KEY (search_id) REFERENCES searches(id)
        )
    """)
    
    # Table 3: Scored companies (with dimension scores)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scored_companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_id INTEGER NOT NULL,
            search_result_id INTEGER NOT NULL,
            scores TEXT,
            expected_cac REAL,
            expected_ltv REAL,
            ai_summary TEXT,
            fit_reason TEXT,
            FOREIGN KEY (search_id) REFERENCES searches(id),
            FOREIGN KEY (search_result_id) REFERENCES search_results(id)
        )
    """)
    
    # Table for User Feedback — like/dislike on outputs for AI learning
    # This captures user preferences to improve future results
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            feedback_type TEXT NOT NULL,
            item_type TEXT NOT NULL,
            item_id TEXT,
            item_content TEXT,
            is_positive INTEGER NOT NULL,
            reason TEXT,
            search_id INTEGER,
            company_name TEXT,
            context TEXT,
            FOREIGN KEY (search_id) REFERENCES searches(id)
        )
    """)
    
    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {DB_PATH}")
    
    # Run migrations for existing databases
    _migrate_add_share_id()


def _migrate_add_share_id():
    """
    Migration: Add share_id column to existing searches table.
    
    Safe to run multiple times — checks if column exists first.
    Backfills existing rows with generated share IDs.
    
    Note: SQLite doesn't support adding UNIQUE columns directly,
    so we add the column without UNIQUE constraint and rely on
    generate_share_id() to produce unique values.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if share_id column exists
    cursor.execute("PRAGMA table_info(searches)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if "share_id" not in columns:
        logger.info("Migrating: Adding share_id column to searches table")
        # SQLite doesn't allow UNIQUE on ALTER TABLE, so we add without constraint
        cursor.execute("ALTER TABLE searches ADD COLUMN share_id TEXT")
        
        # Backfill existing rows with generated share IDs
        cursor.execute("SELECT id FROM searches WHERE share_id IS NULL")
        rows = cursor.fetchall()
        for row in rows:
            new_share_id = generate_share_id()
            cursor.execute(
                "UPDATE searches SET share_id = ? WHERE id = ?",
                (new_share_id, row["id"])
            )
        
        conn.commit()
        logger.info(f"Migration complete: Added share_id to {len(rows)} existing searches")
    
    conn.close()


def save_search(
    scout_mode: str,
    benchmark_label: str,
    location: str,
    criteria: List[str],
    sources: List[str],
    exclusions: List[str],
    search_results: List[SearchResult],
    scored_companies: List[ScoredCompany],
) -> Dict[str, any]:
    """
    Save a complete search session to the database.
    
    Returns dict with:
    - search_id: Database ID for internal use
    - share_id: Short code for sharing via email (e.g., "AS-7F3K9X2M")
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Generate unique share ID for email links
    share_id = generate_share_id()
    
    # Calculate average grounding score
    grounding_scores = [sr.grounding_score for sr in search_results if hasattr(sr, 'grounding_score')]
    avg_grounding = sum(grounding_scores) / len(grounding_scores) if grounding_scores else 0.0
    
    # Insert search metadata with share_id
    cursor.execute("""
        INSERT INTO searches (
            share_id, scout_mode, benchmark_label, location, criteria, sources, 
            exclusions, num_results, grounding_score_avg
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        share_id,
        scout_mode,
        benchmark_label,
        location,
        json.dumps(criteria),
        json.dumps(sources),
        json.dumps(exclusions),
        len(search_results),
        avg_grounding,
    ))
    search_id = cursor.lastrowid
    
    # Insert search results
    result_id_map = {}  # Map SearchResult name -> database ID
    for sr in search_results:
        cursor.execute("""
            INSERT INTO search_results (
                search_id, name, description, website, source_url, source_snippet,
                location, sector, founders, funding_stage, funding_amount,
                grounded_evidence, grounding_score, raw_source_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            search_id,
            sr.name,
            sr.description,
            sr.website,
            sr.source_url,
            sr.source_snippet,
            sr.location,
            sr.sector,
            json.dumps(sr.founders) if sr.founders else "[]",
            sr.funding_stage,
            sr.funding_amount,
            json.dumps(sr.grounded_evidence) if hasattr(sr, 'grounded_evidence') else "{}",
            sr.grounding_score if hasattr(sr, 'grounding_score') else 0.0,
            sr.raw_source_text if hasattr(sr, 'raw_source_text') else "",
        ))
        result_id_map[sr.name] = cursor.lastrowid
    
    # Insert scored companies
    for sc in scored_companies:
        sr_name = sc.search_result.name
        sr_id = result_id_map.get(sr_name, 0)
        
        # Convert scores to JSON
        scores_dict = {}
        for dim_key, dim_score in sc.scores.items():
            scores_dict[dim_key] = dim_score.to_dict()
        
        cursor.execute("""
            INSERT INTO scored_companies (
                search_id, search_result_id, scores, expected_cac, 
                expected_ltv, ai_summary, fit_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            search_id,
            sr_id,
            json.dumps(scores_dict),
            sc.expected_cac,
            sc.expected_ltv,
            sc.ai_summary,
            sc.fit_reason,
        ))
    
    conn.commit()
    conn.close()
    logger.info(f"Saved search {search_id} (share_id: {share_id}): {len(search_results)} results, {len(scored_companies)} scored")
    return {"search_id": search_id, "share_id": share_id}


def load_search_by_share_id(share_id: str) -> Optional[Dict]:
    """
    Load a search by its shareable ID (e.g., "AS-7F3K9X2M").
    
    This is the entry point for users clicking email links.
    Returns the same format as load_search().
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Look up the internal search_id from the share_id
    cursor.execute("SELECT id FROM searches WHERE share_id = ?", (share_id.upper(),))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        logger.warning(f"Share ID not found: {share_id}")
        return None
    
    # Delegate to load_search with the internal ID
    return load_search(row["id"])


def load_search(search_id: int) -> Optional[Dict]:
    """
    Load a complete search session from the database.
    
    Returns a dict with:
    - metadata: Search parameters
    - search_results: List of SearchResult objects
    - scored_companies: List of ScoredCompany objects
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Load search metadata
    cursor.execute("SELECT * FROM searches WHERE id = ?", (search_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    
    metadata = {
        "id": row["id"],
        "share_id": row["share_id"] if "share_id" in row.keys() else None,
        "created_at": row["created_at"],
        "scout_mode": row["scout_mode"],
        "benchmark_label": row["benchmark_label"],
        "location": row["location"],
        "criteria": json.loads(row["criteria"]) if row["criteria"] else [],
        "sources": json.loads(row["sources"]) if row["sources"] else [],
        "exclusions": json.loads(row["exclusions"]) if row["exclusions"] else [],
        "num_results": row["num_results"],
        "grounding_score_avg": row["grounding_score_avg"],
    }
    
    # Load search results
    cursor.execute("SELECT * FROM search_results WHERE search_id = ?", (search_id,))
    result_rows = cursor.fetchall()
    
    search_results = []
    result_id_to_sr = {}  # Map database ID -> SearchResult
    for r in result_rows:
        sr = SearchResult(
            name=r["name"],
            description=r["description"] or "Not Found",
            website=r["website"] or "Not Found",
            source_url=r["source_url"] or "",
            source_snippet=r["source_snippet"] or "",
            location=r["location"] or "Not Found",
            sector=r["sector"] or "Not Found",
            founders=json.loads(r["founders"]) if r["founders"] else [],
            founders_linkedin=[],
            funding_stage=r["funding_stage"] or "Not Found",
            funding_amount=r["funding_amount"] or "Not Found",
            grounded_evidence=json.loads(r["grounded_evidence"]) if r["grounded_evidence"] else {},
            grounding_score=r["grounding_score"] or 0.0,
            raw_source_text=r["raw_source_text"] or "",
        )
        search_results.append(sr)
        result_id_to_sr[r["id"]] = sr
    
    # Load scored companies
    cursor.execute("SELECT * FROM scored_companies WHERE search_id = ?", (search_id,))
    scored_rows = cursor.fetchall()
    
    scored_companies = []
    for sc_row in scored_rows:
        sr = result_id_to_sr.get(sc_row["search_result_id"])
        if not sr:
            continue
        
        # Reconstruct scores
        scores_dict = json.loads(sc_row["scores"]) if sc_row["scores"] else {}
        scores = {}
        for dim_key, dim_data in scores_dict.items():
            scores[dim_key] = DimensionScore(
                dimension=dim_data.get("dimension", dim_key),
                score=dim_data.get("score"),
                evidence_quote=dim_data.get("evidence_quote", "N/A"),
                source_url=dim_data.get("source_url", "N/A"),
                reasoning=dim_data.get("reasoning", ""),
                signals_detected=dim_data.get("signals_detected", []),
                sub_scores=dim_data.get("sub_scores", {}),
                grounded_evidence=dim_data.get("grounded_evidence"),
                is_grounded=dim_data.get("is_grounded", False),
            )
        
        sc = ScoredCompany(
            search_result=sr,
            scores=scores,
            expected_cac=sc_row["expected_cac"],
            expected_ltv=sc_row["expected_ltv"],
            ai_summary=sc_row["ai_summary"] or "",
            fit_reason=sc_row["fit_reason"] or "",
        )
        scored_companies.append(sc)
    
    conn.close()
    
    return {
        "metadata": metadata,
        "search_results": search_results,
        "scored_companies": scored_companies,
    }


def list_searches(limit: int = 20) -> List[Dict]:
    """
    List recent searches (most recent first).
    
    Returns a list of metadata dicts (not full results).
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, share_id, created_at, scout_mode, benchmark_label, num_results, grounding_score_avg
        FROM searches
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "id": r["id"],
            "share_id": r["share_id"] if "share_id" in r.keys() else None,
            "created_at": r["created_at"],
            "scout_mode": r["scout_mode"],
            "benchmark_label": r["benchmark_label"],
            "num_results": r["num_results"],
            "grounding_score_avg": r["grounding_score_avg"],
        }
        for r in rows
    ]


def delete_search(search_id: int):
    """
    Delete a search and all its associated data.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM scored_companies WHERE search_id = ?", (search_id,))
    cursor.execute("DELETE FROM search_results WHERE search_id = ?", (search_id,))
    cursor.execute("DELETE FROM searches WHERE id = ?", (search_id,))
    
    conn.commit()
    conn.close()
    logger.info(f"Deleted search {search_id}")


# ---------------------------------------------------------------------------
# Target List Functions
# ---------------------------------------------------------------------------

def add_to_target_list(
    scored_company: ScoredCompany,
    notes: str = "",
    priority: str = "medium",
) -> int:
    """
    Add a company to the target list for tracking.
    
    Returns the target_id.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    sr = scored_company.search_result
    
    # Convert scores to JSON
    scores_dict = {k: v.to_dict() for k, v in scored_company.scores.items()}
    
    cursor.execute("""
        INSERT INTO target_companies (
            name, website, description, location, sector, funding_stage,
            source_url, notes, status, priority, scores, grounding_score,
            news_alerts_enabled
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        sr.name,
        sr.website,
        sr.description,
        sr.location,
        sr.sector,
        sr.funding_stage,
        sr.source_url,
        notes,
        "watching",
        priority,
        json.dumps(scores_dict),
        sr.grounding_score if hasattr(sr, 'grounding_score') else 0.0,
        0,  # news_alerts_enabled — to be implemented later
    ))
    
    target_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    logger.info(f"Added {sr.name} to target list (ID: {target_id})")
    return target_id


def get_target_list() -> List[Dict]:
    """
    Get all companies in the target list.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM target_companies
        ORDER BY added_at DESC
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "id": r["id"],
            "added_at": r["added_at"],
            "name": r["name"],
            "website": r["website"],
            "description": r["description"],
            "location": r["location"],
            "sector": r["sector"],
            "funding_stage": r["funding_stage"],
            "source_url": r["source_url"],
            "notes": r["notes"],
            "status": r["status"],
            "priority": r["priority"],
            "scores": json.loads(r["scores"]) if r["scores"] else {},
            "grounding_score": r["grounding_score"],
            "news_alerts_enabled": bool(r["news_alerts_enabled"]),
        }
        for r in rows
    ]


def update_target(target_id: int, **kwargs):
    """
    Update a target company's fields (notes, status, priority, etc.)
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Build dynamic UPDATE query
    set_clauses = []
    values = []
    for key, value in kwargs.items():
        if key in ["notes", "status", "priority", "news_alerts_enabled"]:
            set_clauses.append(f"{key} = ?")
            values.append(value)
    
    if set_clauses:
        values.append(target_id)
        cursor.execute(
            f"UPDATE target_companies SET {', '.join(set_clauses)} WHERE id = ?",
            values
        )
        conn.commit()
    
    conn.close()


def remove_from_target_list(target_id: int):
    """
    Remove a company from the target list.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM target_companies WHERE id = ?", (target_id,))
    
    conn.commit()
    conn.close()
    logger.info(f"Removed target {target_id}")


def is_in_target_list(company_name: str) -> bool:
    """
    Check if a company is already in the target list.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT COUNT(*) FROM target_companies WHERE name = ?",
        (company_name,)
    )
    count = cursor.fetchone()[0]
    conn.close()
    
    return count > 0


# ---------------------------------------------------------------------------
# Scheduled Search Functions
# ---------------------------------------------------------------------------

def schedule_search(
    search_id: int,
    name: str,
    email_recipient: str,
    schedule_time: str = "07:00",
    schedule_timezone: str = "Asia/Dubai",
    schedule_frequency: str = "daily",
) -> int:
    """
    Schedule a search to run automatically with email reports.
    
    Default: Daily at 7:00 AM UAE time.
    Returns the schedule_id.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO scheduled_searches (
            search_id, name, schedule_time, schedule_timezone,
            schedule_frequency, email_recipient, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, 1)
    """, (
        search_id,
        name,
        schedule_time,
        schedule_timezone,
        schedule_frequency,
        email_recipient,
    ))
    
    schedule_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    logger.info(f"Scheduled search {search_id} as '{name}' (ID: {schedule_id})")
    return schedule_id


def get_scheduled_searches() -> List[Dict]:
    """
    Get all scheduled searches.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT ss.*, s.scout_mode, s.benchmark_label, s.num_results
        FROM scheduled_searches ss
        JOIN searches s ON ss.search_id = s.id
        ORDER BY ss.created_at DESC
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "id": r["id"],
            "search_id": r["search_id"],
            "name": r["name"],
            "schedule_time": r["schedule_time"],
            "schedule_timezone": r["schedule_timezone"],
            "schedule_frequency": r["schedule_frequency"],
            "email_recipient": r["email_recipient"],
            "is_active": bool(r["is_active"]),
            "last_run_at": r["last_run_at"],
            "run_count": r["run_count"],
            "scout_mode": r["scout_mode"],
            "benchmark_label": r["benchmark_label"],
            "num_results": r["num_results"],
        }
        for r in rows
    ]


def toggle_scheduled_search(schedule_id: int, is_active: bool):
    """
    Enable or disable a scheduled search.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "UPDATE scheduled_searches SET is_active = ? WHERE id = ?",
        (1 if is_active else 0, schedule_id)
    )
    
    conn.commit()
    conn.close()


def delete_scheduled_search(schedule_id: int):
    """
    Delete a scheduled search.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM scheduled_searches WHERE id = ?", (schedule_id,))
    
    conn.commit()
    conn.close()
    logger.info(f"Deleted scheduled search {schedule_id}")


# ---------------------------------------------------------------------------
# User Feedback Functions — Like/Dislike for AI Learning
# ---------------------------------------------------------------------------

def save_feedback(
    feedback_type: str,
    item_type: str,
    is_positive: bool,
    item_id: str = None,
    item_content: str = None,
    reason: str = None,
    search_id: int = None,
    company_name: str = None,
    context: str = None,
) -> int:
    """
    Save user feedback (like/dislike) on an output.
    
    Args:
        feedback_type: Category of feedback (e.g., "company", "source", "score", "summary")
        item_type: Specific type (e.g., "website", "description", "grounding")
        is_positive: True = like (thumbs up), False = dislike (thumbs down)
        item_id: Unique identifier for the item (e.g., URL, company name)
        item_content: The actual content being rated
        reason: Optional user-provided reason for the feedback
        search_id: Associated search session
        company_name: Company this feedback relates to
        context: Additional context (JSON string)
    
    Returns:
        feedback_id
    
    Why this matters:
    - Captures user preferences to improve future results
    - Identifies patterns in what users like/dislike
    - Can be used to fine-tune prompts or adjust scoring weights
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO user_feedback (
            feedback_type, item_type, item_id, item_content,
            is_positive, reason, search_id, company_name, context
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        feedback_type,
        item_type,
        item_id,
        item_content[:1000] if item_content else None,  # Truncate long content
        1 if is_positive else 0,
        reason,
        search_id,
        company_name,
        context,
    ))
    
    feedback_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    logger.info(f"Saved feedback {feedback_id}: {feedback_type}/{item_type} = {'👍' if is_positive else '👎'}")
    return feedback_id


def get_feedback_stats() -> Dict:
    """
    Get aggregated feedback statistics for AI learning.
    
    Returns stats on what users like/dislike to inform improvements.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Overall stats
    cursor.execute("""
        SELECT 
            feedback_type,
            item_type,
            SUM(CASE WHEN is_positive = 1 THEN 1 ELSE 0 END) as likes,
            SUM(CASE WHEN is_positive = 0 THEN 1 ELSE 0 END) as dislikes,
            COUNT(*) as total
        FROM user_feedback
        GROUP BY feedback_type, item_type
        ORDER BY total DESC
    """)
    
    by_type = [
        {
            "feedback_type": r[0],
            "item_type": r[1],
            "likes": r[2],
            "dislikes": r[3],
            "total": r[4],
            "approval_rate": r[2] / r[4] if r[4] > 0 else 0,
        }
        for r in cursor.fetchall()
    ]
    
    # Recent feedback (last 7 days)
    cursor.execute("""
        SELECT 
            feedback_type, item_type, item_content, is_positive, reason, company_name
        FROM user_feedback
        WHERE created_at > datetime('now', '-7 days')
        ORDER BY created_at DESC
        LIMIT 50
    """)
    
    recent = [
        {
            "feedback_type": r[0],
            "item_type": r[1],
            "item_content": r[2][:100] if r[2] else None,
            "is_positive": bool(r[3]),
            "reason": r[4],
            "company_name": r[5],
        }
        for r in cursor.fetchall()
    ]
    
    # Patterns in dislikes (what to improve)
    cursor.execute("""
        SELECT item_type, item_content, COUNT(*) as count
        FROM user_feedback
        WHERE is_positive = 0
        GROUP BY item_type, item_content
        HAVING count > 1
        ORDER BY count DESC
        LIMIT 20
    """)
    
    dislike_patterns = [
        {"item_type": r[0], "item_content": r[1][:100] if r[1] else None, "count": r[2]}
        for r in cursor.fetchall()
    ]
    
    conn.close()
    
    return {
        "by_type": by_type,
        "recent": recent,
        "dislike_patterns": dislike_patterns,
    }


def get_feedback_for_learning() -> List[Dict]:
    """
    Get all feedback in a format suitable for AI learning/fine-tuning.
    
    Returns structured data that can be used to:
    - Adjust prompt templates
    - Modify scoring weights
    - Identify problematic patterns
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            uf.*,
            s.scout_mode,
            s.benchmark_label
        FROM user_feedback uf
        LEFT JOIN searches s ON uf.search_id = s.id
        ORDER BY uf.created_at DESC
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "id": r["id"],
            "created_at": r["created_at"],
            "feedback_type": r["feedback_type"],
            "item_type": r["item_type"],
            "item_id": r["item_id"],
            "item_content": r["item_content"],
            "is_positive": bool(r["is_positive"]),
            "reason": r["reason"],
            "company_name": r["company_name"],
            "context": r["context"],
            "scout_mode": r["scout_mode"] if "scout_mode" in r.keys() else None,
            "benchmark_label": r["benchmark_label"] if "benchmark_label" in r.keys() else None,
        }
        for r in rows
    ]
