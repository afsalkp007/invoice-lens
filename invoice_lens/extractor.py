"""Multimodal document extraction engine.

Extracts structured financial line items, metadata, and totals from document
images (receipts, invoices, bills) using Vision-Language Models (Gemini / OpenAI)
with a zero-crash offline mock fallback for CI/CD and testing.
"""

import os
import json
import base64
import logging
import warnings
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

warnings.filterwarnings("ignore")

import requests
from dotenv import load_dotenv

from invoice_lens.models import ExtractedDocument, LineItem, DocumentType, ConfidenceLevel

load_dotenv()
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert AI Document Auditor and Financial OCR specialist.
Analyze the provided receipt or invoice image with extreme optical accuracy.
Extract all printed financial details into a strict JSON object matching this schema:
{
  "document_type": "invoice" | "receipt" | "bill" | "unknown",
  "vendor_name": "string",
  "vendor_tax_id": "string or null",
  "invoice_number": "string or null",
  "date": "YYYY-MM-DD or string or null",
  "due_date": "YYYY-MM-DD or string or null",
  "currency": "USD" | "EUR" | "GBP" etc.,
  "subtotal": float,
  "tax_amount": float,
  "tax_rate_percent": float or null,
  "tip_amount": float,
  "discount_amount": float,
  "total_amount": float,
  "payment_method": "string or null",
  "line_items": [
    {
      "description": "string",
      "quantity": float,
      "unit_price": float,
      "total_price": float,
      "category": "string or null",
      "confidence": "HIGH" | "MEDIUM" | "LOW"
    }
  ],
  "raw_summary": "one-sentence description of the transaction",
  "extraction_confidence": float between 0.0 and 1.0
}

CRITICAL RULES:
1. Extract exact numerical amounts as printed on the document. Do NOT invent or alter prices.
2. If subtotal is not printed, sum the line item prices.
3. If currency is not explicitly printed, default to "USD".
4. Ensure your response is strictly valid raw JSON without any markdown formatting or commentary.
"""


class BaseExtractor(ABC):
    """Abstract Base Class for Multimodal Document Extractors."""

    @abstractmethod
    def extract(self, image_bytes: bytes, mime_type: str = "image/png", hint_filename: str = "") -> ExtractedDocument:
        """Extract structured financial data from an image file."""
        pass


class GeminiExtractor(BaseExtractor):
    """Google Gemini 2.5/1.5 Flash Multimodal Document Extractor."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.5-flash",
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Please provide it in .env or switch to mock mode."
            )

    def extract(self, image_bytes: bytes, mime_type: str = "image/png", hint_filename: str = "") -> ExtractedDocument:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": SYSTEM_PROMPT + "\nExtract the financial data from this document image:"},
                        {
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": b64_image,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }

        response = requests.post(url, json=payload, timeout=30)
        if response.status_code != 200:
            raise RuntimeError(
                f"Gemini API request failed ({response.status_code}): {response.text}"
            )

        data = response.json()
        try:
            candidates = data.get("candidates", [])
            text_content = candidates[0]["content"]["parts"][0]["text"]
            # Clean markdown codeblocks if returned
            text_content = text_content.strip()
            if text_content.startswith("```json"):
                text_content = text_content[7:]
            if text_content.startswith("```"):
                text_content = text_content[3:]
            if text_content.endswith("```"):
                text_content = text_content[:-3]
            raw_json = json.loads(text_content.strip())
            return ExtractedDocument.model_validate(raw_json)
        except Exception as e:
            logger.error("Failed to parse Gemini VLM response: %s", e)
            raise ValueError(f"Could not parse valid document JSON from Gemini response: {e}")


class MockExtractor(BaseExtractor):
    """High-fidelity Mock Extractor for offline testing, demoing, and CI/CD."""

    def __init__(self, mode: str = "clean_receipt"):
        """
        Args:
            mode: "clean_receipt", "saas_invoice", "math_discrepancy", or "missing_fields"
        """
        self.mode = mode

    def extract(self, image_bytes: bytes, mime_type: str = "image/png", hint_filename: str = "") -> ExtractedDocument:
        # Smart detection based on filename or hint
        mode = self.mode
        lower_hint = hint_filename.lower()
        if "discrepancy" in lower_hint:
            mode = "math_discrepancy"
        elif "saas" in lower_hint or "datadog" in lower_hint:
            mode = "saas_invoice"
        elif "missing" in lower_hint or "faded" in lower_hint:
            mode = "missing_fields"
        elif "cafe" in lower_hint or "receipt" in lower_hint:
            mode = "clean_receipt"

        if mode == "saas_invoice":
            return ExtractedDocument(
                document_type=DocumentType.INVOICE,
                vendor_name="Datadog Infrastructure Inc.",
                vendor_tax_id="US-84920194",
                invoice_number="INV-2026-9041",
                date="2026-10-14",
                due_date="2026-11-14",
                currency="USD",
                subtotal=500.00,
                tax_amount=41.25,
                tax_rate_percent=8.25,
                tip_amount=0.0,
                discount_amount=50.00,
                total_amount=491.25,
                payment_method="ACH Auto-Debit",
                line_items=[
                    LineItem(
                        description="Pro Host Monitoring (20 hosts)",
                        quantity=20.0,
                        unit_price=15.00,
                        total_price=300.00,
                        category="Cloud Infrastructure",
                        confidence=ConfidenceLevel.HIGH,
                    ),
                    LineItem(
                        description="APM & Distributed Tracing",
                        quantity=1.0,
                        unit_price=200.00,
                        total_price=200.00,
                        category="Observability",
                        confidence=ConfidenceLevel.HIGH,
                    ),
                ],
                raw_summary="Monthly cloud infrastructure observability bill with volume discount applied.",
                extraction_confidence=0.98,
            )

        elif mode == "math_discrepancy":
            # Realistic discrepancy: Vendor billing error ($15.00 inflated total)
            return ExtractedDocument(
                document_type=DocumentType.INVOICE,
                vendor_name="Apex Logistics & Freight",
                vendor_tax_id="US-12940210",
                invoice_number="APX-88219",
                date="2026-10-12",
                due_date="2026-10-26",
                currency="USD",
                subtotal=340.00,
                tax_amount=27.20,
                tax_rate_percent=8.0,
                tip_amount=0.0,
                discount_amount=0.0,
                total_amount=382.20,  # Intentional discrepancy! Correct sum is 367.20. Overcharge by $15.00
                payment_method="Credit Card ****4921",
                line_items=[
                    LineItem(
                        description="Expedited Freight Delivery",
                        quantity=2.0,
                        unit_price=120.00,
                        total_price=240.00,
                        category="Shipping & Logistics",
                        confidence=ConfidenceLevel.HIGH,
                    ),
                    LineItem(
                        description="Pallet Wrapping & Securing",
                        quantity=1.0,
                        unit_price=100.00,
                        total_price=100.00,
                        category="Packaging",
                        confidence=ConfidenceLevel.HIGH,
                    ),
                ],
                raw_summary="Freight delivery invoice with $15.00 arithmetic billing overcharge discrepancy.",
                extraction_confidence=0.92,
            )

        elif mode == "missing_fields":
            return ExtractedDocument(
                document_type=DocumentType.RECEIPT,
                vendor_name="Unknown Vendor",
                invoice_number=None,
                date=None,
                currency="USD",
                subtotal=28.50,
                tax_amount=2.50,
                total_amount=31.00,
                payment_method="Cash",
                line_items=[
                    LineItem(
                        description="Office Supplies Misc",
                        quantity=1.0,
                        unit_price=28.50,
                        total_price=28.50,
                        category="Office Supplies",
                        confidence=ConfidenceLevel.LOW,
                    )
                ],
                raw_summary="Faded thermal receipt missing vendor header and transaction date.",
                extraction_confidence=0.62,
            )

        else:
            # Standard Clean Restaurant / Cafe Receipt
            return ExtractedDocument(
                document_type=DocumentType.RECEIPT,
                vendor_name="Artisan Roast & Bakery",
                vendor_tax_id="VAT-GB992019",
                invoice_number="REC-4410",
                date="2026-10-18",
                currency="USD",
                subtotal=32.50,
                tax_amount=2.60,
                tax_rate_percent=8.0,
                tip_amount=5.00,
                discount_amount=0.0,
                total_amount=40.10,
                payment_method="Apple Pay (Mastercard *8812)",
                line_items=[
                    LineItem(
                        description="Oat Milk Flat White",
                        quantity=2.0,
                        unit_price=5.50,
                        total_price=11.00,
                        category="Meals & Entertainment",
                        confidence=ConfidenceLevel.HIGH,
                    ),
                    LineItem(
                        description="Avocado Sourdough Toast",
                        quantity=1.0,
                        unit_price=14.50,
                        total_price=14.50,
                        category="Meals & Entertainment",
                        confidence=ConfidenceLevel.HIGH,
                    ),
                    LineItem(
                        description="Almond Croissant",
                        quantity=1.0,
                        unit_price=7.00,
                        total_price=7.00,
                        category="Meals & Entertainment",
                        confidence=ConfidenceLevel.HIGH,
                    ),
                ],
                raw_summary="Breakfast meeting receipt with exact math and tip reconciliation.",
                extraction_confidence=0.96,
            )


def get_extractor(provider: Optional[str] = None, mode: str = "clean_receipt") -> BaseExtractor:
    """Factory function to instantiate the configured VLM extractor."""
    active_provider = provider or os.getenv("VLM_PROVIDER", "gemini").lower()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

    if active_provider == "gemini":
        if gemini_key and not gemini_key.startswith("your_"):
            try:
                return GeminiExtractor(api_key=gemini_key)
            except Exception as e:
                logger.warning(
                    "Gemini extractor initialization failed (%s). Falling back to MockExtractor.",
                    e,
                )
                return MockExtractor(mode=mode)
        else:
            logger.info("No active GEMINI_API_KEY detected. Using MockExtractor (offline mode).")
            return MockExtractor(mode=mode)

    return MockExtractor(mode=mode)
