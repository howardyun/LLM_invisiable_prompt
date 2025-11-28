from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from PyPDF2 import PdfReader, PdfWriter


# 创建PDF文件：文字层和图片层
def create_pdf(output_file):
    c = canvas.Canvas(output_file, pagesize=letter)

    # 文字层（这是在文字层中绘制的文字）
    c.setFont("Helvetica", 12)
    c.drawString(100, 750, "This is the text layer.")

    # 图片层（添加一张图片作为背景）
    c.drawImage("case3.png", 50, 500, width=500, height=500)  # 使用你自己的图片路径

    c.showPage()
    c.save()


# 合并两个PDF：一个是文字层，另一个是图片层
def merge_pdfs(text_pdf, image_pdf, output_file):
    reader_text = PdfReader(text_pdf)
    reader_image = PdfReader(image_pdf)

    writer = PdfWriter()

    # 假设两个PDF页面相同，合并它们
    page_text = reader_text.pages[0]
    page_image = reader_image.pages[0]

    # 合并页面：先是文字层，再是图片层
    page_image.merge_page(page_text)

    writer.add_page(page_image)

    # 写入输出文件
    with open(output_file, "wb") as f:
        writer.write(f)


# 创建文字层PDF
create_pdf("text_layer.pdf")

# 创建图片层PDF
create_pdf("image_layer.pdf")

# 合并PDF，得到最终的带有不同层的PDF
merge_pdfs("text_layer.pdf", "image_layer.pdf", "final_output.pdf")
