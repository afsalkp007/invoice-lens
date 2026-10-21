"""Generate sample invoice and receipt images for demonstration and offline testing."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def create_receipt_image(output_path: Path):
    """Generate a clean cafe receipt."""
    img = Image.new("RGB", (480, 680), color="#FAF9F6")
    draw = ImageDraw.Draw(img)

    lines = [
        ("=== ARTISAN ROAST & BAKERY ===", 30, True),
        ("104 Market Street, Suite 400", 65, False),
        ("VAT: GB992019  |  Tel: +1-555-0192", 85, False),
        ("--------------------------------------------", 115, False),
        ("Date: 2026-10-18       Receipt: REC-4410", 135, False),
        ("Server: Table 14       Time: 09:15 AM", 155, False),
        ("--------------------------------------------", 175, False),
        ("QTY  ITEM                       AMOUNT", 195, True),
        ("--------------------------------------------", 215, False),
        (" 2   Oat Milk Flat White        $11.00", 235, False),
        (" 1   Avocado Sourdough Toast    $14.50", 260, False),
        (" 1   Almond Croissant           $ 7.00", 285, False),
        ("--------------------------------------------", 315, False),
        ("SUBTOTAL:                       $32.50", 340, False),
        ("TAX (8.00%):                    $ 2.60", 365, False),
        ("TIP:                            $ 5.00", 390, False),
        ("--------------------------------------------", 415, False),
        ("TOTAL PAID:                     $40.10", 440, True),
        ("--------------------------------------------", 470, False),
        ("Paid via: Apple Pay (Mastercard *8812)", 495, False),
        ("Approval Code: #918204", 515, False),
        ("Thank you for your visit!", 560, False),
        ("============================================", 590, False),
    ]

    for text, y, bold in lines:
        draw.text((30, y), text, fill="#1E1E1E")

    img.save(output_path)


def create_saas_invoice_image(output_path: Path):
    """Generate a B2B SaaS invoice."""
    img = Image.new("RGB", (560, 720), color="#FFFFFF")
    draw = ImageDraw.Draw(img)

    # Header banner
    draw.rectangle([(0, 0), (560, 40)], fill="#2C3E50")
    draw.text((25, 12), "DATADOG INFRASTRUCTURE INC. - OFFICIAL INVOICE", fill="#ECF0F1")

    lines = [
        ("Invoice Number: INV-2026-9041", 60),
        ("Issue Date:     2026-10-14", 80),
        ("Payment Due:    2026-11-14", 100),
        ("Vendor Tax ID:  US-84920194", 120),
        ("Bill To:        Acme Cloud Engineering Lab", 150),
        ("----------------------------------------------------------------------", 175),
        ("DESCRIPTION                    QTY   UNIT PRICE    TOTAL", 195),
        ("----------------------------------------------------------------------", 215),
        ("Pro Host Monitoring (20 hosts)  20     $15.00     $300.00", 235),
        ("APM & Distributed Tracing        1    $200.00     $200.00", 260),
        ("----------------------------------------------------------------------", 290),
        ("Subtotal:                                         $500.00", 315),
        ("Volume Discount:                                 -$ 50.00", 340),
        ("Sales Tax (8.25%):                                $ 41.25", 365),
        ("----------------------------------------------------------------------", 390),
        ("GRAND TOTAL DUE:                                  $491.25", 415),
        ("----------------------------------------------------------------------", 445),
        ("Payment Terms: Net 30", 475),
        ("Remit To: billing@datadog-sample.com", 495),
        ("Payment Method on File: ACH Auto-Debit", 515),
    ]

    for text, y in lines:
        draw.text((25, y), text, fill="#2C3E50")

    img.save(output_path)


def create_discrepancy_invoice_image(output_path: Path):
    """Generate an invoice with an intentional billing error ($15.00 overcharge)."""
    img = Image.new("RGB", (560, 720), color="#FFFDF7")
    draw = ImageDraw.Draw(img)

    # Header banner
    draw.rectangle([(0, 0), (560, 40)], fill="#8B0000")
    draw.text((25, 12), "APEX LOGISTICS & FREIGHT - COMMERCIAL INVOICE", fill="#FFFFFF")

    lines = [
        ("Invoice Number: APX-88219", 60),
        ("Issue Date:     2026-10-12", 80),
        ("Vendor Tax ID:  US-12940210", 100),
        ("Bill To:        Global Distribution Corp", 130),
        ("----------------------------------------------------------------------", 160),
        ("ITEM / SERVICE                 QTY   RATE         AMOUNT", 180),
        ("----------------------------------------------------------------------", 200),
        ("Expedited Freight Delivery       2    $120.00     $240.00", 220),
        ("Pallet Wrapping & Securing       1    $100.00     $100.00", 245),
        ("----------------------------------------------------------------------", 275),
        ("Subtotal:                                         $340.00", 300),
        ("Sales Tax (8.00%):                                $ 27.20", 325),
        ("----------------------------------------------------------------------", 350),
        ("TOTAL BILLED:                                     $382.20  <-- ERROR!", 375),
        ("----------------------------------------------------------------------", 405),
        ("*(Note: Reconciled sum is $367.20. Printed total overcharges $15.00)*", 435),
        ("Payment Status: Pending Approval", 470),
    ]

    for text, y in lines:
        color = "#B22222" if "ERROR" in text or "Note" in text else "#2A2A2A"
        draw.text((25, y), text, fill=color)

    img.save(output_path)


if __name__ == "__main__":
    docs_dir = Path(__file__).parent
    create_receipt_image(docs_dir / "receipt_cafe.png")
    create_saas_invoice_image(docs_dir / "invoice_saas.png")
    create_discrepancy_invoice_image(docs_dir / "invoice_discrepancy.png")
    print(f"Generated 3 sample document images in {docs_dir.resolve()}")
