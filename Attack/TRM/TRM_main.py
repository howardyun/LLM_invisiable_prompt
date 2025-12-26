from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors

out_pdf = "text_render_mode_3_invisible_text_poc.pdf"

c = canvas.Canvas(out_pdf, pagesize=letter)
w, h = letter

# Visible content
c.setFont("Helvetica-Bold", 16)
c.drawString(1*inch, h - 1.0*inch, "PDF PoC: Text rendering mode 3 (invisible text)")

c.setFont("Helvetica", 11)
c.drawString(1*inch, h - 1.5*inch,
             "Inside the rectangle below, there is invisible text (Tr=3). Try selecting/copying there.")

# Visible rectangle showing where the invisible text is placed
box_x, box_y = 1*inch, h - 3.2*inch
box_w, box_h = 6.5*inch, 0.8*inch
c.setStrokeColor(colors.black)
c.setLineWidth(1)
c.rect(box_x, box_y, box_w, box_h, stroke=1, fill=0)

# Invisible text via text rendering mode 3
t = c.beginText()
t.setTextOrigin(box_x + 10, box_y + box_h/2 + 4)
t.setFont("Helvetica", 14)
t.setTextRenderMode(3)  # 3 = invisible
t.textLine("INVISIBLE_TEXT: If you can copy this, Tr=3 worked.")
c.drawText(t)

c.setFont("Helvetica", 11)
c.drawString(1*inch, h - 4.2*inch, "Visible footer text: the invisible line above should not be visible.")
c.showPage()
c.save()

print("Created:", out_pdf)
