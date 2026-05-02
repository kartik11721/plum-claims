"""Generate wrong-document samples for the TC001 demo (wrong doc type showcase)."""
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


def prescription_duplicate():
    """A second prescription — wrong doc when a hospital bill is also required."""
    doc = SimpleDocTemplate(str(OUT / "prescription_rajesh_kumar_followup.pdf"), pagesize=A4,
                             topMargin=15*mm, bottomMargin=15*mm, leftMargin=20*mm, rightMargin=20*mm)
    W = A4[0] - 40*mm
    story = []

    story.append(Paragraph("Dr. Arun Sharma", h("h1", 16, bold=True, align=TA_CENTER)))
    story.append(Paragraph("MBBS, MD (Internal Medicine)", h("sub", 10, align=TA_CENTER)))
    story.append(Paragraph("Reg. No: KA/45678/2015", h("reg", 9, align=TA_CENTER, color=colors.grey)))
    story.append(Paragraph("City Medical Centre, 12 MG Road, Bengaluru – 560001", h("addr", 9, align=TA_CENTER)))
    story.append(Paragraph("Ph: +91-80-41234567 | Timing: 9 AM – 1 PM, 5 PM – 8 PM", h("ph", 8, align=TA_CENTER, color=colors.grey)))
    story.append(HRFlowable(width=W, thickness=1, color=colors.HexColor("#3B82F6"), spaceAfter=8))

    pt = Table([
        [Paragraph("<b>Patient:</b> Rajesh Kumar", styles["Normal"]),
         Paragraph("<b>Date:</b> 06-Nov-2024", styles["Normal"])],
        [Paragraph("<b>Age/Gender:</b> 39 Years / Male", styles["Normal"]),
         Paragraph("<b>IP/OP No:</b> OPD-2024-08340  (Follow-up)", styles["Normal"])],
    ], colWidths=[W*0.6, W*0.4])
    pt.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ("PADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(pt)
    story.append(Spacer(1, 6))

    story.append(Paragraph("<b>Chief Complaint:</b> Follow-up — fever resolved, mild cough persisting", styles["Normal"]))
    story.append(Spacer(1, 4))
    story.append(Paragraph("<b>Diagnosis:</b> Viral Fever (resolving), Post-viral Cough", h("dx", 11, bold=True, color=colors.HexColor("#1D4ED8"))))
    story.append(Spacer(1, 8))

    story.append(Paragraph("℞  Prescription", h("rx", 12, bold=True)))
    story.append(HRFlowable(width=W, thickness=0.5, color=colors.grey, spaceAfter=4))

    meds = [
        ["#", "Medicine", "Dosage", "Duration"],
        ["1", "Syp. Benadryl (Diphenhydramine)", "10 mL at night", "5 days"],
        ["2", "Tab Vitamin C 500 mg", "0 – 0 – 1 (after dinner)", "5 days"],
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

    story.append(Paragraph("<b>Advice:</b> Steam inhalation twice daily. Return if cough worsens.", styles["Normal"]))
    story.append(Spacer(1, 20))

    sig = Table([[
        Paragraph("", styles["Normal"]),
        Paragraph("<b>Dr. Arun Sharma</b><br/>MD (Internal Medicine)<br/>Reg. No: KA/45678/2015",
                  h("sig", 9, align=TA_RIGHT)),
    ]], colWidths=[W*0.5, W*0.5])
    story.append(sig)

    doc.build(story)
    print(f"✓ {OUT}/prescription_rajesh_kumar_followup.pdf")


def pharmacy_bill_wrong():
    """A pharmacy bill uploaded for a CONSULTATION claim — clearly wrong type."""
    doc = SimpleDocTemplate(str(OUT / "pharmacy_bill_rajesh_kumar.pdf"), pagesize=A4,
                             topMargin=15*mm, bottomMargin=15*mm, leftMargin=20*mm, rightMargin=20*mm)
    W = A4[0] - 40*mm
    story = []

    story.append(Paragraph("MEDPLUS PHARMACY", h("pn", 18, bold=True, align=TA_CENTER, color=colors.HexColor("#6B21A8"))))
    story.append(Paragraph("Shop 5, Koramangala 1st Block, Bengaluru – 560034", h("pa", 9, align=TA_CENTER)))
    story.append(Paragraph("Drug Lic No: KA-BLR-RETAIL-20891  |  GSTIN: 29PQRST5678G1ZY", h("pg", 8, align=TA_CENTER, color=colors.grey)))
    story.append(HRFlowable(width=W, thickness=2, color=colors.HexColor("#6B21A8"), spaceAfter=6))

    story.append(Paragraph("PHARMACY BILL", h("bt", 13, bold=True, align=TA_CENTER)))
    story.append(Spacer(1, 4))

    meta = Table([
        [Paragraph("<b>Bill No:</b> MPK/2024/44521", styles["Normal"]),
         Paragraph("<b>Date:</b> 01-Nov-2024", styles["Normal"])],
        [Paragraph("<b>Patient:</b> Rajesh Kumar", styles["Normal"]),
         Paragraph("<b>Prescribing Doctor:</b> Dr. Arun Sharma", styles["Normal"])],
    ], colWidths=[W*0.5, W*0.5])
    meta.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 0.5, colors.HexColor("#D8B4FE")),
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#FAF5FF")),
        ("PADDING", (0,0), (-1,-1), 6),
        ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#E9D5FF")),
    ]))
    story.append(meta)
    story.append(Spacer(1, 10))

    items = [
        ["MEDICINE", "BATCH", "EXPIRY", "QTY", "MRP (₹)", "AMOUNT (₹)"],
        ["Tab Paracetamol 650 mg (strip/10)", "BT-24891", "06/2026", "2", "48.00", "96.00"],
        ["Tab Vitamin C 500 mg (strip/10)", "VC-71234", "12/2026", "1", "55.00", "55.00"],
        ["Syp. Electral 200 mL", "EL-33421", "03/2026", "2", "35.00", "70.00"],
    ]
    bt = Table(items, colWidths=[W*0.33, W*0.11, W*0.10, W*0.07, W*0.17, W*0.17])
    bt.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#6B21A8")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("ALIGN", (3,0), (-1,-1), "CENTER"),
        ("ALIGN", (5,1), (5,-1), "RIGHT"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#FAF5FF")]),
        ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#E9D5FF")),
        ("PADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(bt)

    totals = Table([
        ["", "Subtotal:", "221.00"],
        ["", "Discount (5%):", "– 11.05"],
        ["", "Net Amount:", "₹ 209.95"],
    ], colWidths=[W*0.50, W*0.30, W*0.20])
    totals.setStyle(TableStyle([
        ("ALIGN", (1,0), (-1,-1), "RIGHT"),
        ("FONTNAME", (1,2), (-1,2), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("LINEABOVE", (1,2), (-1,2), 1, colors.black),
        ("PADDING", (0,0), (-1,-1), 4),
        ("BACKGROUND", (0,2), (-1,2), colors.HexColor("#F3E8FF")),
    ]))
    story.append(totals)
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>Payment Mode:</b> UPI", styles["Normal"]))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Medicines sold against valid prescription only. Not valid for returns after 7 days.",
                            h("disc", 7, align=TA_CENTER, color=colors.grey)))

    doc.build(story)
    print(f"✓ {OUT}/pharmacy_bill_rajesh_kumar.pdf")


if __name__ == "__main__":
    prescription_duplicate()
    pharmacy_bill_wrong()
    print(f"\nFiles saved to: {OUT.resolve()}")
    print("\nDemo scenarios:")
    print("  TC001-A: CONSULTATION + prescription_rajesh_kumar.pdf + prescription_rajesh_kumar_followup.pdf")
    print("           → Missing: Hospital Bill")
    print("  TC001-B: CONSULTATION + pharmacy_bill_rajesh_kumar.pdf only")
    print("           → You uploaded: Pharmacy Bill. Missing: Prescription, Hospital Bill")
