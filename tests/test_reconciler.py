"""Unit tests for the deterministic financial reconciliation and audit rules engine."""

import pytest
from datetime import date, timedelta
from invoice_lens.models import (
    ExtractedDocument,
    LineItem,
    Severity,
    ReconciliationStatus,
    ConfidenceLevel,
)
from invoice_lens.reconciler import AuditReconciler


@pytest.fixture
def clean_receipt():
    return ExtractedDocument(
        vendor_name="Artisan Roast",
        invoice_number="REC-101",
        date="2026-10-18",
        currency="USD",
        subtotal=20.00,
        tax_amount=1.60,
        tax_rate_percent=8.0,
        tip_amount=3.00,
        discount_amount=0.0,
        total_amount=24.60,
        line_items=[
            LineItem(description="Coffee", quantity=2.0, unit_price=5.00, total_price=10.00),
            LineItem(description="Sandwich", quantity=1.0, unit_price=10.00, total_price=10.00),
        ],
        extraction_confidence=0.95,
    )


def test_reconciler_clean_receipt_passes(clean_receipt):
    reconciler = AuditReconciler()
    result = reconciler.audit(clean_receipt)

    assert result.is_valid is True
    assert result.status == ReconciliationStatus.PASSED
    assert result.calculated_subtotal == 20.00
    assert result.calculated_total == 24.60
    assert len(result.discrepancies) == 0
    assert result.requires_human_review is False


def test_reconciler_total_mismatch_flags_error(clean_receipt):
    # Alter total to introduce an arithmetic error
    clean_receipt.total_amount = 35.00

    reconciler = AuditReconciler()
    result = reconciler.audit(clean_receipt)

    assert result.is_valid is False
    assert result.status == ReconciliationStatus.FAILED
    assert result.requires_human_review is True

    error_discrepancies = [d for d in result.discrepancies if d.severity == Severity.ERROR]
    assert len(error_discrepancies) == 1
    assert error_discrepancies[0].rule_name == "TOTAL_RECONCILIATION"
    assert "35.00" in error_discrepancies[0].actual_value


def test_reconciler_subtotal_mismatch_flags_error(clean_receipt):
    # Alter subtotal to not match line items
    clean_receipt.subtotal = 50.00

    reconciler = AuditReconciler()
    result = reconciler.audit(clean_receipt)

    sub_errors = [d for d in result.discrepancies if d.rule_name == "SUBTOTAL_MISMATCH"]
    assert len(sub_errors) == 1
    assert sub_errors[0].severity == Severity.ERROR


def test_reconciler_line_item_math_warning():
    doc = ExtractedDocument(
        vendor_name="Test Store",
        total_amount=10.00,
        subtotal=10.00,
        line_items=[
            LineItem(description="Item A", quantity=3.0, unit_price=2.00, total_price=10.00) # 3 * 2 != 10
        ],
    )
    reconciler = AuditReconciler()
    result = reconciler.audit(doc)

    item_warnings = [d for d in result.discrepancies if d.rule_name == "LINE_ITEM_UNIT_MATH"]
    assert len(item_warnings) == 1
    assert item_warnings[0].severity == Severity.WARNING


def test_reconciler_missing_vendor_warning():
    doc = ExtractedDocument(
        vendor_name="Unknown Vendor",
        total_amount=25.00,
        subtotal=25.00,
    )
    reconciler = AuditReconciler()
    result = reconciler.audit(doc)

    vendor_warnings = [d for d in result.discrepancies if d.rule_name == "MISSING_VENDOR"]
    assert len(vendor_warnings) == 1
    assert result.status == ReconciliationStatus.FLAGGED_FOR_REVIEW


def test_reconciler_future_date_warning():
    future_date = (date.today() + timedelta(days=10)).isoformat()
    doc = ExtractedDocument(
        vendor_name="Future Mart",
        date=future_date,
        total_amount=15.00,
        subtotal=15.00,
    )
    reconciler = AuditReconciler()
    result = reconciler.audit(doc)

    date_warnings = [d for d in result.discrepancies if d.rule_name == "FUTURE_DATE_ANOMALY"]
    assert len(date_warnings) == 1


def test_reconciler_low_confidence_warning():
    doc = ExtractedDocument(
        vendor_name="Faded Receipt",
        total_amount=10.00,
        subtotal=10.00,
        extraction_confidence=0.55,
    )
    reconciler = AuditReconciler()
    result = reconciler.audit(doc)

    conf_warnings = [d for d in result.discrepancies if d.rule_name == "LOW_EXTRACTION_CONFIDENCE"]
    assert len(conf_warnings) == 1
