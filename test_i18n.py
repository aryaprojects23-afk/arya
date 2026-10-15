"""
Automated Test Suite: 22 Languages Internationalization (i18n) & Completeness
"""

import json
import pytest
from pathlib import Path
from backend.config import LOCALES_DIR, SUPPORTED_LANGUAGES
from backend.services.i18n_service import (
    load_locale, flatten_keys, get_completeness_report,
    record_translation_report, get_translation_reports
)
from backend.database import init_db

@pytest.fixture(autouse=True)
def setup_database():
    init_db()

def test_all_22_locales_exist():
    """Verify that all 22 required Indian language locale files exist on disk."""
    assert len(SUPPORTED_LANGUAGES) == 22, "Must support at least 22 Indian languages."
    
    for code in SUPPORTED_LANGUAGES.keys():
        file_path = LOCALES_DIR / f"{code}.json"
        assert file_path.exists(), f"Locale file for '{code}' is missing at {file_path}"
        
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert isinstance(data, dict), f"Locale {code} must be a valid JSON dictionary."
            assert "meta" in data, f"Locale {code} must contain 'meta' section."
            assert "nav" in data, f"Locale {code} must contain 'nav' section."
            assert "mandi" in data, f"Locale {code} must contain 'mandi' section."
            assert "compare" in data, f"Locale {code} must contain 'compare' section."

def test_translation_completeness_and_key_parity():
    """Verify key parity of all 22 languages against the master English key dictionary."""
    report = get_completeness_report()
    assert report["total_languages"] == 22
    assert report["total_master_keys"] > 50

    for lang_entry in report["languages"]:
        assert lang_entry["coverage_percentage"] >= 95.0, (
            f"Language {lang_entry['code']} ({lang_entry['name']}) coverage is "
            f"{lang_entry['coverage_percentage']}%, below 95% threshold!"
        )
        assert lang_entry["status"] in ("Complete", "Ready")

def test_rtl_layout_configuration():
    """Verify Urdu (ur) and Kashmiri (ks) are correctly configured with RTL direction."""
    assert SUPPORTED_LANGUAGES["ur"]["direction"] == "rtl"
    assert SUPPORTED_LANGUAGES["ks"]["direction"] == "rtl"
    assert SUPPORTED_LANGUAGES["hi"]["direction"] == "ltr"
    assert SUPPORTED_LANGUAGES["te"]["direction"] == "ltr"
    assert SUPPORTED_LANGUAGES["ta"]["direction"] == "ltr"

def test_translation_reporting_service():
    """Verify users can report translation improvements and they are recorded in database."""
    rep_id = record_translation_report(
        language_code="te",
        translation_key="mandi.col_modal_price",
        current_text="మోడల్ ధర",
        suggested_correction="సగటు మార్కెట్ ధర",
        user_notes="Rayalaseema local dialect terminology"
    )
    assert rep_id > 0

    reports = get_translation_reports(limit=10)
    assert any(r["id"] == rep_id and r["language_code"] == "te" for r in reports)
