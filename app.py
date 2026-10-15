"""
HarvestLink 2.0 - Main FastAPI Application
Connects Indian farmers directly with buyers and integrates official Government of India Agmarknet APMC market prices.
Supports 22 official Indian languages, RTL layouts for Urdu, and rich analytics.
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, Query, Request, Header
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from backend.config import (
    PORT, HOST, DEBUG, SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE,
    GOV_ATTRIBUTION, DEFAULT_STATE, DEFAULT_DISTRICT, STATIC_DIR, TEMPLATES_DIR
)
from backend.models import (
    UserLoginRequest, UserRegisterRequest, LanguagePreferenceUpdate,
    PriceComparisonRequest, ProductCreateRequest, OrderCreateRequest,
    QuotationRequest, ReviewCreateRequest, TranslationReportRequest
)
from backend.services.i18n_service import (
    load_locale, get_completeness_report, record_translation_report, get_translation_reports
)
from backend.services.gov_market_service import (
    GovMarketPriceAdapter, query_market_prices, get_mandi_trends,
    get_nearby_mandi_comparisons, get_distinct_locations_and_commodities
)
from backend.services.price_comparison import (
    compare_farmer_price_with_mandi, normalize_unit_to_kg
)
from backend.services.commodity_service import (
    search_commodities, get_autocomplete_suggestions, get_all_commodities, get_commodity_by_id
)
from backend.services.auth_service import (
    authenticate_user, create_user, create_session_token, get_user_from_token,
    update_user_language, get_demo_users
)
from backend.services.marketplace_service import (
    create_product_listing, get_product_by_id, query_products,
    get_farmer_dashboard_stats, create_order, get_order_by_id,
    update_order_status, create_quotation, create_review
)

app = FastAPI(
    title="HarvestLink 2.0 API",
    description="Multilingual Farmer Marketplace with Official Government Mandi Price Integration",
    version="2.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Assets & Templates
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Singleton Government Market Adapter
gov_adapter = GovMarketPriceAdapter()

def get_current_user_optional(authorization: Optional[str] = Header(None)) -> Optional[Dict[str, Any]]:
    """Helper to extract user from Authorization Bearer token."""
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "").strip()
    return get_user_from_token(token)

# ==============================================================================
# 1. INTERNATIONALIZATION (i18n) - 22 LANGUAGES
# ==============================================================================

@app.get("/api/i18n/languages")
def api_get_languages():
    """Retrieve full catalog of 22 supported Indian languages with native scripts and text directions."""
    languages_list = []
    for code, info in SUPPORTED_LANGUAGES.items():
        languages_list.append({
            "code": code,
            "name": info["name"],
            "native": info["native"],
            "direction": info["direction"],
            "script": info["script"]
        })
    return {"languages": languages_list, "default": DEFAULT_LANGUAGE}

@app.get("/api/i18n/locales/{lang_code}")
def api_get_locale_dictionary(lang_code: str):
    """Retrieve structured translation dictionary for specified language."""
    if lang_code not in SUPPORTED_LANGUAGES:
        lang_code = DEFAULT_LANGUAGE
    data = load_locale(lang_code)
    return {
        "language_code": lang_code,
        "direction": SUPPORTED_LANGUAGES[lang_code]["direction"],
        "translations": data
    }

@app.get("/api/i18n/completeness")
def api_get_completeness_report():
    """Language completeness audit dashboard reporting key coverage across all 22 languages."""
    return get_completeness_report()

@app.post("/api/i18n/report-translation")
def api_report_translation(req: TranslationReportRequest, user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)):
    """Allow users to submit suggested improvements for regional agricultural terminology."""
    reporter_id = user["id"] if user else None
    report_id = record_translation_report(
        language_code=req.language_code,
        translation_key=req.translation_key,
        current_text=req.current_text,
        suggested_correction=req.suggested_correction,
        user_notes=req.user_notes,
        reporter_user_id=reporter_id
    )
    return {"status": "success", "report_id": report_id, "message": "Translation feedback successfully recorded."}

@app.get("/api/i18n/reports")
def api_get_translation_reports(limit: int = 50):
    """Retrieve logged translation feedback items for admin review."""
    return {"reports": get_translation_reports(limit=limit)}

# ==============================================================================
# 2. OFFICIAL GOVERNMENT MARKET-PRICE INTEGRATION
# ==============================================================================

@app.get("/api/market-prices")
def api_get_market_prices(
    state: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    market: Optional[str] = Query(None),
    commodity: Optional[str] = Query(None),
    variety: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """Query and filter official Agmarknet wholesale mandi prices with freshness indicators."""
    return query_market_prices(
        state=state,
        district=district,
        market_name=market,
        commodity=commodity,
        variety=variety,
        arrival_date=date,
        search=search,
        limit=limit,
        offset=offset
    )

@app.get("/api/market-prices/filters")
def api_get_market_filters():
    """Retrieve distinct states, districts, mandis, and commodities for filter dropdowns."""
    return get_distinct_locations_and_commodities()

@app.get("/api/market-prices/trends")
def api_get_market_trends(
    commodity: str = Query(..., description="Crop name e.g., Tomato"),
    market: Optional[str] = Query(None),
    days: int = Query(30, ge=7, le=90)
):
    """Retrieve chronological price trends (7-day, 30-day, monthly) for charts."""
    return get_mandi_trends(commodity=commodity, market_name=market, days=days)

@app.get("/api/market-prices/nearby")
def api_get_nearby_mandis(
    state: str = Query(..., description="State name, e.g. Andhra Pradesh"),
    district: str = Query(..., description="District name, e.g. Chittoor"),
    commodity: str = Query(..., description="Commodity name, e.g. Tomato")
):
    """Compare prices for a specific crop across mandis in the district and region."""
    records = get_nearby_mandi_comparisons(state=state, district=district, commodity=commodity)
    return {
        "state": state,
        "district": district,
        "commodity": commodity,
        "nearby_mandis": records,
        "source_attribution": GOV_ATTRIBUTION
    }

@app.get("/api/market-prices/status")
def api_get_market_status():
    """Check official data provider health, API key status, cached records count, and last sync."""
    return gov_adapter.get_provider_health()

@app.post("/api/market-prices/sync")
def api_trigger_manual_sync(state: Optional[str] = None, district: Optional[str] = None):
    """Trigger data synchronization with the official Open Government Data Platform."""
    res = gov_adapter.sync_data(state=state, district=district)
    return res

# ==============================================================================
# 3. FARMER PRICE-COMPARISON TOOL ("KNOW YOUR MANDI PRICE")
# ==============================================================================

@app.post("/api/market-prices/compare")
def api_compare_farmer_price(req: PriceComparisonRequest):
    """
    Compare a farmer's proposed selling price against official government Agmarknet modal wholesale prices.
    Converts units (quintal, kg, tonne, crate), computes revenue impact and percentage variance.
    """
    # 1. Fetch matching government price record
    query_res = query_market_prices(
        state=req.state,
        district=req.district,
        market_name=req.market_name,
        commodity=req.commodity_id,
        limit=1
    )

    if not query_res["data"]:
        # Broaden search to state level if district mandi is missing
        query_res = query_market_prices(
            state=req.state,
            commodity=req.commodity_id,
            limit=1
        )

    if not query_res["data"]:
        # General national fallback for the commodity
        query_res = query_market_prices(
            commodity=req.commodity_id,
            limit=1
        )

    if not query_res["data"]:
        raise HTTPException(
            status_code=404,
            detail=f"No official government mandi price records found for commodity '{req.commodity_id}'."
        )

    matched_record = query_res["data"][0]

    # 2. Execute mathematical comparison
    try:
        comparison = compare_farmer_price_with_mandi(
            proposed_price=req.proposed_price,
            quantity=req.quantity,
            unit=req.unit,
            mandi_modal_price_per_quintal=matched_record["modal_price"],
            mandi_min_price_per_quintal=matched_record["min_price"],
            mandi_max_price_per_quintal=matched_record["max_price"],
            commodity_name=matched_record["commodity_name"],
            market_name=f"{matched_record['market_name']} ({matched_record['district']}, {matched_record['state']})",
            reporting_date=matched_record["arrival_date"],
            data_freshness=matched_record.get("freshness_status", "Fresh")
        )
        return comparison
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==============================================================================
# 4. SMART SEARCH & LOCALIZED COMMODITY CATALOG
# ==============================================================================

@app.get("/api/commodities")
def api_get_commodities(lang: str = Query("en"), limit: int = 50):
    """Retrieve commodity catalog with localized display names and varieties."""
    return {"commodities": get_all_commodities(lang=lang, limit=limit)}

@app.get("/api/commodities/search")
def api_search_commodities(q: str = Query("", description="Crop search query"), lang: str = Query("en")):
    """Multilingual alias search mapping vernacular terms (tamatar, batata, thakkali) to canonical crops."""
    results = search_commodities(query=q, lang=lang)
    return {"query": q, "language": lang, "results": results}

@app.get("/api/commodities/autocomplete")
def api_autocomplete_commodities(q: str = Query(""), lang: str = Query("en")):
    """Fast prefix suggestions for search inputs."""
    suggestions = get_autocomplete_suggestions(query=q, lang=lang)
    return {"suggestions": suggestions}

@app.get("/api/commodities/{commodity_id}")
def api_get_commodity_details(commodity_id: str, lang: str = Query("en")):
    """Get metadata for specific commodity."""
    comm = get_commodity_by_id(commodity_id, lang=lang)
    if not comm:
        raise HTTPException(status_code=404, detail="Commodity not found.")
    return comm

# ==============================================================================
# 5. DIRECT FARMER-TO-BUYER MARKETPLACE
# ==============================================================================

@app.get("/api/products")
def api_list_products(
    category: Optional[str] = None,
    state: Optional[str] = None,
    district: Optional[str] = None,
    search: Optional[str] = None,
    organic_only: bool = False,
    sort_by: str = "newest",
    farmer_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """Browse active farmer produce listings with location and search filters."""
    products = query_products(
        category=category,
        state=state,
        district=district,
        search=search,
        organic_only=organic_only,
        sort_by=sort_by,
        farmer_id=farmer_id,
        limit=limit,
        offset=offset
    )
    return {"total": len(products), "products": products}

@app.get("/api/products/{product_id}")
def api_get_product(product_id: str):
    """Retrieve full product details including live mandi benchmark."""
    product = get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product listing not found.")
    return product

@app.post("/api/products")
def api_create_product(req: ProductCreateRequest, user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)):
    """Allow farmers to publish new produce listings with mandi price benchmarking."""
    farmer_id = user["id"] if user else "demo_farmer_ramesh"
    try:
        new_prod = create_product_listing(farmer_id, req.dict())
        return {"status": "success", "product": new_prod}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/farmer/stats")
def api_get_farmer_stats(user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)):
    """Farmer dashboard key metrics: active listings, sales, pending orders, quotes."""
    farmer_id = user["id"] if user else "demo_farmer_ramesh"
    return get_farmer_dashboard_stats(farmer_id)

@app.post("/api/orders")
def api_create_order(req: OrderCreateRequest, user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)):
    """Place direct farm order from shopping cart."""
    buyer_id = user["id"] if user else "demo_restaurant_anita"
    try:
        order = create_order(buyer_id, req.dict())
        return {"status": "success", "order": order}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/orders/{order_id}")
def api_get_order(order_id: str):
    """Retrieve order details and delivery status."""
    order = get_order_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    return order

@app.post("/api/orders/{order_id}/status")
def api_update_order_status(order_id: str, status: str = Query(...)):
    """Update order fulfillment status."""
    try:
        update_order_status(order_id, status)
        return {"status": "success", "order_id": order_id, "new_status": status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/quotations")
def api_create_quotation(req: QuotationRequest, user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)):
    """Submit B2B wholesale quotation enquiry."""
    buyer_id = user["id"] if user else "demo_restaurant_anita"
    quote = create_quotation(buyer_id, req.dict())
    return quote

@app.post("/api/reviews")
def api_create_review(req: ReviewCreateRequest, user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)):
    """Submit verified purchase review."""
    buyer_id = user["id"] if user else "demo_restaurant_anita"
    rev_id = create_review(buyer_id, req.dict())
    return {"status": "success", "review_id": rev_id}

# ==============================================================================
# 6. AUTHENTICATION & DEMO ROLES
# ==============================================================================

@app.post("/api/auth/login")
def api_login(req: UserLoginRequest):
    """User login via mobile phone and password."""
    user = authenticate_user(req.phone, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid mobile number or password.")
    token = create_session_token(user)
    return {"status": "success", "token": token, "user": user}

@app.post("/api/auth/register")
def api_register(req: UserRegisterRequest):
    """Register new farmer, buyer, retailer, or wholesaler."""
    try:
        user = create_user(
            phone=req.phone,
            password=req.password,
            full_name=req.full_name,
            role=req.role,
            state=req.state,
            district=req.district,
            preferred_language=req.preferred_language,
            organization_name=req.organization_name,
            pincode=req.pincode
        )
        token = create_session_token(user)
        return {"status": "success", "token": token, "user": user}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/auth/demo-users")
def api_get_demo_users():
    """Retrieve pre-seeded demo accounts representing all 6 marketplace roles."""
    return {"demo_users": get_demo_users()}

@app.post("/api/auth/switch-demo")
def api_switch_demo(user_id: str = Query(...)):
    """Fast switch to a demo persona for demonstration."""
    users = get_demo_users()
    matched = next((u for u in users if u["id"] == user_id), None)
    if not matched:
        raise HTTPException(status_code=404, detail="Demo persona not found.")
    token = create_session_token(matched)
    return {"status": "success", "token": token, "user": matched}

@app.post("/api/user/language")
def api_update_user_language(req: LanguagePreferenceUpdate, user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)):
    """Persist user's selected language preference in their profile."""
    if user:
        update_user_language(user["id"], req.preferred_language)
    return {"status": "success", "language": req.preferred_language}

# ==============================================================================
# 7. WEB APPLICATION ROUTE
# ==============================================================================

@app.get("/", response_class=HTMLResponse)
def serve_index(request: Request):
    """Serve the complete HarvestLink 2.0 Web Application."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "supported_languages": SUPPORTED_LANGUAGES,
            "default_state": DEFAULT_STATE,
            "default_district": DEFAULT_DISTRICT,
            "attribution": GOV_ATTRIBUTION
        }
    )

if __name__ == "__main__":
    import uvicorn
    print(f"Starting HarvestLink 2.0 server on http://{HOST}:{PORT}")
    uvicorn.run("backend.app:app", host=HOST, port=PORT, reload=DEBUG)
