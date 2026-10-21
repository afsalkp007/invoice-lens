"""Rich Command Line Interface for InvoiceLens."""

import argparse
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from invoice_lens.extractor import get_extractor
from invoice_lens.reconciler import AuditReconciler
from invoice_lens.exporter import AuditExporter
from invoice_lens.models import Severity, ReconciliationStatus

console = Console()


def render_audit_report(result):
    """Render a visual, high-impact terminal audit report using Rich."""
    doc = result.document

    # Header Panel
    status_style = (
        "bold green"
        if result.status == ReconciliationStatus.PASSED
        else ("bold yellow" if result.status == ReconciliationStatus.FLAGGED_FOR_REVIEW else "bold red")
    )
    status_icon = "✅" if result.status == ReconciliationStatus.PASSED else ("⚠️" if result.status == ReconciliationStatus.FLAGGED_FOR_REVIEW else "❌")

    header_text = Text()
    header_text.append(f"{status_icon} AUDIT VERDICT: {result.status.value}\n\n", style=status_style)
    header_text.append(f"Vendor:        {doc.vendor_name}\n", style="bold white")
    header_text.append(f"Invoice/Ref:   {doc.invoice_number or 'N/A'}\n")
    header_text.append(f"Date:          {doc.date or 'N/A'}\n")
    header_text.append(f"Currency:      {doc.currency}\n")
    header_text.append(f"VLM Confidence: {doc.extraction_confidence * 100:.0f}%\n")
    header_text.append(f"\n{result.summary}", style="italic cyan")

    console.print(Panel(header_text, title="[bold]InvoiceLens Financial Audit Report[/bold]", border_style=status_style))

    # Financial Reconciliation Table
    recon_table = Table(title="Financial Math Reconciliation", title_style="bold magenta")
    recon_table.add_column("Component", style="cyan")
    recon_table.add_column("Printed on Doc", justify="right")
    recon_table.add_column("Calculated Invariant", justify="right")
    recon_table.add_column("Variance / Status", justify="center")

    sub_diff = abs(doc.subtotal - result.calculated_subtotal)
    recon_table.add_row(
        "Subtotal",
        f"{doc.currency} {doc.subtotal:.2f}",
        f"{doc.currency} {result.calculated_subtotal:.2f}",
        "[green]Reconciled[/green]" if sub_diff <= 0.02 else f"[red]Diff: {doc.currency} {sub_diff:.2f}[/red]",
    )
    recon_table.add_row(
        "Tax Amount",
        f"{doc.currency} {doc.tax_amount:.2f}",
        f"{doc.tax_rate_percent}%" if doc.tax_rate_percent else "N/A",
        "—",
    )
    recon_table.add_row(
        "Tip / Gratuity",
        f"{doc.currency} {doc.tip_amount:.2f}",
        "—",
        "—",
    )
    recon_table.add_row(
        "Discount",
        f"-{doc.currency} {doc.discount_amount:.2f}",
        "—",
        "—",
    )

    tot_diff = abs(doc.total_amount - result.calculated_total)
    recon_table.add_row(
        "[bold]Grand Total[/bold]",
        f"[bold]{doc.currency} {doc.total_amount:.2f}[/bold]",
        f"[bold]{doc.currency} {result.calculated_total:.2f}[/bold]",
        "[bold green]PERFECT MATCH[/bold green]" if tot_diff <= 0.02 else f"[bold red]MISMATCH: {doc.currency} {tot_diff:.2f}[/bold red]",
    )
    console.print(recon_table)

    # Line Items Table
    if doc.line_items:
        items_table = Table(title="Extracted Line Items", title_style="bold blue")
        items_table.add_column("#", justify="right", style="dim")
        items_table.add_column("Description", style="white")
        items_table.add_column("Category", style="yellow")
        items_table.add_column("Qty", justify="right")
        items_table.add_column("Unit Price", justify="right")
        items_table.add_column("Total Price", justify="right", style="green")
        items_table.add_column("VLM Conf", justify="center")

        for i, item in enumerate(doc.line_items, 1):
            conf_style = "green" if item.confidence.value == "HIGH" else "yellow"
            items_table.add_row(
                str(i),
                item.description,
                item.category or "General",
                f"{item.quantity:.1f}" if item.quantity % 1 != 0 else str(int(item.quantity)),
                f"{doc.currency} {item.unit_price:.2f}",
                f"{doc.currency} {item.total_price:.2f}",
                f"[{conf_style}]{item.confidence.value}[/{conf_style}]",
            )
        console.print(items_table)

    # Discrepancies Table
    if result.discrepancies:
        disc_table = Table(title="⚠️ Flagged Violations & Discrepancies", title_style="bold red")
        disc_table.add_column("Severity", justify="center")
        disc_table.add_column("Rule ID", style="bold yellow")
        disc_table.add_column("Field", style="cyan")
        disc_table.add_column("Explanation")
        disc_table.add_column("Expected", style="green")
        disc_table.add_column("Actual", style="red")

        for d in result.discrepancies:
            sev_color = "red" if d.severity == Severity.ERROR else "yellow"
            disc_table.add_row(
                f"[{sev_color}]{d.severity.value}[/{sev_color}]",
                d.rule_name,
                d.field,
                d.message,
                d.expected_value or "—",
                d.actual_value or "—",
            )
        console.print(disc_table)
    else:
        console.print("\n[bold green]✨ Clean audit: Zero discrepancies detected.[/bold green]\n")


def audit_document(file_path: Path, provider: str = None, export_fmt: str = None, output_file: str = None):
    """Audit a single document image."""
    if not file_path.exists():
        console.print(f"[bold red]Error: Document file not found: {file_path}[/bold red]")
        sys.exit(1)

    console.print(f"\n[cyan]🔍 Auditing document:[/cyan] [bold]{file_path.name}[/bold]...")

    with open(file_path, "rb") as f:
        image_bytes = f.read()

    extractor = get_extractor(provider=provider)
    doc = extractor.extract(image_bytes, hint_filename=file_path.name)

    reconciler = AuditReconciler()
    result = reconciler.audit(doc)

    render_audit_report(result)

    # Handle Exports
    if export_fmt:
        base_out = output_file or f"audit_{file_path.stem}.{export_fmt.lower()}"
        if export_fmt.lower() == "json":
            out = AuditExporter.to_json(result, base_out)
            console.print(f"[green]📁 Exported JSON report to:[/green] {out}")
        elif export_fmt.lower() == "csv":
            out = AuditExporter.to_accounting_csv(result, base_out)
            console.print(f"[green]📁 Exported Accounting CSV to:[/green] {out}")
        elif export_fmt.lower() in ("md", "markdown"):
            md = AuditExporter.to_markdown(result)
            Path(base_out).write_text(md, encoding="utf-8")
            console.print(f"[green]📁 Exported Markdown report to:[/green] {base_out}")

    return result


def run_sample_suite():
    """Run an automated audit across all sample documents."""
    sample_dir = Path(__file__).parent.parent / "sample_docs"
    samples = [
        sample_dir / "receipt_cafe.png",
        sample_dir / "invoice_saas.png",
        sample_dir / "invoice_discrepancy.png",
    ]

    console.print(Panel(
        "[bold cyan]Running Automated InvoiceLens Audit Test Suite across Sample Documents[/bold cyan]",
        border_style="cyan"
    ))

    for s in samples:
        if s.exists():
            audit_document(s)
            console.print("\n" + "=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="InvoiceLens - Multimodal Document Auditor & Financial Reconciliation Engine"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Audit command
    audit_parser = subparsers.add_parser("audit", help="Audit an invoice or receipt image")
    audit_parser.add_argument("file", type=str, help="Path to invoice/receipt image")
    audit_parser.add_argument(
        "--provider",
        choices=["gemini", "mock"],
        default=None,
        help="VLM provider (defaults to VLM_PROVIDER from env or mock fallback)",
    )
    audit_parser.add_argument(
        "--export",
        choices=["json", "csv", "md"],
        default=None,
        help="Export audit output format",
    )
    audit_parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Destination path for exported file",
    )

    # Sample command
    subparsers.add_parser("sample", help="Run audit on built-in sample receipts and invoices")

    args = parser.parse_args()

    if args.command == "audit":
        audit_document(Path(args.file), provider=args.provider, export_fmt=args.export, output_file=args.output)
    elif args.command == "sample":
        run_sample_suite()
    else:
        # Default behavior if no args provided
        parser.print_help()


if __name__ == "__main__":
    main()
