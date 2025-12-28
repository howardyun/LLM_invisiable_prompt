import os, subprocess
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors

out_dir = "."
os.makedirs(out_dir, exist_ok=True)

def render_png(pdf_path):
    prefix = os.path.splitext(pdf_path)[0]
    subprocess.run(["pdftoppm", "-png", pdf_path, prefix], check=True)
    return prefix + "-1.png"

def pdf_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

# -------------------------
# PoC 1: Tr=3 + tiny text matrix
# -------------------------
p1 = os.path.join(out_dir, "poc_tr3_tiny_matrix.pdf")
c = canvas.Canvas(p1, pagesize=letter)
w, h = letter

c.setFont("Helvetica-Bold", 16)
c.drawString(1*inch, h - 1.0*inch, "PoC #1: Tr=3 + tiny text matrix (bbox ~0)")

c.setFont("Helvetica", 11)
c.drawString(1*inch, h - 1.5*inch,
             "Invisible payload uses Tr=3 and Tm scale ~1e-5. Try selecting/copying inside the box.")

box_x, box_y = 1*inch, h - 3.2*inch
box_w, box_h = 6.5*inch, 0.9*inch
c.setStrokeColor(colors.black); c.setLineWidth(1)
c.rect(box_x, box_y, box_w, box_h, stroke=1, fill=0)
c.circle(box_x + 10, box_y + box_h/2, 1, stroke=0, fill=1)

payload1 = "P1_INVISIBLE_TINY_TM: Tr=3 + Tm scale ~1e-5."
t = c.beginText()
t.setTextTransform(1e-5, 0, 0, 1e-5, box_x + 20, box_y + box_h/2 + 2)
t.setFont("Helvetica", 14)
t.setTextRenderMode(3)
t.textLine(payload1)
c.drawText(t)

c.setFont("Helvetica", 11)
c.drawString(1*inch, h - 4.3*inch, "Visible footer.")
c.showPage()
c.save()

# -------------------------
# PoC 2: Tr=3 + TJ fragmented with extreme offsets
# -------------------------
p2 = os.path.join(out_dir, "poc_tr3_tj_fragmented.pdf")
c = canvas.Canvas(p2, pagesize=letter)
w, h = letter

c.setFont("Helvetica-Bold", 16)
c.drawString(1*inch, h - 1.0*inch, "PoC #2: Tr=3 + TJ fragmentation")

c.setFont("Helvetica", 11)
c.drawString(1*inch, h - 1.5*inch,
             "Payload emitted as TJ array with per-char fragments + extreme offsets under Tr=3.")

box_x, box_y = 1*inch, h - 3.2*inch
box_w, box_h = 6.5*inch, 0.9*inch
c.setStrokeColor(colors.black); c.setLineWidth(1)
c.rect(box_x, box_y, box_w, box_h, stroke=1, fill=0)

# Force creation of /F1 by setting font once
c.setFont("Helvetica", 14)

payload2 = "P2_TJ_FRAG"
frags = list(payload2)
offsets = [900, -300, 1200, -200, 800, 1500, -500, 1000, -250, 1300, -400, 900, -200]
offsets = offsets[:len(frags)-1]

tj_parts = []
for i, ch in enumerate(frags):
    tj_parts.append(f"({pdf_escape(ch)})")
    if i < len(frags) - 1:
        tj_parts.append(str(offsets[i]))
tj_array = "[ " + " ".join(tj_parts) + " ] TJ"

x = box_x + 10
y = box_y + box_h/2 + 2

c._code.append("q")
c._code.append("BT")
c._code.append("/F1 14 Tf")
c._code.append("3 Tr")
c._code.append(f"1 0 0 1 {x:.2f} {y:.2f} Tm")
c._code.append(tj_array)
c._code.append("ET")
c._code.append("Q")

c.setFont("Helvetica", 11)
c.drawString(1*inch, h - 4.3*inch, "Visible footer.")
c.showPage()
c.save()

# -------------------------
# PoC 3: Tr=3 inside /Artifact marked content
# -------------------------
p3 = os.path.join(out_dir, "poc_tr3_marked_content_artifact.pdf")
c = canvas.Canvas(p3, pagesize=letter)
w, h = letter

c.setFont("Helvetica-Bold", 16)
c.drawString(1*inch, h - 1.0*inch, "PoC #3: Tr=3 wrapped in /Artifact marked content")

c.setFont("Helvetica", 11)
c.drawString(1*inch, h - 1.5*inch,
             "Payload is inside /Artifact BMC ... EMC and Tr=3.")

box_x, box_y = 1*inch, h - 3.2*inch
box_w, box_h = 6.5*inch, 0.9*inch
c.setStrokeColor(colors.black); c.setLineWidth(1)
c.rect(box_x, box_y, box_w, box_h, stroke=1, fill=0)

c.setFont("Helvetica", 14)
payload3 = "P3_ARTIFACT_TR3: invisible text in /Artifact BMC ... EMC"
x = box_x + 10
y = box_y + box_h/2 + 2

c._code.append("q")
c._code.append("/Artifact BMC")
c._code.append("BT")
c._code.append("/F1 14 Tf")
c._code.append("3 Tr")
c._code.append(f"1 0 0 1 {x:.2f} {y:.2f} Tm")
c._code.append(f"({pdf_escape(payload3)}) Tj")
c._code.append("ET")
c._code.append("EMC")
c._code.append("Q")

c.setFont("Helvetica", 11)
c.drawString(1*inch, h - 4.3*inch, "Visible footer.")
c.showPage()
c.save()

print("Generated:", p1, p2, p3)
