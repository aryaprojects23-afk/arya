"""
HarvestLink 2.0 - Government Mandi Market Price Integration Service
Official AGMARKNET / Open Government Data Platform India (data.gov.in) Adapter.
Provides real API querying, rate limiting, exponential backoff, database caching,
historical price trends, nearby mandi comparisons, and health tracking.
"""

import time
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from backend.config import (
    OGD_API_KEY,
    GOV_DATA_API_BASE,
    GOV_REQUEST_TIMEOUT_SECONDS,
    GOV_MAX_RETRIES,
    GOV_SYNC_INTERVAL_HOURS,
    GOV_ATTRIBUTION,
    DEFAULT_STATE,
    DEFAULT_DISTRICT
)
from backend.database import db_session

logger = logging.getLogger("harvestlink.gov_market")

class GovMarketPriceAdapter:
    """
    Adapter for Open Government Data Platform India (data.gov.in)
    AGMARKNET APMC Daily Commodity Wholesale Prices.
    """
    PROVIDER_ID = "ogd_agmarknet_in"
    PROVIDER_NAME = "Open Government Data Platform India (data.gov.in - Agmarknet)"
    SOURCE_URL = "https://www.data.gov.in/resource/current-daily-price-various-commodities-various-markets-mandi"

    def __init__(self):
        self.api_key = OGD_API_KEY
        self.api_base = GOV_DATA_API_BASE
        self.timeout = GOV_REQUEST_TIMEOUT_SECONDS
        self.max_retries = GOV_MAX_RETRIES
        self.session = self._create_resilient_session()

    def _create_resilient_session(self) -> requests.Session:
        """Create requests session with retry strategy and exponential backoff."""
        session = requests.Session()
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def fetch_live_records(self, state: str = None, district: str = None,
                           commodity: str = None, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """
        Query the official OGD API endpoint with parameters and API key.
        Returns normalized payload or raises informative exceptions.
        """
        if not self.api_key:
            raise ValueError(
                "OGD_API_KEY is not configured in environment. "
                "Official live API requests require a free API key from https://data.gov.in"
            )

        params = {
            "api-key": self.api_key,
            "format": "json",
            "offset": offset,
            "limit": limit
        }

        # Apply server-side filters if provided
        filters = {}
        if state:
            filters["state"] = state
        if district:
            filters["district"] = district
        if commodity:
            filters["commodity"] = commodity
        
        if filters:
            for k, v in filters.items():
                params[f"filters[{k}]"] = v

        start_time = time.time()
        try:
            response = self.session.get(self.api_base, params=params, timeout=self.timeout)
            latency_ms = int((time.time() - start_time) * 1000)

            if response.status_code == 200:
                data = response.json()
                raw_records = data.get("records", [])
                total_available = data.get("total", len(raw_records))
                self._update_provider_health(True, latency_ms=latency_ms, status_code=200, message="Live API responsive.")
                return {
                    "success": True,
                    "records": raw_records,
                    "total": total_available,
                    "latency_ms": latency_ms,
                    "source": "live_api"
                }
            elif response.status_code in (401, 403):
                msg = f"Official API Authentication Error ({response.status_code}). Check your OGD_API_KEY."
                self._update_provider_health(False, latency_ms=latency_ms, status_code=response.status_code, message=msg)
                raise PermissionError(msg)
            else:
                msg = f"Official Portal returned HTTP {response.status_code}: {response.text[:200]}"
                self._update_provider_health(False, latency_ms=latency_ms, status_code=response.status_code, message=msg)
                raise RuntimeError(msg)

        except requests.exceptions.RequestException as e:
            latency_ms = int((time.time() - start_time) * 1000)
            msg = f"Network or timeout error contacting official portal: {str(e)}"
            self._update_provider_health(False, latency_ms=latency_ms, status_code=0, message=msg)
            raise ConnectionError(msg)

    def normalize_and_store_records(self, raw_records: List[Dict[str, Any]], is_live: bool = True) -> Dict[str, int]:
        """
        Normalize raw API or seed records into canonical schema and persist in SQLite.
        Guarantees idempotent updates and duplicate prevention.
        """
        inserted = 0
        updated = 0
        now_str = datetime.now().isoformat()

        with db_session() as conn:
            cursor = conn.cursor()
            for r in raw_records:
                # Normalize keys across possible field variations in data.gov.in Agmarknet outputs
                state = r.get("state") or r.get("State") or "Unknown"
                district = r.get("district") or r.get("District") or "Unknown"
                market = r.get("market") or r.get("market_name") or r.get("Market") or "General APMC"
                commodity = r.get("commodity") or r.get("commodity_name") or r.get("Commodity") or "Produce"
                variety = r.get("variety") or r.get("Variety") or "Other"
                grade = r.get("grade") or r.get("Grade") or "FAQ"
                arrival_date = r.get("arrival_date") or r.get("Arrival_Date") or datetime.now().strftime("%Y-%m-%d")
                
                # Format arrival date to YYYY-MM-DD
                if "/" in str(arrival_date):
                    parts = str(arrival_date).split("/")
                    if len(parts) == 3:
                        if len(parts[0]) == 4: # YYYY/MM/DD
                            arrival_date = f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
                        else: # DD/MM/YYYY
                            arrival_date = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"

                try:
                    min_price = float(r.get("min_price") or r.get("Min_Price") or 0.0)
                    max_price = float(r.get("max_price") or r.get("Max_Price") or 0.0)
                    modal_price = float(r.get("modal_price") or r.get("Modal_Price") or 0.0)
                    arrivals = float(r.get("arrivals_in_qtl") or r.get("Arrivals_Tonnes") or r.get("arrivals_in_tonnes") or 0.0)
                except (ValueError, TypeError):
                    continue

                if modal_price <= 0 and (min_price > 0 or max_price > 0):
                    modal_price = round((min_price + max_price) / 2.0, 2)

                source_rec_id = str(r.get("id") or r.get("record_id") or f"{state}_{district}_{market}_{commodity}_{arrival_date}")
                raw_json = json.dumps(r)

                # Check if record already exists to accurately count inserted vs updated
                cursor.execute("""
                    SELECT id FROM government_market_price_records
                    WHERE state = ? AND district = ? AND market_name = ?
                      AND commodity_name = ? AND variety = ? AND grade = ? AND arrival_date = ?
                """, (state, district, market, commodity, variety, grade, arrival_date))
                existing_row = cursor.fetchone()

                # Upsert record
                cursor.execute("""
                    INSERT INTO government_market_price_records (
                        source_record_id, state, district, market_name, commodity_name,
                        variety, grade, arrival_date, min_price, max_price, modal_price,
                        price_unit, arrivals_in_tonnes, retrieval_timestamp, is_live_synced, raw_source_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(state, district, market_name, commodity_name, variety, grade, arrival_date)
                    DO UPDATE SET
                        min_price = excluded.min_price,
                        max_price = excluded.max_price,
                        modal_price = excluded.modal_price,
                        arrivals_in_tonnes = excluded.arrivals_in_tonnes,
                        retrieval_timestamp = excluded.retrieval_timestamp,
                        is_live_synced = excluded.is_live_synced;
                """, (
                    source_rec_id, state, district, market, commodity, variety, grade,
                    arrival_date, min_price, max_price, modal_price, "Rs/Quintal",
                    arrivals, now_str, 1 if is_live else 0, raw_json
                ))

                if existing_row:
                    updated += 1
                else:
                    inserted += 1

                # Also ensure market entry is tracked
                market_id = f"{state.lower()}-{district.lower()}-{market.lower()}".replace(" ", "-")
                cursor.execute("""
                    INSERT OR IGNORE INTO markets (id, name, state, district, is_active)
                    VALUES (?, ?, ?, ?, 1);
                """, (market_id, market, state, district))

        return {"inserted": inserted, "updated": updated}

    def _update_provider_health(self, is_healthy: bool, latency_ms: int = 0, status_code: int = 0, message: str = ""):
        """Update provider health tracking table."""
        now_str = datetime.now().isoformat()
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO provider_health_status (
                    provider_id, provider_name, is_healthy, consecutive_failures,
                    last_checked_at, last_success_at, last_status_code, latency_ms, message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider_id) DO UPDATE SET
                    is_healthy = excluded.is_healthy,
                    consecutive_failures = CASE WHEN excluded.is_healthy = 1 THEN 0 ELSE provider_health_status.consecutive_failures + 1 END,
                    last_checked_at = excluded.last_checked_at,
                    last_success_at = CASE WHEN excluded.is_healthy = 1 THEN excluded.last_checked_at ELSE provider_health_status.last_success_at END,
                    last_status_code = excluded.last_status_code,
                    latency_ms = excluded.latency_ms,
                    message = excluded.message;
            """, (
                self.PROVIDER_ID, self.PROVIDER_NAME, 1 if is_healthy else 0,
                0 if is_healthy else 1, now_str, now_str if is_healthy else None,
                status_code, latency_ms, message
            ))

    def get_provider_health(self) -> Dict[str, Any]:
        """Query current provider health and database record statistics."""
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM provider_health_status WHERE provider_id = ?", (self.PROVIDER_ID,))
            row = cursor.fetchone()
            
            cursor.execute("SELECT COUNT(*), MAX(retrieval_timestamp) FROM government_market_price_records")
            cnt_row = cursor.fetchone()
            total_records = cnt_row[0] if cnt_row else 0
            last_record_ts = cnt_row[1] if cnt_row else None

            cursor.execute("SELECT status FROM government_data_sync_logs ORDER BY id DESC LIMIT 1")
            sync_row = cursor.fetchone()
            last_sync_status = sync_row["status"] if sync_row else "INITIALIZED"

            if row:
                return {
                    "provider_id": self.PROVIDER_ID,
                    "provider_name": self.PROVIDER_NAME,
                    "is_healthy": bool(row["is_healthy"]),
                    "last_checked_at": row["last_checked_at"],
                    "last_success_at": row["last_success_at"],
                    "latency_ms": row["latency_ms"],
                    "sync_interval_hours": GOV_SYNC_INTERVAL_HOURS,
                    "total_records_cached": total_records,
                    "last_sync_status": last_sync_status,
                    "last_record_timestamp": last_record_ts,
                    "source_attribution": GOV_ATTRIBUTION,
                    "source_link": self.SOURCE_URL,
                    "api_key_configured": bool(self.api_key)
                }
            else:
                return {
                    "provider_id": self.PROVIDER_ID,
                    "provider_name": self.PROVIDER_NAME,
                    "is_healthy": False,
                    "last_checked_at": None,
                    "last_success_at": None,
                    "latency_ms": None,
                    "sync_interval_hours": GOV_SYNC_INTERVAL_HOURS,
                    "total_records_cached": total_records,
                    "last_sync_status": last_sync_status,
                    "last_record_timestamp": last_record_ts,
                    "source_attribution": GOV_ATTRIBUTION,
                    "source_link": self.SOURCE_URL,
                    "api_key_configured": bool(self.api_key)
                }

    def sync_data(self, state: str = None, district: str = None, limit: int = 100) -> Dict[str, Any]:
        """
        Execute scheduled or manual synchronization. Logs to government_data_sync_logs.
        If API key is missing or portal fails, falls back gracefully to cached data.
        """
        start_ts = time.time()
        now_str = datetime.now().isoformat()
        try:
            result = self.fetch_live_records(state=state, district=district, limit=limit)
            storage_res = self.normalize_and_store_records(result["records"], is_live=True)
            elapsed_ms = int((time.time() - start_ts) * 1000)

            with db_session() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO government_data_sync_logs (
                        sync_timestamp, source_name, records_fetched,
                        records_inserted, records_updated, status, response_time_ms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    now_str, "OGD_API", len(result["records"]),
                    storage_res["inserted"], storage_res["updated"], "SUCCESS", elapsed_ms
                ))

            return {
                "status": "SUCCESS",
                "message": f"Successfully synchronized {len(result['records'])} live official records from data.gov.in",
                "records_fetched": len(result["records"]),
                "records_inserted": storage_res["inserted"],
                "records_updated": storage_res["updated"],
                "response_time_ms": elapsed_ms
            }

        except Exception as e:
            elapsed_ms = int((time.time() - start_ts) * 1000)
            logger.warning(f"Live Government Sync encountered issue: {e}. Falling back to cached historical data.")
            with db_session() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO government_data_sync_logs (
                        sync_timestamp, source_name, records_fetched,
                        records_inserted, records_updated, status, error_message, response_time_ms
                    ) VALUES (?, ?, 0, 0, 0, 'FALLBACK_CACHED', ?, ?)
                """, (now_str, "OGD_API_FALLBACK", str(e), elapsed_ms))

            return {
                "status": "FALLBACK_CACHED",
                "message": f"Live sync unavailable ({str(e)}). Active records are securely served from persistent cache.",
                "error_detail": str(e),
                "is_cached_fallback": True
            }

# --- Query Services for Frontend & API ---

def query_market_prices(
    state: str = None,
    district: str = None,
    market_name: str = None,
    commodity: str = None,
    variety: str = None,
    arrival_date: str = None,
    search: str = None,
    limit: int = 50,
    offset: int = 0
) -> Dict[str, Any]:
    """
    Retrieve and filter government mandi prices from the database.
    Calculates freshness status for every record.
    """
    conditions = []
    params = []

    if state:
        conditions.append("state = ?")
        params.append(state)
    if district:
        conditions.append("district = ?")
        params.append(district)
    if market_name:
        conditions.append("market_name = ?")
        params.append(market_name)
    if commodity:
        conditions.append("LOWER(commodity_name) LIKE ?")
        params.append(f"%{commodity.lower().strip()}%")
    if variety:
        conditions.append("variety = ?")
        params.append(variety)
    if arrival_date:
        conditions.append("arrival_date = ?")
        params.append(arrival_date)
    if search:
        search_term = f"%{search.lower().strip()}%"
        conditions.append("(LOWER(commodity_name) LIKE ? OR LOWER(market_name) LIKE ? OR LOWER(district) LIKE ?)")
        params.extend([search_term, search_term, search_term])

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

    with db_session() as conn:
        cursor = conn.cursor()
        
        # Get count
        cursor.execute(f"SELECT COUNT(*) FROM government_market_price_records{where_clause}", params)
        total = cursor.fetchone()[0]

        # Get rows sorted by arrival_date desc, modal_price desc
        query = f"""
            SELECT id, source_record_id, state, district, market_name, commodity_name,
                   variety, grade, arrival_date, min_price, max_price, modal_price,
                   price_unit, arrivals_in_tonnes, retrieval_timestamp, is_live_synced
            FROM government_market_price_records
            {where_clause}
            ORDER BY arrival_date DESC, modal_price DESC
            LIMIT ? OFFSET ?
        """
        cursor.execute(query, params + [limit, offset])
        rows = cursor.fetchall()

        now = datetime.now()
        records = []
        for r in rows:
            rec = dict(r)
            # Evaluate freshness
            retrieval_dt = None
            if rec.get("retrieval_timestamp"):
                try:
                    retrieval_dt = datetime.fromisoformat(str(rec["retrieval_timestamp"]))
                except Exception:
                    pass

            if rec.get("is_live_synced") and retrieval_dt and (now - retrieval_dt) < timedelta(hours=6):
                rec["freshness_status"] = "Live"
            elif retrieval_dt and (now - retrieval_dt) < timedelta(hours=24):
                rec["freshness_status"] = "Fresh"
            else:
                rec["freshness_status"] = "Stale (Cached)"
            records.append(rec)

        data_freshness = "Live & Fresh" if any(r["freshness_status"] in ("Live", "Fresh") for r in records) else "Historical / Cached"

        return {
            "total": total,
            "data": records,
            "state": state,
            "district": district,
            "market_name": market_name,
            "commodity": commodity,
            "data_freshness": data_freshness,
            "source_attribution": GOV_ATTRIBUTION,
            "source_link": GovMarketPriceAdapter.SOURCE_URL
        }

def get_mandi_trends(commodity: str, market_name: str = None, days: int = 30) -> Dict[str, Any]:
    """
    Retrieve chronological historical price points for 7-day, 30-day, or monthly trends.
    """
    conditions = ["LOWER(commodity_name) LIKE ?"]
    params = [f"%{commodity.lower().strip()}%"]

    if market_name:
        conditions.append("LOWER(market_name) LIKE ?")
        params.append(f"%{market_name.lower().strip()}%")

    where_clause = " WHERE " + " AND ".join(conditions)

    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT arrival_date,
                   AVG(modal_price) as avg_modal,
                   MIN(min_price) as lowest_min,
                   MAX(max_price) as highest_max,
                   SUM(arrivals_in_tonnes) as total_arrivals,
                   COUNT(*) as record_count
            FROM government_market_price_records
            {where_clause}
            GROUP BY arrival_date
            ORDER BY arrival_date ASC
            LIMIT ?
        """, params + [days])
        
        rows = cursor.fetchall()
        trends = []
        for r in rows:
            trends.append({
                "date": r["arrival_date"],
                "modal_price": round(r["avg_modal"], 2),
                "min_price": round(r["lowest_min"], 2),
                "max_price": round(r["highest_max"], 2),
                "arrivals": round(r["total_arrivals"] or 0.0, 1),
                "records": r["record_count"]
            })

        avg_price = round(sum(t["modal_price"] for t in trends) / len(trends), 2) if trends else 0.0
        min_seen = min([t["min_price"] for t in trends], default=0.0)
        max_seen = max([t["max_price"] for t in trends], default=0.0)

        return {
            "commodity": commodity,
            "market_name": market_name or "All Mandis",
            "date_range": f"Past {len(trends)} reporting days",
            "records_count": len(trends),
            "trends": trends,
            "summary": {
                "average_modal_price": avg_price,
                "lowest_min_price": min_seen,
                "highest_max_price": max_seen,
                "data_points": len(trends)
            }
        }

def get_nearby_mandi_comparisons(state: str, district: str, commodity: str) -> List[Dict[str, Any]]:
    """
    Compare prices for a specific commodity across different mandis within the selected district
    or neighboring areas (e.g. Chittoor vs Madanapalle vs Palamaner).
    """
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT market_name, district, state, arrival_date,
                   min_price, max_price, modal_price, arrivals_in_tonnes
            FROM government_market_price_records
            WHERE LOWER(state) = LOWER(?) AND LOWER(commodity_name) LIKE ?
            ORDER BY (district = ?) DESC, arrival_date DESC, modal_price DESC
            LIMIT 10
        """, (state, f"%{commodity.lower().strip()}%", district))
        
        return [dict(r) for r in cursor.fetchall()]

def get_distinct_locations_and_commodities() -> Dict[str, Any]:
    """Retrieve distinct states, districts, mandis, and commodities for filter dropdowns."""
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT state FROM government_market_price_records ORDER BY state ASC")
        states = [r[0] for r in cursor.fetchall()]

        cursor.execute("SELECT DISTINCT state, district FROM government_market_price_records ORDER BY state, district")
        districts_by_state = {}
        for r in cursor.fetchall():
            s, d = r[0], r[1]
            districts_by_state.setdefault(s, []).append(d)

        cursor.execute("SELECT DISTINCT district, market_name FROM government_market_price_records ORDER BY district, market_name")
        markets_by_district = {}
        for r in cursor.fetchall():
            d, m = r[0], r[1]
            markets_by_district.setdefault(d, []).append(m)

        cursor.execute("SELECT DISTINCT commodity_name FROM government_market_price_records ORDER BY commodity_name ASC")
        commodities = [r[0] for r in cursor.fetchall()]

        return {
            "states": states,
            "districts_by_state": districts_by_state,
            "markets_by_district": markets_by_district,
            "commodities": commodities,
            "default_state": DEFAULT_STATE,
            "default_district": DEFAULT_DISTRICT
        }
