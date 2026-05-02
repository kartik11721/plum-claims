"""
Generate mock medical document images for demo/testing.

Produces realistic-looking Indian medical documents (prescription, hospital bill,
lab report, pharmacy bill) using Pillow. Output images go to
backend/scripts/sample_docs/ and are suitable for uploading to the live vision pipeline.

Usage:
    cd backend
    python scripts/generate_mock_docs.py
"""

from __future__ import annotations
import os
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    raise SystemExit("Install Pillow first: pip install pillow")

OUTPUT_DIR = Path(__file__).parent / "sample_docs"
OUTPUT_DIR.mkdir(exist_ok=True)

W, H = 794, 1123  # A4 at 96dpi
BG = (255, 255, 255)
BLACK = (0, 0, 0)
DARK_BLUE = (15, 52, 96)
LIGHT_GRAY = (230, 230, 230)
MID_GRAY = (180, 180, 180)
RED = (200, 30, 30)


def _canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)


def _font(size: int, bold: bool = False):
    try:
        path = "/System/Library/Fonts/Helvetica.ttc" if not bold else "/System/Library/Fonts/HelveticaNeue.ttc"
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _header(draw: ImageDraw.ImageDraw, name: str, address: str, phone: str = ""):
    draw.rectangle([(0, 0), (W, 80)], fill=DARK_BLUE)
    draw.text((20, 12), name, font=_font(22, bold=True), fill=(255, 255, 255))
    draw.text((20, 42), address, font=_font(12), fill=(200, 220, 255))
    if phone:
        draw.text((20, 58), phone, font=_font(11), fill=(200, 220, 255))
    draw.rectangle([(0, 80), (W, 84)], fill=(255, 180, 0))


def _divider(draw: ImageDraw.ImageDraw, y: int):
    draw.line([(20, y), (W - 20, y)], fill=LIGHT_GRAY, width=1)


def _label_value(draw: ImageDraw.ImageDraw, y: int, label: str, value: str, lx: int = 20, vx: int = 160):
    draw.text((lx, y), label + ":", font=_font(11), fill=MID_GRAY)
    draw.text((vx, y), value, font=_font(11, bold=True), fill=BLACK)


def generate_prescription():
    img, draw = _canvas()
    _header(draw, "Dr. Anand Krishnamurthy, MBBS MD (Internal Medicine)",
            "Apollo Medical Centre, 21 Jubilee Hills, Hyderabad — 500033",
            "Tel: 040-2356-7890  Reg No: AP-23456-2019")

    draw.text((20, 95), "PRESCRIPTION", font=_font(16, bold=True), fill=DARK_BLUE)
    draw.text((W - 160, 95), "Date: 01 Nov 2024", font=_font(11), fill=BLACK)
    _divider(draw, 118)

    _label_value(draw, 128, "Patient", "Rajesh Kumar", 20, 130)
    _label_value(draw, 148, "Age/Sex", "38 Years / Male", 20, 130)
    _label_value(draw, 168, "Member ID", "EMP001", 20, 130)
    _divider(draw, 192)

    draw.text((20, 200), "Diagnosis:", font=_font(12, bold=True), fill=DARK_BLUE)
    draw.text((20, 220), "• Acute upper respiratory tract infection (URTI) with mild pharyngitis", font=_font(11), fill=BLACK)
    draw.text((20, 238), "• Seasonal allergic rhinitis", font=_font(11), fill=BLACK)
    _divider(draw, 260)

    draw.text((20, 268), "Rx  Medicines:", font=_font(12, bold=True), fill=DARK_BLUE)
    meds = [
        ("1.", "Tab Azithromycin 500mg", "1-0-0 × 5 days"),
        ("2.", "Tab Cetirizine 10mg", "0-0-1 × 7 days (at bedtime)"),
        ("3.", "Syp Benadryl (Diphenhydramine)", "10ml TDS × 5 days"),
        ("4.", "Tab Paracetamol 500mg", "1-1-1 SOS (if fever/pain)"),
    ]
    y = 292
    for num, name, dose in meds:
        draw.text((30, y), num, font=_font(11), fill=BLACK)
        draw.text((52, y), name, font=_font(11, bold=True), fill=BLACK)
        draw.text((320, y), dose, font=_font(11), fill=BLACK)
        y += 22
    _divider(draw, y + 8)

    draw.text((20, y + 18), "Instructions:", font=_font(11, bold=True), fill=DARK_BLUE)
    draw.text((20, y + 36), "• Rest, increase fluid intake. Avoid cold beverages.", font=_font(10), fill=BLACK)
    draw.text((20, y + 52), "• Review after 5 days if symptoms persist.", font=_font(10), fill=BLACK)

    draw.text((W - 200, H - 120), "Dr. Anand Krishnamurthy", font=_font(12, bold=True), fill=DARK_BLUE)
    draw.text((W - 200, H - 100), "MBBS, MD (Internal Medicine)", font=_font(10), fill=BLACK)
    draw.text((W - 200, H - 82), "Reg No: AP-23456-2019", font=_font(10), fill=BLACK)
    draw.rectangle([(W - 200, H - 140), (W - 20, H - 60)], outline=MID_GRAY, width=1)
    draw.text((20, H - 40), "Strictly for medical use only. Valid for 30 days from date of issue.", font=_font(9), fill=MID_GRAY)

    out = OUTPUT_DIR / "prescription_rajesh_kumar.jpg"
    img.save(out, quality=90)
    print(f"  Saved: {out}")


def generate_hospital_bill():
    img, draw = _canvas()
    _header(draw, "Apollo Hospitals",
            "Road No. 72, Jubilee Hills, Hyderabad — 500033  |  GSTIN: 36AABCA1234F1ZX",
            "Tel: 040-2360-7777  |  www.apollohospitals.com")

    draw.text((20, 95), "OUTPATIENT CONSULTATION BILL", font=_font(15, bold=True), fill=DARK_BLUE)
    draw.rectangle([(0, 115), (W, 135)], fill=(240, 245, 255))
    _label_value(draw, 119, "Bill No", "APH/OPD/2024/81234", 20, 120)
    _label_value(draw, 119, "Date", "01 Nov 2024", 400, 460)
    _divider(draw, 138)

    _label_value(draw, 148, "Patient Name", "Rajesh Kumar", 20, 160)
    _label_value(draw, 166, "Age / Gender", "38 Yrs / Male", 20, 160)
    _label_value(draw, 184, "UHID", "APH-9087654", 20, 160)
    _label_value(draw, 202, "Consultant", "Dr. Anand Krishnamurthy (Internal Medicine)", 20, 160)
    _divider(draw, 225)

    # Table header
    draw.rectangle([(20, 233), (W - 20, 253)], fill=(240, 245, 255))
    draw.text((25, 237), "S.No", font=_font(10, bold=True), fill=DARK_BLUE)
    draw.text((70, 237), "Description", font=_font(10, bold=True), fill=DARK_BLUE)
    draw.text((460, 237), "Qty", font=_font(10, bold=True), fill=DARK_BLUE)
    draw.text((520, 237), "Rate (₹)", font=_font(10, bold=True), fill=DARK_BLUE)
    draw.text((640, 237), "Amount (₹)", font=_font(10, bold=True), fill=DARK_BLUE)
    _divider(draw, 254)

    items = [
        ("1", "OPD Consultation Charges (Specialist)", "1", "900", "900"),
        ("2", "Registration / Administrative Charges", "1", "100", "100"),
        ("3", "Medicines Dispensed — Azithromycin 500mg (5 tabs)", "5", "28", "140"),
        ("4", "Medicines Dispensed — Cetirizine 10mg (7 tabs)", "7", "12", "84"),
        ("5", "Medicines Dispensed — Benadryl Syrup 100ml", "1", "76", "76"),
        ("6", "Medicines Dispensed — Paracetamol 500mg (10 tabs)", "10", "8", "80"),
    ]
    y = 262
    for num, desc, qty, rate, amt in items:
        draw.text((25, y), num, font=_font(10), fill=BLACK)
        draw.text((70, y), desc, font=_font(10), fill=BLACK)
        draw.text((465, y), qty, font=_font(10), fill=BLACK)
        draw.text((520, y), rate, font=_font(10), fill=BLACK)
        draw.text((645, y), amt, font=_font(10), fill=BLACK)
        y += 20
        _divider(draw, y)

    y += 10
    draw.text((520, y), "Subtotal", font=_font(11, bold=True), fill=BLACK)
    draw.text((645, y), "1,380", font=_font(11, bold=True), fill=BLACK)
    draw.text((520, y + 20), "GST (0% — Healthcare)", font=_font(10), fill=MID_GRAY)
    draw.text((645, y + 20), "0", font=_font(10), fill=MID_GRAY)
    draw.rectangle([(510, y + 40), (W - 20, y + 62)], fill=DARK_BLUE)
    draw.text((520, y + 46), "TOTAL AMOUNT PAYABLE", font=_font(11, bold=True), fill=(255, 255, 255))
    draw.text((640, y + 46), "₹1,380", font=_font(11, bold=True), fill=(255, 255, 255))

    draw.text((20, H - 100), "Network Hospital under Plum Health Insurance (PLUM_GHI_2024)", font=_font(10), fill=DARK_BLUE)
    draw.text((20, H - 80), "This bill is computer generated and does not require a physical signature.", font=_font(9), fill=MID_GRAY)
    draw.text((20, H - 60), "For billing queries: billing@apollohyderabad.com  |  040-2360-7777 Ext: 112", font=_font(9), fill=MID_GRAY)

    out = OUTPUT_DIR / "hospital_bill_rajesh_kumar.jpg"
    img.save(out, quality=90)
    print(f"  Saved: {out}")


def generate_lab_report():
    img, draw = _canvas()
    _header(draw, "SRL Diagnostics — Hyderabad",
            "Plot 45, Banjara Hills Road No. 3, Hyderabad — 500034  |  NABL Accredited",
            "Tel: 040-6655-4433  |  NABL Cert No: MC-3419")

    draw.text((20, 95), "LABORATORY TEST REPORT", font=_font(15, bold=True), fill=DARK_BLUE)
    draw.text((W - 200, 95), "NABL ACCREDITED", font=_font(10, bold=True), fill=(0, 140, 0))
    _divider(draw, 115)

    _label_value(draw, 125, "Patient", "Rajesh Kumar", 20, 160)
    _label_value(draw, 143, "Age / Sex", "38 Yrs / Male", 20, 160)
    _label_value(draw, 161, "Ref. Doctor", "Dr. Anand Krishnamurthy", 20, 160)
    _label_value(draw, 179, "Sample Date", "01 Nov 2024", 20, 160)
    _label_value(draw, 179, "Report Date", "01 Nov 2024", 380, 470)
    _label_value(draw, 197, "Report No", "SRL/HYD/2024/443211", 20, 160)
    _divider(draw, 218)

    draw.text((20, 226), "COMPLETE BLOOD COUNT (CBC)", font=_font(12, bold=True), fill=DARK_BLUE)
    draw.rectangle([(20, 244), (W - 20, 260)], fill=(240, 245, 255))
    cols = [(25, "Test Name"), (330, "Result"), (430, "Unit"), (520, "Normal Range"), (660, "Flag")]
    for x, label in cols:
        draw.text((x, 247), label, font=_font(9, bold=True), fill=DARK_BLUE)
    _divider(draw, 261)

    tests = [
        ("Haemoglobin (Hb)", "13.8", "g/dL", "13.0 – 17.0", ""),
        ("Total WBC Count", "11,200", "cells/µL", "4,000 – 11,000", "H"),
        ("Neutrophils", "72", "%", "40 – 75", ""),
        ("Lymphocytes", "20", "%", "20 – 45", ""),
        ("Eosinophils", "5", "%", "1 – 6", ""),
        ("Platelet Count", "2.4", "Lakh/µL", "1.5 – 4.5", ""),
        ("RBC Count", "4.9", "million/µL", "4.5 – 5.5", ""),
        ("MCV", "88.2", "fL", "83 – 101", ""),
    ]
    y = 268
    for name, result, unit, nrange, flag in tests:
        draw.text((25, y), name, font=_font(10), fill=BLACK)
        color = RED if flag else BLACK
        draw.text((330, y), result, font=_font(10, bold=bool(flag)), fill=color)
        draw.text((430, y), unit, font=_font(10), fill=BLACK)
        draw.text((520, y), nrange, font=_font(10), fill=MID_GRAY)
        if flag:
            draw.text((665, y), flag, font=_font(10, bold=True), fill=RED)
        y += 20
        _divider(draw, y)

    y += 12
    draw.text((20, y), "Comments:", font=_font(11, bold=True), fill=DARK_BLUE)
    draw.text((20, y + 18), "Mild leukocytosis (elevated WBC) consistent with acute bacterial infection. Clinical correlation advised.", font=_font(10), fill=BLACK)

    draw.text((W - 260, H - 100), "Dr. Pradeep Mohan, MD (Pathology)", font=_font(11, bold=True), fill=DARK_BLUE)
    draw.text((W - 260, H - 80), "Consultant Pathologist", font=_font(10), fill=BLACK)
    draw.text((W - 260, H - 62), "Reg No: TS-PATH-12345", font=_font(10), fill=BLACK)
    draw.text((20, H - 40), "This is a computer-generated report. Results should be interpreted in clinical context.", font=_font(9), fill=MID_GRAY)

    out = OUTPUT_DIR / "lab_report_rajesh_kumar.jpg"
    img.save(out, quality=90)
    print(f"  Saved: {out}")


def generate_pharmacy_bill():
    img, draw = _canvas()
    _header(draw, "MedPlus Pharmacy",
            "Shop 4, Apollo Hospital Complex, Jubilee Hills, Hyderabad — 500033",
            "Drug License: AP/DL/2018/34567  |  GST: 36AABCM5678G1ZP")

    draw.text((20, 95), "PHARMACY BILL / CASH MEMO", font=_font(15, bold=True), fill=DARK_BLUE)
    _label_value(draw, 120, "Bill No", "MPX-HYD-2024/99812", 20, 150)
    _label_value(draw, 120, "Date", "01 Nov 2024", 420, 480)
    _divider(draw, 142)

    _label_value(draw, 152, "Patient", "Rajesh Kumar", 20, 150)
    _label_value(draw, 170, "Rx Ref", "APH/OPD/2024/81234", 20, 150)
    _label_value(draw, 188, "Doctor", "Dr. Anand Krishnamurthy", 20, 150)
    _divider(draw, 208)

    draw.rectangle([(20, 216), (W - 20, 232)], fill=(240, 245, 255))
    hdrs = [(25, "Sl"), (55, "Medicine"), (350, "Batch"), (430, "Expiry"), (500, "Qty"), (550, "Rate"), (630, "Amount")]
    for x, h in hdrs:
        draw.text((x, 219), h, font=_font(9, bold=True), fill=DARK_BLUE)
    _divider(draw, 233)

    items = [
        ("1", "Azithromycin 500mg Tab (Zithromax)", "BAT2024AB", "06/2026", "5", "28.00", "140.00"),
        ("2", "Cetirizine 10mg Tab (Zyrtec)", "BAT2024CD", "09/2026", "7", "12.00", "84.00"),
        ("3", "Diphenhydramine Syrup 100ml (Benadryl)", "BAT2024EF", "03/2026", "1", "76.00", "76.00"),
        ("4", "Paracetamol 500mg Tab (Crocin)", "BAT2024GH", "12/2026", "10", "8.00", "80.00"),
    ]
    y = 240
    for sl, name, batch, exp, qty, rate, amt in items:
        draw.text((25, y), sl, font=_font(10), fill=BLACK)
        draw.text((55, y), name, font=_font(10), fill=BLACK)
        draw.text((350, y), batch, font=_font(9), fill=MID_GRAY)
        draw.text((430, y), exp, font=_font(9), fill=MID_GRAY)
        draw.text((505, y), qty, font=_font(10), fill=BLACK)
        draw.text((555, y), rate, font=_font(10), fill=BLACK)
        draw.text((635, y), amt, font=_font(10), fill=BLACK)
        y += 22
        _divider(draw, y)

    y += 10
    draw.text((540, y), "Subtotal:", font=_font(11), fill=BLACK)
    draw.text((650, y), "380.00", font=_font(11), fill=BLACK)
    draw.text((540, y + 20), "Discount (2%):", font=_font(11), fill=BLACK)
    draw.text((650, y + 20), "- 7.60", font=_font(11), fill=RED)
    draw.text((540, y + 40), "GST (0%):", font=_font(10), fill=MID_GRAY)
    draw.text((650, y + 40), "0.00", font=_font(10), fill=MID_GRAY)
    draw.rectangle([(530, y + 58), (W - 20, y + 80)], fill=DARK_BLUE)
    draw.text((540, y + 64), "Net Amount Paid", font=_font(11, bold=True), fill=(255, 255, 255))
    draw.text((640, y + 64), "₹372.40", font=_font(11, bold=True), fill=(255, 255, 255))

    draw.text((20, H - 80), "Prescribed medicines dispensed against valid prescription.", font=_font(10), fill=DARK_BLUE)
    draw.text((20, H - 60), "Keep all medicines out of reach of children. Store as directed.", font=_font(9), fill=MID_GRAY)
    draw.text((20, H - 42), "Thank you for choosing MedPlus — Trusted Pharmacy Partner of Apollo Hospitals.", font=_font(9), fill=MID_GRAY)

    out = OUTPUT_DIR / "pharmacy_bill_rajesh_kumar.jpg"
    img.save(out, quality=90)
    print(f"  Saved: {out}")


def generate_unreadable_doc():
    """Generate a blurry/dark unreadable document to demo TC002."""
    img, draw = _canvas()
    draw.rectangle([(0, 0), (W, H)], fill=(30, 30, 30))
    draw.text((100, 200), "HOSPITAL BILL", font=_font(28, bold=True), fill=(60, 60, 60))
    draw.text((80, 260), "Patient Name: ░░░░░░░░░░░░░", font=_font(14), fill=(50, 50, 50))
    draw.text((80, 290), "Amount Due:   ░░░░░░░░░░░░░", font=_font(14), fill=(50, 50, 50))
    for y in range(0, H, 4):
        import random
        x = random.randint(0, W)
        draw.line([(x, y), (x + random.randint(5, 40), y)], fill=(40, 40, 40), width=1)
    out = OUTPUT_DIR / "unreadable_document_blurry.jpg"
    img.save(out, quality=60)
    print(f"  Saved: {out}")


if __name__ == "__main__":
    print("Generating mock medical documents...")
    generate_prescription()
    generate_hospital_bill()
    generate_lab_report()
    generate_pharmacy_bill()
    generate_unreadable_doc()
    print(f"\nAll docs saved to: {OUTPUT_DIR}")
    print("\nTo test the live vision pipeline:")
    print(f"  1. export ANTHROPIC_API_KEY=sk-ant-...")
    print(f"  2. Upload {OUTPUT_DIR}/prescription_rajesh_kumar.jpg")
    print(f"     and {OUTPUT_DIR}/hospital_bill_rajesh_kumar.jpg")
    print(f"     for member EMP001 (Rajesh Kumar), CONSULTATION category")
