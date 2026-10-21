"""Unit tests for Pydantic data schemas in InvoiceLens."""

import pytest
from invoice_lens.models import (
    LineItem,
    ExtractedDocument,
    ConfidenceLevel,
    DocumentType,
    Severity,
    Discrepancy,
    AuditResult,
    ReconciliationStatus,
)


def test_line_item_rounding_and_defaults():
    item = LineItem(
        description="Espresso Shot",
        quantity=2,
        unit_price=3.5011,
        total_price=7.0022,
    )
    assert item.unit_price == 3.50
    assert item.total_price == 7.00
    assert item.confidence == ConfidenceLevel.HIGH
    assert item.category is None


def test_extracted_document_financial_cleaning():
    doc = ExtractedDocument(
        vendor_name="Acme Supplies",
        subtotal="100.555",
        tax_amount="8.044",
        total_amount="108.60",
    )
    assert doc.subtotal == 100.56
    assert doc.tax_amount == 8.04
    assert doc.total_amount == 108.60
    assert doc.currency == "USD"
    assert doc.document_type == DocumentType.INVOICE


def test_audit_result_structure():
    doc = ExtractedDocument(vendor_name="Test Store", total_amount=50.0)
    result = AuditResult(
        is_valid=True,
        status=ReconciliationStatus.PASSED,
        calculated_subtotal=50.0,
        calculated_total=50.0,
        discrepancies=[],
        document=doc,
        summary="Audit passed cleanly.",
    )
    assert result.is_valid is True
    assert result.requires_human_review is False
    assert len(result.discrepancies) == 0
