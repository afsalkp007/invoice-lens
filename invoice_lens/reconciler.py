"""Deterministic financial reconciliation and audit rules engine.

Enforces strict accounting invariants, cross-field arithmetic checks,
and enterprise compliance rules on extracted document payloads.
"""

from datetime import datetime, date
from typing import List, Optional, Tuple
from invoice_lens.models import (
    ExtractedDocument,
    AuditResult,
    Discrepancy,
    Severity,
    ReconciliationStatus,
)


class AuditReconciler:
    """Deterministic financial reconciliation engine for receipts and invoices."""

    def __init__(self, tolerance: float = 0.02):
        """
        Args:
            tolerance: Permissible float discrepancy in currency units (default: $0.02).
        """
        self.tolerance = tolerance

    def audit(self, doc: ExtractedDocument) -> AuditResult:
        """Run all deterministic compliance and arithmetic checks on the extracted document."""
        discrepancies: List[Discrepancy] = []

        # 1. Line Item Unit Math
        self._check_line_item_math(doc, discrepancies)

        # 2. Subtotal Sum Verification
        calculated_subtotal = self._check_subtotal(doc, discrepancies)

        # 3. Tax Consistency Check
        self._check_tax(doc, calculated_subtotal, discrepancies)

        # 4. Grand Total Reconciliation
        calculated_total = self._check_total(doc, calculated_subtotal, discrepancies)

        # 5. Critical Fields & Metadata Compliance
        self._check_critical_fields(doc, discrepancies)

        # 6. Date Sanity Check
        self._check_date_sanity(doc, discrepancies)

        # 7. Model Confidence Guardrail
        self._check_confidence(doc, discrepancies)

        # Determine overall verdict
        has_errors = any(d.severity == Severity.ERROR for d in discrepancies)
        has_warnings = any(d.severity == Severity.WARNING for d in discrepancies)

        if has_errors:
            status = ReconciliationStatus.FAILED
            is_valid = False
            requires_human_review = True
            summary = (
                f"AUDIT FAILED: Found {len([d for d in discrepancies if d.severity == Severity.ERROR])} "
                f"critical financial discrepancy(s). Manual human-in-the-loop review required."
            )
        elif has_warnings:
            status = ReconciliationStatus.FLAGGED_FOR_REVIEW
            is_valid = True
            requires_human_review = True
            summary = (
                f"FLAGGED FOR REVIEW: Financial math reconciled, but {len(discrepancies)} "
                f"compliance or metadata warning(s) detected."
            )
        else:
            status = ReconciliationStatus.PASSED
            is_valid = True
            requires_human_review = False
            summary = "AUDIT PASSED: All line items, tax, and totals mathematically reconciled perfectly."

        return AuditResult(
            is_valid=is_valid,
            status=status,
            calculated_subtotal=round(calculated_subtotal, 2),
            calculated_total=round(calculated_total, 2),
            discrepancies=discrepancies,
            requires_human_review=requires_human_review,
            document=doc,
            summary=summary,
        )

    def _check_line_item_math(self, doc: ExtractedDocument, discrepancies: List[Discrepancy]) -> None:
        for i, item in enumerate(doc.line_items):
            if item.quantity > 0 and item.unit_price > 0:
                expected_total = round(item.quantity * item.unit_price, 2)
                diff = abs(expected_total - item.total_price)
                if diff > self.tolerance:
                    discrepancies.append(
                        Discrepancy(
                            rule_name="LINE_ITEM_UNIT_MATH",
                            severity=Severity.WARNING,
                            field=f"line_items[{i}].total_price",
                            message=(
                                f"Item '{item.description}' arithmetic mismatch: "
                                f"{item.quantity} x {doc.currency} {item.unit_price:.2f} = "
                                f"{doc.currency} {expected_total:.2f}, but got {doc.currency} {item.total_price:.2f}."
                            ),
                            expected_value=f"{expected_total:.2f}",
                            actual_value=f"{item.total_price:.2f}",
                        )
                    )

    def _check_subtotal(self, doc: ExtractedDocument, discrepancies: List[Discrepancy]) -> float:
        if not doc.line_items:
            # If no line items extracted, trust doc subtotal or total
            return doc.subtotal if doc.subtotal > 0 else doc.total_amount

        calculated_subtotal = round(sum(item.total_price for item in doc.line_items), 2)

        if doc.subtotal > 0:
            diff = abs(calculated_subtotal - doc.subtotal)
            if diff > self.tolerance:
                discrepancies.append(
                    Discrepancy(
                        rule_name="SUBTOTAL_MISMATCH",
                        severity=Severity.ERROR,
                        field="subtotal",
                        message=(
                            f"Sum of {len(doc.line_items)} line items ({doc.currency} {calculated_subtotal:.2f}) "
                            f"does not match printed subtotal ({doc.currency} {doc.subtotal:.2f}). "
                            f"Variance: {doc.currency} {diff:.2f}."
                        ),
                        expected_value=f"{calculated_subtotal:.2f}",
                        actual_value=f"{doc.subtotal:.2f}",
                    )
                )
        return calculated_subtotal

    def _check_tax(self, doc: ExtractedDocument, base_amount: float, discrepancies: List[Discrepancy]) -> None:
        if doc.tax_rate_percent and doc.tax_rate_percent > 0 and base_amount > 0:
            expected_tax = round(base_amount * (doc.tax_rate_percent / 100.0), 2)
            if doc.tax_amount > 0:
                diff = abs(expected_tax - doc.tax_amount)
                # Allow higher rounding tolerance for composite tax rates
                if diff > max(self.tolerance * 2, 0.05):
                    discrepancies.append(
                        Discrepancy(
                            rule_name="TAX_RATE_VARIANCE",
                            severity=Severity.WARNING,
                            field="tax_amount",
                            message=(
                                f"Extracted tax ({doc.currency} {doc.tax_amount:.2f}) differs from "
                                f"{doc.tax_rate_percent}% of subtotal ({doc.currency} {expected_tax:.2f})."
                            ),
                            expected_value=f"{expected_tax:.2f}",
                            actual_value=f"{doc.tax_amount:.2f}",
                        )
                    )

    def _check_total(self, doc: ExtractedDocument, subtotal: float, discrepancies: List[Discrepancy]) -> float:
        calculated_total = round(
            subtotal + doc.tax_amount + doc.tip_amount - doc.discount_amount, 2
        )

        diff = abs(calculated_total - doc.total_amount)
        if diff > self.tolerance:
            discrepancies.append(
                Discrepancy(
                    rule_name="TOTAL_RECONCILIATION",
                    severity=Severity.ERROR,
                    field="total_amount",
                    message=(
                        f"Reconciled total ({doc.currency} {calculated_total:.2f} = "
                        f"subtotal {subtotal:.2f} + tax {doc.tax_amount:.2f} + tip {doc.tip_amount:.2f} - discount {doc.discount_amount:.2f}) "
                        f"does not match printed total ({doc.currency} {doc.total_amount:.2f}). "
                        f"Discrepancy: {doc.currency} {diff:.2f}."
                    ),
                    expected_value=f"{calculated_total:.2f}",
                    actual_value=f"{doc.total_amount:.2f}",
                )
            )
        return calculated_total

    def _check_critical_fields(self, doc: ExtractedDocument, discrepancies: List[Discrepancy]) -> None:
        if not doc.vendor_name or doc.vendor_name.strip().lower() in ("unknown", "unknown vendor", ""):
            discrepancies.append(
                Discrepancy(
                    rule_name="MISSING_VENDOR",
                    severity=Severity.WARNING,
                    field="vendor_name",
                    message="Vendor name is missing or unidentifiable from document header.",
                    expected_value="Valid vendor name",
                    actual_value=doc.vendor_name,
                )
            )

        if doc.total_amount <= 0:
            discrepancies.append(
                Discrepancy(
                    rule_name="ZERO_TOTAL_AMOUNT",
                    severity=Severity.ERROR,
                    field="total_amount",
                    message="Document has a total amount of $0.00 or negative.",
                    expected_value="> 0.00",
                    actual_value=f"{doc.total_amount:.2f}",
                )
            )

        if not doc.date:
            discrepancies.append(
                Discrepancy(
                    rule_name="MISSING_DATE",
                    severity=Severity.WARNING,
                    field="date",
                    message="Document date was not identified or is unreadable.",
                    expected_value="YYYY-MM-DD",
                    actual_value="None",
                )
            )

    def _check_date_sanity(self, doc: ExtractedDocument, discrepancies: List[Discrepancy]) -> None:
        if not doc.date:
            return

        parsed_date: Optional[date] = None
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
            try:
                parsed_date = datetime.strptime(doc.date.strip(), fmt).date()
                break
            except ValueError:
                continue

        if parsed_date:
            today = date.today()
            if (parsed_date - today).days > 1:
                discrepancies.append(
                    Discrepancy(
                        rule_name="FUTURE_DATE_ANOMALY",
                        severity=Severity.WARNING,
                        field="date",
                        message=f"Document date '{doc.date}' is set in the future relative to system date.",
                        expected_value=f"<= {today.isoformat()}",
                        actual_value=str(parsed_date),
                    )
                )

    def _check_confidence(self, doc: ExtractedDocument, discrepancies: List[Discrepancy]) -> None:
        if doc.extraction_confidence < 0.70:
            discrepancies.append(
                Discrepancy(
                    rule_name="LOW_EXTRACTION_CONFIDENCE",
                    severity=Severity.WARNING,
                    field="extraction_confidence",
                    message=(
                        f"Vision model reported low extraction confidence ({doc.extraction_confidence * 100:.0f}%). "
                        f"Verify numbers against visual image."
                    ),
                    expected_value=">= 70%",
                    actual_value=f"{doc.extraction_confidence * 100:.0f}%",
                )
            )
