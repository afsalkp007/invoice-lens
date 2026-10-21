"""Unit tests for multimodal document extractors and mock fallbacks."""

import pytest
from invoice_lens.extractor import MockExtractor, get_extractor
from invoice_lens.models import DocumentType


def test_mock_extractor_clean_receipt():
    extractor = MockExtractor(mode="clean_receipt")
    doc = extractor.extract(b"dummy_bytes")

    assert doc.document_type == DocumentType.RECEIPT
    assert doc.vendor_name == "Artisan Roast & Bakery"
    assert doc.total_amount == 40.10
    assert len(doc.line_items) == 3


def test_mock_extractor_saas_invoice():
    extractor = MockExtractor(mode="saas_invoice")
    doc = extractor.extract(b"dummy_bytes")

    assert doc.document_type == DocumentType.INVOICE
    assert doc.vendor_name == "Datadog Infrastructure Inc."
    assert doc.discount_amount == 50.00
    assert doc.total_amount == 491.25


def test_mock_extractor_discrepancy():
    extractor = MockExtractor(mode="math_discrepancy")
    doc = extractor.extract(b"dummy_bytes")

    assert doc.vendor_name == "Apex Logistics & Freight"
    assert doc.total_amount == 382.20
    assert doc.subtotal == 340.00


def test_get_extractor_fallback_when_no_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    extractor = get_extractor(provider="gemini")
    assert isinstance(extractor, MockExtractor)
