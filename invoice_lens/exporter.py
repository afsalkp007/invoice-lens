"""Export utilities for financial audit results (JSON, Accounting CSV, Markdown reports)."""

import csv
import json
from pathlib import Path
from typing import Union

from invoice_lens.models import AuditResult


class AuditExporter:
    """Exports audited invoices and reconciliation trails into enterprise formats."""

    @staticmethod
    def to_json(result: AuditResult, filepath: Union[str, Path]) -> Path:
        """Export full structured audit result as pretty-printed JSON."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))
        return path

    @staticmethod
    def to_accounting_csv(result: AuditResult, filepath: Union[str, Path]) -> Path:
        """Export line items to CSV formatted for ERP / accounting import."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        doc = result.document

        fieldnames = [
            "vendor_name",
            "invoice_number",
            "date",
            "currency",
            "item_description",
            "category",
            "quantity",
            "unit_price",
            "total_price",
            "audit_status",
            "has_discrepancy",
        ]

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            if doc.line_items:
                for item in doc.line_items:
                    writer.writerow({
                        "vendor_name": doc.vendor_name,
                        "invoice_number": doc.invoice_number or "N/A",
                        "date": doc.date or "N/A",
                        "currency": doc.currency,
                        "item_description": item.description,
                        "category": item.category or "General Expense",
                        "quantity": item.quantity,
                        "unit_price": f"{item.unit_price:.2f}",
                        "total_price": f"{item.total_price:.2f}",
                        "audit_status": result.status.value,
                        "has_discrepancy": not result.is_valid,
                    })
            else:
                # Write header row for doc with no extracted line items
                writer.writerow({
                    "vendor_name": doc.vendor_name,
                    "invoice_number": doc.invoice_number or "N/A",
                    "date": doc.date or "N/A",
                    "currency": doc.currency,
                    "item_description": "Total Document Expense",
                    "category": "Uncategorized",
                    "quantity": 1.0,
                    "unit_price": f"{doc.total_amount:.2f}",
                    "total_price": f"{doc.total_amount:.2f}",
                    "audit_status": result.status.value,
                    "has_discrepancy": not result.is_valid,
                })

        return path

    @staticmethod
    def to_markdown(result: AuditResult) -> str:
        """Generate an executive audit trail report in GitHub Markdown."""
        doc = result.document
        lines = [
            f"# Financial Audit Report: {doc.vendor_name}",
            f"**Audit Status:** `{result.status.value}` | **Valid:** {'✅ YES' if result.is_valid else '❌ NO'} | **Review Needed:** {'⚠️ YES' if result.requires_human_review else '🟢 NO'}",
            "",
            "## Summary",
            f"> {result.summary}",
            "",
            "## Financial Reconciliation Breakdown",
            "| Field | Printed on Document | Reconciled / Calculated | Discrepancy |",
            "| :--- | :--- | :--- | :--- |",
            f"| **Subtotal** | {doc.currency} {doc.subtotal:.2f} | {doc.currency} {result.calculated_subtotal:.2f} | {f'{abs(doc.subtotal - result.calculated_subtotal):.2f}' if abs(doc.subtotal - result.calculated_subtotal) > 0.01 else 'Reconciled'} |",
            f"| **Sales Tax** | {doc.currency} {doc.tax_amount:.2f} | {f'{doc.tax_rate_percent}%' if doc.tax_rate_percent else 'N/A'} | — |",
            f"| **Tip / Gratuity** | {doc.currency} {doc.tip_amount:.2f} | — | — |",
            f"| **Discounts** | -{doc.currency} {doc.discount_amount:.2f} | — | — |",
            f"| **Grand Total** | **{doc.currency} {doc.total_amount:.2f}** | **{doc.currency} {result.calculated_total:.2f}** | **{f'⚠️ {abs(doc.total_amount - result.calculated_total):.2f}' if abs(doc.total_amount - result.calculated_total) > 0.01 else '✅ Perfect Match'}** |",
            "",
        ]

        if result.discrepancies:
            lines.extend([
                "## Flagged Discrepancies & Violations",
                "| Severity | Rule ID | Field | Message | Expected | Actual |",
                "| :--- | :--- | :--- | :--- | :--- | :--- |",
            ])
            for d in result.discrepancies:
                sev_icon = "🔴" if d.severity.value == "ERROR" else ("🟡" if d.severity.value == "WARNING" else "ℹ️")
                lines.append(
                    f"| {sev_icon} `{d.severity.value}` | `{d.rule_name}` | `{d.field}` | {d.message} | `{d.expected_value or 'N/A'}` | `{d.actual_value or 'N/A'}` |"
                )
            lines.append("")

        lines.extend([
            "## Line Items",
            "| # | Description | Category | Qty | Unit Price | Total Price | VLM Confidence |",
            "| :-: | :--- | :--- | :-: | :-: | :-: | :-: |",
        ])
        for i, item in enumerate(doc.line_items, 1):
            lines.append(
                f"| {i} | {item.description} | {item.category or 'General'} | {item.quantity} | {doc.currency} {item.unit_price:.2f} | {doc.currency} {item.total_price:.2f} | `{item.confidence.value}` |"
            )

        return "\n".join(lines)
