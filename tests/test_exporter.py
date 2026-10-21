"""Unit tests for audit exporter utilities (JSON, CSV, Markdown)."""

import json
import csv
import pytest
from invoice_lens.models import ExtractedDocument, LineItem, AuditResult, ReconciliationStatus
from invoice_lens.reconciler import AuditReconciler
from invoice_lens.exporter import AuditExporter


@pytest.fixture
def sample_audit_result():
    doc = ExtractedDocument(
        vendor_name="Acme Corp",
        invoice_number="INV-001",
        date="2026-10-10",
        currency="USD",
        subtotal=100.0,
        tax_amount=10.0,
        total_amount=110.0,
        line_items=[
            LineItem(description="Widget A", quantity=2.0, unit_price=50.0, total_price=100.0)
        ],
    )
    reconciler = AuditReconciler()
    return reconciler.audit(doc)


def test_export_to_json(tmp_path, sample_audit_result):
    json_path = tmp_path / "test_audit.json"
    out = AuditExporter.to_json(sample_audit_result, json_path)
    assert out.exists()

    with open(out, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["status"] == "PASSED"
    assert data["document"]["vendor_name"] == "Acme Corp"


def test_export_to_csv(tmp_path, sample_audit_result):
    csv_path = tmp_path / "test_audit.csv"
    out = AuditExporter.to_accounting_csv(sample_audit_result, csv_path)
    assert out.exists()

    with open(out, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["vendor_name"] == "Acme Corp"
    assert rows[0]["item_description"] == "Widget A"
    assert rows[0]["total_price"] == "100.00"


def test_export_to_markdown(sample_audit_result):
    md = AuditExporter.to_markdown(sample_audit_result)
    assert "# Financial Audit Report: Acme Corp" in md
    assert "Grand Total" in md
    assert "Widget A" in md
