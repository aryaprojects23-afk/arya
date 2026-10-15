"""
HarvestLink 2.0 - Pydantic Data Models & Schemas
Enforces strict type validation, request/response serialization, and business rules.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import date, datetime

# --- Authentication & User Models ---
class UserLoginRequest(BaseModel):
    phone: str = Field(..., description="10-digit Indian mobile number")
    password: str

class UserRegisterRequest(BaseModel):
    phone: str = Field(..., description="10-digit Indian mobile number")
    password: str
    full_name: str
    role: str = Field(..., description="farmer, consumer, restaurant, retailer, wholesaler, admin")
    state: str
    district: str
    preferred_language: str = "en"
    organization_name: Optional[str] = None
    pincode: Optional[str] = None

class LanguagePreferenceUpdate(BaseModel):
    preferred_language: str = Field(..., description="ISO language code, e.g., 'te', 'hi', 'en'")

class UserResponse(BaseModel):
    id: str
    phone: str
    email: Optional[str] = None
    full_name: str
    role: str
    is_verified: bool
    state: Optional[str] = None
    district: Optional[str] = None
    preferred_language: str = "en"

# --- Government Mandi Price Models ---
class MandiPriceRecord(BaseModel):
    id: Optional[int] = None
    source_record_id: Optional[str] = None
    state: str
    district: str
    market_name: str
    commodity_name: str
    variety: str = "Other"
    grade: str = "FAQ"
    arrival_date: str
    min_price: float = Field(..., description="Minimum wholesale price in INR per quintal")
    max_price: float = Field(..., description="Maximum wholesale price in INR per quintal")
    modal_price: float = Field(..., description="Modal wholesale price in INR per quintal")
    price_unit: str = "Rs/Quintal"
    arrivals_in_tonnes: float = 0.0
    retrieval_timestamp: Optional[str] = None
    is_live_synced: bool = False
    freshness_status: Optional[str] = "Fresh" # 'Live', 'Fresh', 'Stale'

class MandiPricesResponse(BaseModel):
    total: int
    data: List[MandiPriceRecord]
    state: Optional[str] = None
    district: Optional[str] = None
    market_name: Optional[str] = None
    commodity: Optional[str] = None
    data_freshness: str
    last_synced_at: Optional[str] = None
    source_attribution: str
    source_link: str

class MandiTrendPoint(BaseModel):
    date: str
    modal_price: float
    min_price: float
    max_price: float
    arrivals: float

class MandiTrendResponse(BaseModel):
    commodity: str
    market_name: str
    date_range: str
    records_count: int
    trends: List[MandiTrendPoint]
    summary: Dict[str, Any]

class ProviderHealthResponse(BaseModel):
    provider_id: str
    provider_name: str
    is_healthy: bool
    last_checked_at: Optional[str] = None
    last_success_at: Optional[str] = None
    latency_ms: Optional[int] = None
    sync_interval_hours: int
    total_records_cached: int
    last_sync_status: str
    source_attribution: str

# --- "Know Your Mandi Price" Models ---
class PriceComparisonRequest(BaseModel):
    commodity_id: str
    variety: Optional[str] = "Standard"
    grade: Optional[str] = "Grade A"
    state: str
    district: str
    market_name: Optional[str] = None
    proposed_price: float = Field(..., gt=0, description="Farmer proposed selling price")
    quantity: float = Field(..., gt=0, description="Proposed quantity")
    unit: str = Field(default="kg", description="kg, quintal, tonne, crate")

class PriceComparisonResponse(BaseModel):
    commodity_name: str
    input_unit: str
    normalized_quantity_kg: float
    farmer_proposed_price_per_input_unit: float
    farmer_proposed_price_per_kg: float
    government_mandi_name: str
    government_reporting_date: str
    mandi_modal_price_per_quintal: float
    mandi_modal_price_per_kg: float
    mandi_min_price_per_kg: float
    mandi_max_price_per_kg: float
    price_difference_per_kg: float
    percentage_difference: float
    farmer_gross_sale_value: float
    mandi_equivalent_gross_value: float
    gross_variance_value: float
    comparison_sentiment: str # 'above_modal', 'at_modal', 'below_modal'
    status_label: str
    formula_explanation: str
    is_msp_warning: str
    source_attribution: str
    data_freshness: str

# --- Commodity & Smart Search Models ---
class CommoditySummary(BaseModel):
    id: str
    canonical_name: str
    localized_name: str
    category: str
    standard_unit: str
    image_url: Optional[str] = None
    varieties: List[str] = []

class AutocompleteResult(BaseModel):
    term: str
    commodity_id: str
    canonical_name: str
    matched_locale: Optional[str] = None

# --- Marketplace Products, Orders & Quotations ---
class ProductCreateRequest(BaseModel):
    commodity_id: str
    variety: str
    grade: str = "Grade A"
    title: str
    description: Optional[str] = ""
    price_per_unit: float
    unit: str = "kg"
    available_quantity: float
    minimum_order_qty: float = 1.0
    bulk_discount_percentage: float = 0.0
    bulk_threshold_qty: float = 0.0
    harvest_date: Optional[str] = None
    organic_certified: bool = False
    location_state: str
    location_district: str
    image_url: Optional[str] = None

class ProductResponse(BaseModel):
    id: str
    farmer_id: str
    farmer_name: str
    farmer_phone: Optional[str] = None
    commodity_id: str
    commodity_name: str
    variety: str
    grade: str
    title: str
    description: Optional[str] = None
    price_per_unit: float
    unit: str
    available_quantity: float
    minimum_order_qty: float
    bulk_discount_percentage: float
    bulk_threshold_qty: float
    harvest_date: Optional[str] = None
    organic_certified: bool
    location_state: str
    location_district: str
    image_url: Optional[str] = None
    status: str
    created_at: str
    mandi_reference_price: Optional[float] = None

class CartItem(BaseModel):
    product_id: str
    quantity: float

class OrderCreateRequest(BaseModel):
    items: List[CartItem]
    delivery_address: str
    delivery_pincode: str
    delivery_state: str
    delivery_district: str
    contact_phone: str
    payment_method: str = "cash_on_delivery"

class OrderItemResponse(BaseModel):
    product_id: str
    product_title: str
    farmer_name: str
    quantity: float
    unit: str
    unit_price: float
    total_price: float
    item_status: str

class OrderResponse(BaseModel):
    id: str
    order_number: str
    total_amount: float
    currency: str
    order_status: str
    delivery_address: str
    delivery_pincode: str
    delivery_state: str
    delivery_district: str
    contact_phone: str
    payment_status: str
    payment_method: str
    created_at: str
    items: List[OrderItemResponse]

class QuotationRequest(BaseModel):
    farmer_id: str
    commodity_id: str
    requested_quantity: float
    unit: str = "kg"
    target_price_per_unit: Optional[float] = None
    buyer_notes: Optional[str] = None

class QuotationResponse(BaseModel):
    id: str
    buyer_name: str
    farmer_name: str
    commodity_name: str
    requested_quantity: float
    unit: str
    target_price_per_unit: Optional[float] = None
    offered_price_per_unit: Optional[float] = None
    status: str
    buyer_notes: Optional[str] = None
    farmer_notes: Optional[str] = None
    created_at: str

# --- Review & Translation Reports ---
class ReviewCreateRequest(BaseModel):
    order_id: str
    product_id: str
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = ""

class TranslationReportRequest(BaseModel):
    language_code: str
    translation_key: str
    current_text: str
    suggested_correction: str
    user_notes: Optional[str] = None
