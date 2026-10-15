"""
HarvestLink 2.0 - Smart Search & Localized Commodity Catalog Service
Maps regional crop terms, local language aliases, and vernacular dialects to canonical commodities.
"""

from typing import List, Dict, Any, Optional
from backend.database import db_session

def search_commodities(query: str, lang: str = "en", limit: int = 15) -> List[Dict[str, Any]]:
    """
    Multilingual fuzzy & alias-aware search.
    A user searching for 'tamatar' (Hindi/Urdu), 'thakkali' (Tamil/Malayalam), 'batata' (Marathi/Konkani),
    or 'aloo' matches the underlying canonical commodity (Tomato, Potato, etc.).
    """
    clean_q = query.strip().lower()
    if not clean_q:
        return get_all_commodities(lang=lang, limit=limit)

    with db_session() as conn:
        cursor = conn.cursor()
        
        # 1. Exact or partial match on canonical_name, aliases, or translations
        sql = """
            SELECT DISTINCT c.id, c.canonical_name, c.category, c.standard_unit, c.image_url,
                   COALESCE(ct.localized_name, c.canonical_name) as display_name,
                   ca.alias_term as matched_term
            FROM commodities c
            LEFT JOIN commodity_translations ct ON c.id = ct.commodity_id AND ct.language_code = ?
            LEFT JOIN commodity_aliases ca ON c.id = ca.commodity_id
            WHERE LOWER(c.canonical_name) LIKE ?
               OR LOWER(ct.localized_name) LIKE ?
               OR LOWER(ca.alias_term) LIKE ?
            LIMIT ?
        """
        pattern = f"%{clean_q}%"
        cursor.execute(sql, (lang, pattern, pattern, pattern, limit))
        rows = cursor.fetchall()
        
        results = []
        seen = set()
        for r in rows:
            if r["id"] not in seen:
                seen.add(r["id"])
                results.append({
                    "id": r["id"],
                    "canonical_name": r["canonical_name"],
                    "display_name": r["display_name"],
                    "category": r["category"],
                    "standard_unit": r["standard_unit"],
                    "image_url": r["image_url"],
                    "matched_term": r["matched_term"]
                })
        return results

def get_autocomplete_suggestions(query: str, lang: str = "en", limit: int = 8) -> List[Dict[str, Any]]:
    """Fast prefix and substring suggestions for search bars."""
    clean_q = query.strip().lower()
    if len(clean_q) < 1:
        return []

    with db_session() as conn:
        cursor = conn.cursor()
        sql = """
            SELECT DISTINCT ca.alias_term, c.id as commodity_id, c.canonical_name,
                   COALESCE(ct.localized_name, c.canonical_name) as localized_name
            FROM commodity_aliases ca
            JOIN commodities c ON ca.commodity_id = c.id
            LEFT JOIN commodity_translations ct ON c.id = ct.commodity_id AND ct.language_code = ?
            WHERE LOWER(ca.alias_term) LIKE ?
            LIMIT ?
        """
        cursor.execute(sql, (lang, f"{clean_q}%", limit))
        rows = cursor.fetchall()

        suggestions = []
        for r in rows:
            suggestions.append({
                "term": r["alias_term"],
                "commodity_id": r["commodity_id"],
                "canonical_name": r["canonical_name"],
                "localized_name": r["localized_name"]
            })
        return suggestions

def get_all_commodities(lang: str = "en", limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieve full catalog with localized display names and varieties."""
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.id, c.canonical_name, c.category, c.scientific_name,
                   c.standard_unit, c.image_url,
                   COALESCE(ct.localized_name, c.canonical_name) as display_name
            FROM commodities c
            LEFT JOIN commodity_translations ct ON c.id = ct.commodity_id AND ct.language_code = ?
            WHERE c.is_active = 1
            ORDER BY c.canonical_name ASC
            LIMIT ?
        """, (lang, limit))
        
        commodities = []
        for r in cursor.fetchall():
            cid = r["id"]
            # Fetch varieties
            cursor.execute("SELECT variety_name FROM commodity_varieties WHERE commodity_id = ?", (cid,))
            vars_list = [v[0] for v in cursor.fetchall()]
            if not vars_list:
                vars_list = ["Standard", "Hybrid", "Desi"]

            commodities.append({
                "id": cid,
                "canonical_name": r["canonical_name"],
                "display_name": r["display_name"],
                "category": r["category"],
                "scientific_name": r["scientific_name"],
                "standard_unit": r["standard_unit"],
                "image_url": r["image_url"],
                "varieties": vars_list
            })
        return commodities

def get_commodity_by_id(commodity_id: str, lang: str = "en") -> Optional[Dict[str, Any]]:
    """Retrieve detailed commodity metadata, localized name, and varieties."""
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.id, c.canonical_name, c.category, c.scientific_name,
                   c.standard_unit, c.image_url,
                   COALESCE(ct.localized_name, c.canonical_name) as display_name
            FROM commodities c
            LEFT JOIN commodity_translations ct ON c.id = ct.commodity_id AND ct.language_code = ?
            WHERE c.id = ?
        """, (lang, commodity_id))
        row = cursor.fetchone()
        if not row:
            return None

        cursor.execute("SELECT variety_name FROM commodity_varieties WHERE commodity_id = ?", (commodity_id,))
        varieties = [v[0] for v in cursor.fetchall()]

        cursor.execute("SELECT alias_term FROM commodity_aliases WHERE commodity_id = ?", (commodity_id,))
        aliases = [a[0] for a in cursor.fetchall()]

        return {
            "id": row["id"],
            "canonical_name": row["canonical_name"],
            "display_name": row["display_name"],
            "category": row["category"],
            "scientific_name": row["scientific_name"],
            "standard_unit": row["standard_unit"],
            "image_url": row["image_url"],
            "varieties": varieties or ["Standard", "Hybrid", "Desi"],
            "aliases": aliases
        }
