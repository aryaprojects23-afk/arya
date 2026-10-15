"""
HarvestLink 2.0 - Configuration Module
Manages application settings, environment variables, language definitions, and constants.
"""

import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
LOCALES_DIR = BASE_DIR / "locales"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
DATA_DIR = BASE_DIR / "data"

# Ensure runtime directories exist
DATA_DIR.mkdir(exist_ok=True)
LOCALES_DIR.mkdir(exist_ok=True)

# Server Config
PORT = int(os.getenv("PORT", 8000))
HOST = os.getenv("HOST", "0.0.0.0")
DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")
SECRET_KEY = os.getenv("SECRET_KEY", "harvestlink-super-secret-key-2026")

# Database Config
DATABASE_PATH = str(DATA_DIR / "harvestlink.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_PATH}")

# Government Open Data API (AGMARKNET via data.gov.in)
OGD_API_KEY = os.getenv("OGD_API_KEY", "")
# Default resource ID for Current Daily Price of Various Commodities from Various Markets
GOV_DATA_API_BASE = os.getenv(
    "GOV_DATA_API_BASE", 
    "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
)
GOV_SYNC_INTERVAL_HOURS = int(os.getenv("GOV_SYNC_INTERVAL_HOURS", 6))
GOV_REQUEST_TIMEOUT_SECONDS = int(os.getenv("GOV_REQUEST_TIMEOUT_SECONDS", 15))
GOV_MAX_RETRIES = int(os.getenv("GOV_MAX_RETRIES", 3))

# Demonstration / Default Region
DEFAULT_STATE = os.getenv("DEFAULT_STATE", "Andhra Pradesh")
DEFAULT_DISTRICT = os.getenv("DEFAULT_DISTRICT", "Chittoor")

# Official Attribution String
GOV_ATTRIBUTION = (
    "Official Data Source: Directorate of Marketing & Inspection (DMI), "
    "Ministry of Agriculture & Farmers Welfare, Government of India, "
    "via Open Government Data (OGD) Platform India (data.gov.in / Agmarknet)."
)

# 22 Official Supported Indian Languages
SUPPORTED_LANGUAGES = {
    "en": {"name": "English", "native": "English", "direction": "ltr", "script": "Latin"},
    "hi": {"name": "Hindi", "native": "हिन्दी", "direction": "ltr", "script": "Devanagari"},
    "te": {"name": "Telugu", "native": "తెలుగు", "direction": "ltr", "script": "Telugu"},
    "ta": {"name": "Tamil", "native": "தமிழ்", "direction": "ltr", "script": "Tamil"},
    "kn": {"name": "Kannada", "native": "ಕನ್ನಡ", "direction": "ltr", "script": "Kannada"},
    "ml": {"name": "Malayalam", "native": "മലയാളം", "direction": "ltr", "script": "Malayalam"},
    "bn": {"name": "Bengali", "native": "বাংলা", "direction": "ltr", "script": "Bengali"},
    "mr": {"name": "Marathi", "native": "मराठी", "direction": "ltr", "script": "Devanagari"},
    "gu": {"name": "Gujarati", "native": "ગુજરાતી", "direction": "ltr", "script": "Gujarati"},
    "pa": {"name": "Punjabi", "native": "ਪੰਜਾਬੀ", "direction": "ltr", "script": "Gurmukhi"},
    "or": {"name": "Odia", "native": "ଓଡ଼ିଆ", "direction": "ltr", "script": "Odia"},
    "as": {"name": "Assamese", "native": "অসমীয়া", "direction": "ltr", "script": "Bengali-Assamese"},
    "ur": {"name": "Urdu", "native": "اردو", "direction": "rtl", "script": "Nastaliq / Arabic"},
    "sa": {"name": "Sanskrit", "native": "संस्कृतम्", "direction": "ltr", "script": "Devanagari"},
    "ks": {"name": "Kashmiri", "native": "کٲشُر / कॉशुर", "direction": "rtl", "script": "Perso-Arabic"},
    "kok": {"name": "Konkani", "native": "कोंकणी", "direction": "ltr", "script": "Devanagari"},
    "mni": {"name": "Manipuri (Meitei)", "native": "মৈতৈলোন্", "direction": "ltr", "script": "Bengali / Meitei"},
    "ne": {"name": "Nepali", "native": "नेपाली", "direction": "ltr", "script": "Devanagari"},
    "sat": {"name": "Santali", "native": "ᱥᱟᱱᱛᱟᱲᱤ", "direction": "ltr", "script": "Ol Chiki"},
    "brx": {"name": "Bodo", "native": "बड़ो", "direction": "ltr", "script": "Devanagari"},
    "doi": {"name": "Dogri", "native": "डोगरी", "direction": "ltr", "script": "Devanagari"},
    "mai": {"name": "Maithili", "native": "मैथिली", "direction": "ltr", "script": "Devanagari"},
}

DEFAULT_LANGUAGE = "en"
