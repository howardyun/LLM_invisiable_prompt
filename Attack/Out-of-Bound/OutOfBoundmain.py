# oob_text_poc.py
#
# 运行后会生成两个文件：
#   - oob_poc_base.pdf  : 原始 PDF（未裁剪）
#   - oob_poc_cropped.pdf : 带“越界隐藏文本”的 PoC（可见区被裁剪）

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

from pypdf import PdfReader, PdfWriter  # 如果你装的是 PyPDF2，则改为 from PyPDF2 import PdfReader, PdfWriter


def create_base_pdf(filename: str):
    """
    用 reportlab 生成一个基础 PDF：
    - 一行正常可见文本（位于 CropBox 内）
    - 一行“Out-of-Bound”隐藏文本（画在页面可见区域之外）
    """
    page_width, page_height = A4  # 595 x 842 pt 左右

    c = canvas.Canvas(filename, pagesize=A4)

    # 1) 可见文本：在常规位置
    visible_text = "This is the visible text (what the user sees)."
    c.setFont("Helvetica", 12)
    c.drawString(30 * mm, 260 * mm, visible_text)

    # 2) 越界隐藏文本（Out-of-Bound Text）
    # 思路：把文字画在“正常阅读区域”上方，比如 y 坐标远大于页面高度
    # 很多 PDF viewer 会把它裁掉，但解析工具仍然能读到。
    hidden_text = (
        "HIDDEN OOB TEXT: e.g., phishing URL, fake contract terms, or malicious content."
    )
    # 故意设置一个“超出页面高度”的 y 坐标，比如 1200pt（A4 高度大约 842pt）
    c.setFillColorRGB(1, 0, 0)  # 颜色无所谓，只是便于调试（看不见就无所谓了）
    c.drawString(30 * mm, page_height + 300, hidden_text)

    # 你也可以加更多“超边界”的内容，比如在右侧超宽处：
    hidden_text_right = "ANOTHER HIDDEN OOB TEXT placed far to the right."
    c.drawString(page_width + 300, 200 * mm, hidden_text_right)

    c.showPage()
    c.save()


def crop_pdf_to_hide_oob_text(input_pdf: str, output_pdf: str):
    """
    使用 pypdf / PyPDF2 修改 CropBox：
    - MediaBox 保持原始尺寸（内容都在）
    - CropBox 缩小，只显示页面中间一块，可见内容只剩“正常文字”
    - 越界文本虽然在内容流里，但被裁出可见区域
    """
    reader = PdfReader(input_pdf)
    writer = PdfWriter()

    page = reader.pages[0]

    # 取原始页面尺寸（单位：pt）
    media_box = page.mediabox
    x0, y0, x1, y1 = media_box

    # 你可以根据需要调整“可见区域”大小，这里示例：仅保留下方 2/3 的区域
    # 也可以直接手动给一个 crop 区域，比如 (0, 0, 595, 600)
    new_y1 = y1 * 0.7  # 上方 30% 的内容被裁掉（包括我们塞在更上方的隐藏文本）

    # 设置 CropBox：指定“可见的矩形区域”
    page.cropbox.lower_left = (x0, y0)
    page.cropbox.upper_right = (x1, new_y1)

    writer.add_page(page)

    with open(output_pdf, "wb") as f:
        writer.write(f)


if __name__ == "__main__":
    base_pdf = "oob_poc_base.pdf"
    cropped_pdf = "oob_poc_cropped.pdf"

    # 1. 生成带越界文本的基础 PDF
    create_base_pdf(base_pdf)
    print(f"[+] Created base PDF: {base_pdf}")

    # 2. 修改 CropBox，形成真正的 Out-of-Bound Text PoC
    crop_pdf_to_hide_oob_text(base_pdf, cropped_pdf)
    print(f"[+] Created cropped PoC PDF with OOB text: {cropped_pdf}")





