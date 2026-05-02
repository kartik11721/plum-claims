"""Generate sample medical documents for manual UI testing (TC004 scenario)."""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

OUT = Path(__file__).parent.parent.parent / "sample_docs"
OUT.mkdir(exist_ok=True)

styles = getSampleStyleSheet()

def h(name, size, bold=False, align=TA_LEFT, color=colors.black):
    return ParagraphStyle(name, fontSize=size, fontName="Helvetica-Bold" if bold else "Helvetica",
                          alignment=align, textColor=color, spaceAfter=2)

def prescription():
    doc = SimpleDocTemplate(str(OUT / "prescription_rajesh_kumar.pdf"), pagesize=A4,
                             topMargin=15*mm, bottomMargin=15*mm, leftMargin=20*mm, rightMargin=20*mm)
    W = A4[0] - 40*mm
    story = []

    # Header
    story.append(Paragraph("Dr. Arun Sharma", h("h1", 16, bold=True, align=TA_CENTER)))
    story.append(Paragraph("MBBS, MD (Internal Medicine)", h("sub", 10, align=TA_CENTER)))
    story.append(Paragraph("Reg. No: KA/45678/2015", h("reg", 9, align=TA_CENTER, color=colors.grey)))
    story.append(Paragraph("City Medical Centre, 12 MG Road, Bengaluru – 560001", h("addr", 9, align=TA_CENTER)))
    story.append(Paragraph("Ph: +91-80-41234567 | Timing: 9 AM – 1 PM, 5 PM – 8 PM", h("ph", 8, align=TA_CENTER, color=colors.grey)))
    story.append(HRFlowable(width=W, thickness=1, color=colors.HexColor("#3B82F6"), spaceAfter=8))

    # Patient info
    pt = Table([
        [Paragraph("<b>Patient:</b> Rajesh Kumar", styles["Normal"]),
         Paragraph("<b>Date:</b> 01-Nov-2024", styles["Normal"])],
        [Paragraph("<b>Age/Gender:</b> 39 Years / Male", styles["Normal"]),
         Paragraph("<b>IP/OP No:</b> OPD-2024-08321", styles["Normal"])],
    ], colWidths=[W*0.6, W*0.4])
    pt.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ("PADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(pt)
    story.append(Spacer(1, 6))

    story.append(Paragraph("<b>Chief Complaint:</b> Fever since 3 days, body ache, mild headache", styles["Normal"]))
    story.append(Spacer(1, 4))
    story.append(Paragraph("<b>Diagnosis:</b> Viral Fever", h("dx", 11, bold=True, color=colors.HexColor("#1D4ED8"))))
    story.append(Spacer(1, 8))

    story.append(Paragraph("℞  Prescription", h("rx", 12, bold=True)))
    story.append(HRFlowable(width=W, thickness=0.5, color=colors.grey, spaceAfter=4))

    meds = [
        ["#", "Medicine", "Dosage", "Duration"],
        ["1", "Tab Paracetamol 650 mg", "1 – 1 – 1 (after meals)", "5 days"],
        ["2", "Tab Vitamin C 500 mg", "0 – 0 – 1 (after dinner)", "7 days"],
        ["3", "Syp. Electral / ORS", "200 mL after each loose stool", "As needed"],
    ]
    mt = Table(meds, colWidths=[8*mm, W*0.45, W*0.30, W*0.18])
    mt.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#3B82F6")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#EFF6FF")]),
        ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#CBD5E1")),
        ("PADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(mt)
    story.append(Spacer(1, 8))

    story.append(Paragraph("<b>Investigations Ordered:</b>", styles["Normal"]))
    story.append(Paragraph("• CBC (Complete Blood Count)", styles["Normal"]))
    story.append(Paragraph("• Dengue NS1 Antigen", styles["Normal"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph("<b>Advice:</b> Rest, adequate fluids, light diet. Follow-up after 5 days if no improvement.", styles["Normal"]))
    story.append(Spacer(1, 20))

    sig = Table([[
        Paragraph("", styles["Normal"]),
        Paragraph("<b>Dr. Arun Sharma</b><br/>MD (Internal Medicine)<br/>Reg. No: KA/45678/2015",
                  h("sig", 9, align=TA_RIGHT)),
    ]], colWidths=[W*0.5, W*0.5])
    story.append(sig)

    doc.build(story)
    print(f"✓ {OUT}/prescription_rajesh_kumar.pdf")


def hospital_bill():
    doc = SimpleDocTemplate(str(OUT / "hospital_bill_rajesh_kumar.pdf"), pagesize=A4,
                             topMargin=15*mm, bottomMargin=15*mm, leftMargin=20*mm, rightMargin=20*mm)
    W = A4[0] - 40*mm
    story = []

    story.append(Paragraph("CITY MEDICAL CENTRE", h("hname", 18, bold=True, align=TA_CENTER, color=colors.HexColor("#1E3A5F"))))
    story.append(Paragraph("12 MG Road, Bengaluru – 560001 | Ph: 080-41234567", h("ha", 9, align=TA_CENTER)))
    story.append(Paragraph("GSTIN: 29ABCDE1234F1ZX | Email: billing@citymedical.in", h("hg", 8, align=TA_CENTER, color=colors.grey)))
    story.append(HRFlowable(width=W, thickness=2, color=colors.HexColor("#1E3A5F"), spaceAfter=6))

    story.append(Paragraph("BILL / RECEIPT", h("bt", 14, bold=True, align=TA_CENTER)))
    story.append(Spacer(1, 4))

    meta = Table([
        [Paragraph("<b>Bill No:</b> CMC/2024/08321", styles["Normal"]),
         Paragraph("<b>Date:</b> 01-Nov-2024", styles["Normal"])],
        [Paragraph("<b>Patient:</b> Rajesh Kumar", styles["Normal"]),
         Paragraph("<b>Age/Gender:</b> 39 / Male", styles["Normal"])],
        [Paragraph("<b>Referring Doctor:</b> Dr. Arun Sharma", styles["Normal"]),
         Paragraph("<b>Dept:</b> General OPD", styles["Normal"])],
    ], colWidths=[W*0.6, W*0.4])
    meta.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 0.5, colors.HexColor("#94A3B8")),
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#F1F5F9")),
        ("PADDING", (0,0), (-1,-1), 6),
        ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#CBD5E1")),
    ]))
    story.append(meta)
    story.append(Spacer(1, 10))

    items = [
        ["DESCRIPTION", "QTY", "RATE (₹)", "AMOUNT (₹)"],
        ["Consultation Fee (OPD)", "1", "1,000.00", "1,000.00"],
        ["CBC – Complete Blood Count", "1", "300.00", "300.00"],
        ["Dengue NS1 Antigen Test", "1", "200.00", "200.00"],
    ]
    bt = Table(items, colWidths=[W*0.50, W*0.10, W*0.20, W*0.20])
    bt.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1E3A5F")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("ALIGN", (1,0), (-1,-1), "CENTER"),
        ("ALIGN", (3,1), (3,-1), "RIGHT"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#CBD5E1")),
        ("PADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(bt)

    totals = Table([
        ["", "Subtotal:", "1,500.00"],
        ["", "GST (0% on medical services):", "0.00"],
        ["", "Total Amount:", "₹ 1,500.00"],
    ], colWidths=[W*0.50, W*0.30, W*0.20])
    totals.setStyle(TableStyle([
        ("ALIGN", (1,0), (-1,-1), "RIGHT"),
        ("FONTNAME", (1,2), (-1,2), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("LINEABOVE", (1,2), (-1,2), 1, colors.black),
        ("PADDING", (0,0), (-1,-1), 4),
        ("BACKGROUND", (0,2), (-1,2), colors.HexColor("#DBEAFE")),
    ]))
    story.append(totals)
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>Payment Mode:</b> Cash", styles["Normal"]))
    story.append(Spacer(1, 20))

    footer = Table([[
        Paragraph("Received by: _________________<br/>Cashier", h("f", 9)),
        Paragraph("<b>Authorised Signatory</b><br/>City Medical Centre",
                  h("fs", 9, align=TA_RIGHT)),
    ]], colWidths=[W*0.5, W*0.5])
    story.append(footer)
    story.append(Spacer(1, 4))
    story.append(Paragraph("This is a computer-generated bill and is valid without a physical signature.",
                            h("disc", 7, align=TA_CENTER, color=colors.grey)))

    doc.build(story)
    print(f"✓ {OUT}/hospital_bill_rajesh_kumar.pdf")


def lab_report():
    doc = SimpleDocTemplate(str(OUT / "lab_report_rajesh_kumar.pdf"), pagesize=A4,
                             topMargin=15*mm, bottomMargin=15*mm, leftMargin=20*mm, rightMargin=20*mm)
    W = A4[0] - 40*mm
    story = []

    story.append(Paragraph("PRECISION DIAGNOSTICS PVT LTD", h("ln", 16, bold=True, align=TA_CENTER, color=colors.HexColor("#065F46"))))
    story.append(Paragraph("NABL Accredited Laboratory  |  Lab ID: KA-NABL-1234", h("la", 9, align=TA_CENTER)))
    story.append(Paragraph("45 Jayanagar 4th Block, Bengaluru – 560041  |  Ph: 080-26571234", h("lad", 9, align=TA_CENTER)))
    story.append(HRFlowable(width=W, thickness=2, color=colors.HexColor("#065F46"), spaceAfter=6))

    story.append(Paragraph("LABORATORY REPORT", h("rt", 13, bold=True, align=TA_CENTER)))
    story.append(Spacer(1, 4))

    info = Table([
        [Paragraph("<b>Patient:</b> Rajesh Kumar", styles["Normal"]),
         Paragraph("<b>Sample ID:</b> PD-2024-18723", styles["Normal"])],
        [Paragraph("<b>Age/Sex:</b> 39 Years / Male", styles["Normal"]),
         Paragraph("<b>Sample Date:</b> 01-Nov-2024", styles["Normal"])],
        [Paragraph("<b>Ref Doctor:</b> Dr. Arun Sharma", styles["Normal"]),
         Paragraph("<b>Report Date:</b> 01-Nov-2024", styles["Normal"])],
    ], colWidths=[W*0.55, W*0.45])
    info.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 0.5, colors.HexColor("#6EE7B7")),
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#ECFDF5")),
        ("PADDING", (0,0), (-1,-1), 6),
        ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#A7F3D0")),
    ]))
    story.append(info)
    story.append(Spacer(1, 10))

    story.append(Paragraph("CBC – Complete Blood Count", h("sh", 11, bold=True)))
    cbc = [
        ["TEST NAME", "RESULT", "UNIT", "NORMAL RANGE", "FLAG"],
        ["Haemoglobin", "13.2", "g/dL", "13.0 – 17.0", ""],
        ["WBC Count", "9,800", "/μL", "4,500 – 11,000", ""],
        ["Platelet Count", "1,85,000", "/μL", "1,50,000 – 4,50,000", ""],
        ["Neutrophils", "68", "%", "40 – 75", ""],
        ["Lymphocytes", "24", "%", "20 – 45", ""],
        ["MCV", "88.4", "fL", "80.0 – 100.0", ""],
    ]
    ct = Table(cbc, colWidths=[W*0.32, W*0.12, W*0.10, W*0.30, W*0.08])
    ct.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#065F46")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("ALIGN", (1,1), (-1,-1), "CENTER"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F0FDF4")]),
        ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#A7F3D0")),
        ("PADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(ct)
    story.append(Spacer(1, 8))

    story.append(Paragraph("Dengue Serology", h("sh2", 11, bold=True)))
    dng = [
        ["TEST NAME", "RESULT", "METHOD", "INTERPRETATION"],
        ["Dengue NS1 Antigen", "NEGATIVE", "ICT Rapid", "No active Dengue infection detected"],
    ]
    dt = Table(dng, colWidths=[W*0.28, W*0.15, W*0.20, W*0.37])
    dt.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#065F46")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTNAME", (1,1), (1,1), "Helvetica-Bold"),
        ("TEXTCOLOR", (1,1), (1,1), colors.HexColor("#065F46")),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#A7F3D0")),
        ("PADDING", (0,0), (-1,-1), 5),
        ("BACKGROUND", (0,1), (-1,1), colors.HexColor("#F0FDF4")),
    ]))
    story.append(dt)
    story.append(Spacer(1, 8))

    story.append(Paragraph("<b>Remarks:</b> WBC count is towards the upper limit of normal — monitor if fever persists. "
                            "Dengue NS1 negative. Clinical correlation advised.", styles["Normal"]))
    story.append(Spacer(1, 20))

    sig = Table([[
        Paragraph("", styles["Normal"]),
        Paragraph("<b>Dr. Meena Pillai</b><br/>MD (Pathology)<br/>Reg. No: KA/89012/2018<br/>Precision Diagnostics Pvt Ltd",
                  h("ps", 9, align=TA_RIGHT)),
    ]], colWidths=[W*0.5, W*0.5])
    story.append(sig)
    story.append(Spacer(1, 4))
    story.append(Paragraph("Report generated electronically. Valid without physical signature.",
                            h("d2", 7, align=TA_CENTER, color=colors.grey)))

    doc.build(story)
    print(f"✓ {OUT}/lab_report_rajesh_kumar.pdf")


if __name__ == "__main__":
    prescription()
    hospital_bill()
    lab_report()
    print(f"\nAll files saved to: {OUT.resolve()}")
    print("\nTest scenario — Consultation claim, EMP001 (Rajesh Kumar), ₹1,500")
    print("Expected result: APPROVED ₹1,350 (10% co-pay deducted)")
