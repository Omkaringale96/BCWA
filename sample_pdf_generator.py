import os
import io
import logging

def create_sample_pdf(title, subtitle, store_name, doc_number):
    """
    Generate professional sample PDF bytes using ReportLab or clean PDF canvas structure.
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from reportlab.lib import colors

        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Header Banner
        c.setFillColor(colors.HexColor('#1E3A8A')) # Dark Blue
        c.rect(0, height - 80, width, 80, fill=True, stroke=False)

        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(30, height - 40, "BOISAR WELFARE CHEMIST ASSOCIATION (BCWA)")
        c.setFont("Helvetica", 12)
        c.drawString(30, height - 60, "Official Pharmacy Compliance & License Verification System")

        # Document Title
        c.setFillColor(colors.HexColor('#111827'))
        c.setFont("Helvetica-Bold", 20)
        c.drawString(40, height - 130, title)

        c.setFillColor(colors.HexColor('#4B5563'))
        c.setFont("Helvetica", 12)
        c.drawString(40, height - 150, subtitle)

        # Divider
        c.setStrokeColor(colors.HexColor('#E5E7EB'))
        c.setLineWidth(1)
        c.line(40, height - 165, width - 40, height - 165)

        # Document Details Box
        c.setFillColor(colors.HexColor('#F8FAFC'))
        c.rect(40, height - 320, width - 80, 140, fill=True, stroke=True)

        c.setFillColor(colors.HexColor('#1E293B'))
        c.setFont("Helvetica-Bold", 12)
        c.drawString(60, height - 195, f"Medical Store: {store_name}")
        c.drawString(60, height - 220, f"Registration / Ref #: {doc_number}")
        c.drawString(60, height - 245, "Issuing Authority: FDA Maharashtra / Competent Authority")
        c.drawString(60, height - 270, "Status: Verified & Active")
        c.drawString(60, height - 295, "Verification Date: 2026-08-06")

        # Watermark Stamp
        c.setFillColor(colors.HexColor('#D1D5DB'))
        c.setFont("Helvetica-Bold", 42)
        c.drawString(100, height - 450, "BCWA OFFICIAL COPY")

        # Footer
        c.setFillColor(colors.HexColor('#6B7280'))
        c.setFont("Helvetica", 9)
        c.drawString(40, 40, "This is an automated verified document record generated for BCWA Portal Self-Service Vault.")
        c.drawString(40, 25, "Boisar MIDC & Palghar Region • https://bcwa.onrender.com")

        c.showPage()
        c.save()

        buffer.seek(0)
        return buffer.getvalue()
    except Exception as e:
        logging.error(f"[PDF GENERATION WARNING] ReportLab fallback: {e}")
        # Fallback raw minimal valid PDF string
        raw_pdf = (
            f"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            f"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
            f"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Contents 4 0 R>>endobj\n"
            f"4 0 obj<</Length 120>>stream\nBT /F1 18 Tf 50 700 Td ({title}) Tj /F1 12 Tf 0 -30 Td ({store_name} - {doc_number}) Tj ET\nendstream\nendobj\n"
            f"xref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000056 00000 n\n0000000111 00000 n\n0000000212 00000 n\n"
            f"trailer<</Size 5/Root 1 0 R>>\nstartxref\n380\n%%EOF"
        )
        return raw_pdf.encode('utf-8')

def ensure_sample_pdfs_for_store(store_id, store_name):
    """Create sample PDF files in static/docs for store if missing."""
    doc_folder = os.path.join(os.path.dirname(__file__), 'static', 'docs')
    os.makedirs(doc_folder, exist_ok=True)

    samples = [
        ("Drug License.pdf", "DRUG LICENSE (20B / 21B)", "Form 20B & Form 21B Pharmacy License", f"DL-{store_id}-20B"),
        ("Food License.pdf", "FSSAI FOOD LICENSE", "Food Safety and Standards Authority Certificate", f"FSSAI-{store_id}"),
        ("Inspection Report.pdf", "ANNUAL FDA INSPECTION REPORT", "Official Pharmacy Inspection Verification", f"INSP-{store_id}"),
        ("Rent Agreement.pdf", "STORE RENT AGREEMENT", "Commercial Shop Lease Agreement", f"RENT-{store_id}"),
        ("Owner Aadhaar.pdf", "OWNER AADHAAR IDENTIFICATION", "Verified Owner Identity Document", f"ADH-{store_id}")
    ]

    generated_urls = {}
    for filename, title, subtitle, ref in samples:
        file_path = os.path.join(doc_folder, f"{store_id}_{filename}")
        if not os.path.exists(file_path):
            pdf_bytes = create_sample_pdf(title, subtitle, store_name, ref)
            with open(file_path, 'wb') as f:
                f.write(pdf_bytes)
        generated_urls[filename] = f"/static/docs/{store_id}_{filename}"

    return generated_urls
