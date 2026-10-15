"""
HarvestLink 2.0 - Internationalization (i18n) Service
Manages 22 Indian language dictionaries, completeness auditing, and user translation feedback.
"""

import json
import logging
from typing import Dict, Any, List
from pathlib import Path
from backend.config import LOCALES_DIR, SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE
from backend.database import db_session

logger = logging.getLogger("harvestlink.i18n")

# In-memory locale cache
_LOCALE_CACHE: Dict[str, Dict[str, Any]] = {}

def load_locale(lang_code: str) -> Dict[str, Any]:
    """Load locale JSON file, falling back to English if missing."""
    if lang_code in _LOCALE_CACHE:
        return _LOCALE_CACHE[lang_code]
    
    locale_file = LOCALES_DIR / f"{lang_code}.json"
    if not locale_file.exists():
        logger.warning(f"Locale file for '{lang_code}' not found. Falling back to English.")
        locale_file = LOCALES_DIR / f"{DEFAULT_LANGUAGE}.json"
    
    try:
        with open(locale_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            _LOCALE_CACHE[lang_code] = data
            return data
    except Exception as e:
        logger.error(f"Error loading locale {lang_code}: {e}")
        # Last resort fallback
        if lang_code != DEFAULT_LANGUAGE:
            return load_locale(DEFAULT_LANGUAGE)
        return {}

def flatten_keys(d: Dict[str, Any], prefix: str = "") -> Dict[str, str]:
    """Flatten nested translation dictionary to dot-notation keys."""
    items = {}
    for k, v in d.items():
        new_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.update(flatten_keys(v, new_key))
        else:
            items[new_key] = str(v)
    return items

def get_completeness_report() -> Dict[str, Any]:
    """
    Generate an exhaustive translation completeness audit for all 22 languages.
    Compares every locale against the master English key dictionary.
    """
    master_en = load_locale("en")
    flat_en = flatten_keys(master_en)
    total_master_keys = len(flat_en)

    report_list = []
    
    for code, info in SUPPORTED_LANGUAGES.items():
        locale_dict = load_locale(code)
        flat_locale = flatten_keys(locale_dict)
        
        # Check matching keys
        translated_count = 0
        missing_keys = []
        
        for k in flat_en.keys():
            val = flat_locale.get(k)
            if val is not None and str(val).strip() != "":
                translated_count += 1
            else:
                missing_keys.append(k)
        
        coverage = round((translated_count / total_master_keys) * 100, 1) if total_master_keys > 0 else 100.0
        
        status = "Complete" if coverage >= 100.0 else ("Ready" if coverage >= 95.0 else "In Progress")
        
        report_list.append({
            "code": code,
            "name": info["name"],
            "native": info["native"],
            "direction": info["direction"],
            "script": info["script"],
            "total_keys": total_master_keys,
            "translated_keys": translated_count,
            "missing_keys_count": len(missing_keys),
            "missing_keys": missing_keys[:5], # sample if any
            "coverage_percentage": coverage,
            "status": status
        })

    return {
        "total_languages": len(SUPPORTED_LANGUAGES),
        "total_master_keys": total_master_keys,
        "languages": report_list,
        "default_language": DEFAULT_LANGUAGE
    }

def record_translation_report(language_code: str, translation_key: str, current_text: str,
                              suggested_correction: str, user_notes: str = None,
                              reporter_user_id: str = None) -> int:
    """Store user-reported translation feedback in the database."""
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO translation_reports (
                language_code, translation_key, current_text,
                suggested_correction, user_notes, reporter_user_id
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (language_code, translation_key, current_text, suggested_correction, user_notes, reporter_user_id))
        return cursor.lastrowid

def get_translation_reports(limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieve recent translation improvement submissions."""
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, language_code, translation_key, current_text,
                   suggested_correction, user_notes, reporter_user_id, status, created_at
            FROM translation_reports
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
