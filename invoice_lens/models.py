"""Pydantic data models for multimodal document extraction and audit reconciliation."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class DocumentType(str, Enum):
    INVOICE = "invoice"
    RECEIPT = "receipt"
    BILL = "bill"
    UNKNOWN = "unknown"


class ReconciliationStatus(str, Enum):
    PASSED = "PASSED"
    FLAGGED_FOR_REVIEW = "FLAGGED_FOR_REVIEW"
    FAILED = "FAILED"


class LineItem(BaseModel):
    """An individual line item on a receipt or invoice."""
    description: str = Field(..., description="Description or product name")
    quantity: float = Field(default=1.0, ge=0, description="Quantity purchased")
    unit_price: float = Field(default=0.0, ge=0, description="Unit price per item")
    total_price: float = Field(..., ge=0, description="Total price for this line item")
    category: Optional[str] = Field(default=None, description="Inferred accounting category")
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.HIGH)

    @field_validator("quantity", "unit_price", "total_price", mode="before")
    @classmethod
    def round_floats(cls, v):
        if v is None:
            return 0.0
        try:
            return round(float(v), 2)
        except (ValueError, TypeError):
            return 0.0


class ExtractedDocument(BaseModel):
    """Extracted financial document payload from Vision-Language Model."""
    document_type: DocumentType = Field(default=DocumentType.INVOICE)
    vendor_name: str = Field(default="Unknown Vendor", description="Name of company or seller")
    vendor_tax_id: Optional[str] = Field(default=None, description="VAT/Tax ID/EIN if present")
    invoice_number: Optional[str] = Field(default=None, description="Invoice or receipt reference number")
    date: Optional[str] = Field(default=None, description="Date in YYYY-MM-DD or raw format")
    due_date: Optional[str] = Field(default=None, description="Payment due date if applicable")
    currency: str = Field(default="USD", description="Currency code (USD, EUR, GBP, etc.)")
    
    subtotal: float = Field(default=0.0, ge=0, description="Sum of line items before tax/discounts")
    tax_amount: float = Field(default=0.0, ge=0, description="Extracted sales tax / VAT")
    tax_rate_percent: Optional[float] = Field(default=None, description="Extracted tax rate in %")
    tip_amount: float = Field(default=0.0, ge=0, description="Tip or gratuity")
    discount_amount: float = Field(default=0.0, ge=0, description="Discounts applied")
    total_amount: float = Field(..., ge=0, description="Grand total as printed on the document")
    
    payment_method: Optional[str] = Field(default=None, description="Payment method used (e.g. Visa, Cash)")
    line_items: List[LineItem] = Field(default_factory=list, description="List of individual items")
    raw_summary: Optional[str] = Field(default=None, description="Brief LLM-generated summary of the purchase")
    extraction_confidence: float = Field(default=0.90, ge=0.0, le=1.0)

    @field_validator("subtotal", "tax_amount", "tip_amount", "discount_amount", "total_amount", mode="before")
    @classmethod
    def clean_financial_amounts(cls, v):
        if v is None:
            return 0.0
        try:
            return round(float(v), 2)
        except (ValueError, TypeError):
            return 0.0


class Discrepancy(BaseModel):
    """A flagged audit violation, arithmetic mismatch, or compliance warning."""
    rule_name: str = Field(..., description="Machine-readable rule ID")
    severity: Severity = Field(..., description="ERROR, WARNING, or INFO")
    field: str = Field(..., description="Primary field impacted")
    message: str = Field(..., description="Human-readable explanation of discrepancy")
    expected_value: Optional[str] = Field(default=None, description="What the rule calculated")
    actual_value: Optional[str] = Field(default=None, description="What the document claimed")


class AuditResult(BaseModel):
    """Complete audit verdict and reconciliation report."""
    is_valid: bool = Field(..., description="True if document has no critical ERROR discrepancies")
    status: ReconciliationStatus = Field(..., description="PASSED, FLAGGED_FOR_REVIEW, or FAILED")
    calculated_subtotal: float = Field(..., description="Sum of line items calculated by rule engine")
    calculated_total: float = Field(..., description="Calculated subtotal + tax + tip - discount")
    discrepancies: List[Discrepancy] = Field(default_factory=list)
    requires_human_review: bool = Field(default=False)
    document: ExtractedDocument
    summary: str = Field(..., description="Executive audit conclusion")
