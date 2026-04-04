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
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import asdict

from models import SearchResult, ScoredCompany, DimensionScore

logger = logging.getLogger(__name__)

# Database file location (same directory as app)
DB_PATH = os.path.join(os.path.dirname(__file__), "alpha_scout.db")


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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    
    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {DB_PATH}")


def save_search(
    scout_mode: str,
    benchmark_label: str,
    location: str,
    criteria: List[str],
    sources: List[str],
    exclusions: List[str],
    search_results: List[SearchResult],
    scored_companies: List[ScoredCompany],
) -> int:
    """
    Save a complete search session to the database.
    
    Returns the search_id for future reference.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Calculate average grounding score
    grounding_scores = [sr.grounding_score for sr in search_results if hasattr(sr, 'grounding_score')]
    avg_grounding = sum(grounding_scores) / len(grounding_scores) if grounding_scores else 0.0
    
    # Insert search metadata
    cursor.execute("""
        INSERT INTO searches (
            scout_mode, benchmark_label, location, criteria, sources, 
            exclusions, num_results, grounding_score_avg
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
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
    logger.info(f"Saved search {search_id}: {len(search_results)} results, {len(scored_companies)} scored")
    return search_id


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
        SELECT id, created_at, scout_mode, benchmark_label, num_results, grounding_score_avg
        FROM searches
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "id": r["id"],
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
