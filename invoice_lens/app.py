"""Interactive Streamlit Human-in-the-Loop (HITL) Review Dashboard for InvoiceLens."""

import os
import io
import warnings
from pathlib import Path
from PIL import Image

warnings.filterwarnings("ignore")

import streamlit as st

from invoice_lens.extractor import get_extractor
from invoice_lens.reconciler import AuditReconciler
from invoice_lens.exporter import AuditExporter
from invoice_lens.models import ExtractedDocument, LineItem, Severity, ReconciliationStatus

# Streamlit Page Config
st.set_page_config(
    page_title="InvoiceLens | Multimodal Document Auditor & HITL Review",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 12px;
        text-align: center;
    }
    .badge-passed {
        background-color: #DCFCE7;
        color: #166534;
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: 600;
    }
    .badge-review {
        background-color: #FEF9C3;
        color: #854D0E;
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: 600;
    }
    .badge-failed {
        background-color: #FEE2E2;
        color: #991B1B;
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="main-header">🔍 InvoiceLens: Multimodal Document Auditor</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Automated VLM line-item extraction, deterministic financial reconciliation, and Human-in-the-Loop review UX.</div>',
    unsafe_allow_html=True,
)

# Sidebar Configuration
st.sidebar.header("⚙️ Configuration")
provider_choice = st.sidebar.selectbox(
    "VLM Engine",
    options=["gemini", "mock"],
    index=0 if os.getenv("GEMINI_API_KEY") and not os.getenv("GEMINI_API_KEY").startswith("your_") else 1,
    help="Select 'gemini' for real Vision API extraction or 'mock' for instant offline demonstration.",
)

tolerance_cents = st.sidebar.slider(
    "Math Tolerance ($)",
    min_value=0.00,
    max_value=0.10,
    value=0.02,
    step=0.01,
    help="Permissible rounding difference before flagging an arithmetic discrepancy.",
)

st.sidebar.divider()
st.sidebar.subheader("📄 Document Input")
doc_source = st.sidebar.radio(
    "Select Source",
    options=["Pre-loaded Sample Document", "Upload Custom Image"],
)

sample_dir = Path(__file__).parent.parent / "sample_docs"

sample_map = {
    "Blue Bottle Cafe Receipt (Passed ✅)": sample_dir / "receipt_cafe.png",
    "Datadog SaaS B2B Invoice (Passed ✅)": sample_dir / "invoice_saas.png",
    "Apex Logistics Freight (Failed - $15 Math Discrepancy ❌)": sample_dir / "invoice_discrepancy.png",
}

image_bytes = None
image_name = ""

if doc_source == "Pre-loaded Sample Document":
    sample_key = st.sidebar.selectbox("Choose Sample Document", list(sample_map.keys()), index=2)
    selected_path = sample_map[sample_key]
    if selected_path.exists():
        with open(selected_path, "rb") as f:
            image_bytes = f.read()
        image_name = selected_path.name
else:
    uploaded_file = st.sidebar.file_uploader(
        "Upload Receipt or Invoice (PNG, JPG, JPEG)",
        type=["png", "jpg", "jpeg"],
    )
    if uploaded_file is not None:
        image_bytes = uploaded_file.read()
        image_name = uploaded_file.name

# Main Layout: 2 Columns (Left: Visual Inspector, Right: Audit Results & HITL Review)
col_left, col_right = st.columns([4, 6], gap="medium")

with col_left:
    st.subheader("🖼️ Document Preview")
    if image_bytes:
        pil_img = Image.open(io.BytesIO(image_bytes))
        st.image(pil_img, use_container_width=True, caption=f"Document: {image_name}")
    else:
        st.info("👈 Select a sample document or upload an image to begin audit.")

if image_bytes:
    # Perform Extraction & Audit
    with st.spinner("Extracting financial data via VLM & running reconciliation rules..."):
        extractor = get_extractor(provider=provider_choice)
        doc = extractor.extract(image_bytes, hint_filename=image_name)
        reconciler = AuditReconciler(tolerance=tolerance_cents)
        result = reconciler.audit(doc)

    with col_right:
        st.subheader("📊 Audit & Reconciliation Verdict")

        # Status Banner
        if result.status == ReconciliationStatus.PASSED:
            st.success(f"**STATUS: PASSED** — {result.summary}")
        elif result.status == ReconciliationStatus.FLAGGED_FOR_REVIEW:
            st.warning(f"**STATUS: FLAGGED FOR REVIEW** — {result.summary}")
        else:
            st.error(f"**STATUS: FAILED DISCREPANCY** — {result.summary}")

        # Metrics Row
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Vendor", doc.vendor_name[:16])
        with m2:
            st.metric("Printed Total", f"{doc.currency} {doc.total_amount:.2f}")
        with m3:
            st.metric("Calculated Total", f"{doc.currency} {result.calculated_total:.2f}")
        with m4:
            variance = abs(doc.total_amount - result.calculated_total)
            st.metric(
                "Variance",
                f"{doc.currency} {variance:.2f}",
                delta=f"-{variance:.2f}" if variance > 0.02 else "0.00",
                delta_color="inverse" if variance > 0.02 else "normal",
            )

        # Discrepancies Alert Box
        if result.discrepancies:
            st.markdown("#### ⚠️ Flagged Discrepancies")
            for d in result.discrepancies:
                alert_type = st.error if d.severity == Severity.ERROR else st.warning
                alert_type(
                    f"**[{d.severity.value}] Rule `{d.rule_name}` ({d.field}):** {d.message} "
                    f"(Expected: `{d.expected_value or 'N/A'}` | Document Claimed: `{d.actual_value or 'N/A'}`)"
                )

        # Tabbed Details
        tab_items, tab_recon, tab_hitl, tab_export = st.tabs([
            "📋 Line Items",
            "🧮 Math Invariants",
            "🧑‍💼 Human-in-the-Loop Review",
            "💾 Export Reports",
        ])

        with tab_items:
            if doc.line_items:
                items_data = [
                    {
                        "#": i,
                        "Description": item.description,
                        "Category": item.category or "General",
                        "Qty": item.quantity,
                        "Unit Price": f"{doc.currency} {item.unit_price:.2f}",
                        "Total Price": f"{doc.currency} {item.total_price:.2f}",
                        "Confidence": item.confidence.value,
                    }
                    for i, item in enumerate(doc.line_items, 1)
                ]
                st.dataframe(items_data, use_container_width=True)
            else:
                st.info("No itemized line items found.")

        with tab_recon:
            st.markdown("##### Reconciliation Proof")
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                st.write("**Extracted Values:**")
                st.write(f"- Subtotal: `{doc.currency} {doc.subtotal:.2f}`")
                st.write(f"- Tax Amount: `{doc.currency} {doc.tax_amount:.2f}`")
                st.write(f"- Tip Amount: `{doc.currency} {doc.tip_amount:.2f}`")
                st.write(f"- Discounts: `-{doc.currency} {doc.discount_amount:.2f}`")
                st.write(f"- **Printed Grand Total:** `{doc.currency} {doc.total_amount:.2f}`")
            with col_r2:
                st.write("**Deterministic Invariant Calculation:**")
                st.code(
                    f"Calculated Subtotal = Sum(LineItems) = {result.calculated_subtotal:.2f}\n"
                    f"Calculated Total    = Subtotal ({result.calculated_subtotal:.2f})\n"
                    f"                    + Tax ({doc.tax_amount:.2f})\n"
                    f"                    + Tip ({doc.tip_amount:.2f})\n"
                    f"                    - Discount ({doc.discount_amount:.2f})\n"
                    f"                    = {result.calculated_total:.2f}\n\n"
                    f"Variance            = |{doc.total_amount:.2f} - {result.calculated_total:.2f}| = {variance:.2f}",
                    language="text",
                )

        with tab_hitl:
            st.markdown("##### 🧑‍💼 Human Review & Override Interface")
            st.caption("Reviewers can rectify OCR extraction errors or override flagged discrepancies before final accounting export.")

            with st.form("hitl_review_form"):
                f_vendor = st.text_input("Vendor Name", value=doc.vendor_name)
                f_inv_num = st.text_input("Invoice / Receipt Number", value=doc.invoice_number or "")
                f_date = st.text_input("Date (YYYY-MM-DD)", value=doc.date or "")

                c_sub, c_tax, c_tot = st.columns(3)
                with c_sub:
                    f_subtotal = st.number_input("Subtotal ($)", value=float(doc.subtotal), step=0.01)
                with c_tax:
                    f_tax = st.number_input("Tax ($)", value=float(doc.tax_amount), step=0.01)
                with c_tot:
                    f_total = st.number_input("Total Amount ($)", value=float(doc.total_amount), step=0.01)

                reviewer_notes = st.text_area("Reviewer Audit Notes", placeholder="e.g. Verified vendor billing discrepancy with finance team.")

                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    submit_override = st.form_submit_button("✅ Save Corrections & Re-Audit", use_container_width=True)
                with col_btn2:
                    approve_as_is = st.form_submit_button("🛡️ Approve Audit (Sign-off)", use_container_width=True)

                if submit_override:
                    # Update doc with human corrections
                    doc.vendor_name = f_vendor
                    doc.invoice_number = f_inv_num or None
                    doc.date = f_date or None
                    doc.subtotal = round(f_subtotal, 2)
                    doc.tax_amount = round(f_tax, 2)
                    doc.total_amount = round(f_total, 2)
                    new_result = reconciler.audit(doc)
                    st.success(f"Audit updated! New Status: {new_result.status.value}")
                    st.rerun()

                if approve_as_is:
                    st.balloons()
                    st.success("Invoice signed off and approved by reviewer! Ready for ERP integration.")

        with tab_export:
            st.markdown("##### 📥 Export Accounting Artifacts")
            json_str = result.model_dump_json(indent=2)
            md_str = AuditExporter.to_markdown(result)

            col_ex1, col_ex2 = st.columns(2)
            with col_ex1:
                st.download_button(
                    label="📄 Download Audit JSON",
                    data=json_str,
                    file_name=f"audit_{Path(image_name).stem}.json",
                    mime="application/json",
                    use_container_width=True,
                )
            with col_ex2:
                st.download_button(
                    label="📝 Download Markdown Report",
                    data=md_str,
                    file_name=f"audit_report_{Path(image_name).stem}.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
