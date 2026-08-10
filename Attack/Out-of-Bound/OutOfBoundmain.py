# oob_text_poc.py
#
# 运行后会生成两个文件：
#   - oob_poc_base.pdf  : 添加了越界隐藏文本的原始 PDF（未裁剪）
#   - oob_poc_cropped.pdf : 带"越界隐藏文本"的 PoC（可见区被裁剪）

import fitz  # PyMuPDF
from pypdf import PdfReader, PdfWriter


def _escape_pdf_string(text: str) -> str:
    """转义 PDF 字符串中的特殊字符"""
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def add_hidden_text_to_pdf(input_pdf_path: str, output_pdf_path: str, target_page: int = None, hidden_text: str = "HIDDEN and invisible."):
    """
    使用 PyMuPDF 直接操作内容流，在页面 MediaBox 之外注入越界隐藏文本。

    修复：原实现使用 ReportLab + pypdf merge_page，但 merge_page 会将 overlay
    内容裁剪到 MediaBox 范围内，导致越界文本（y = page_height + 300）被丢弃。
    现改为直接用 doc.update_stream() 将越界文本写入内容流，绕过裁剪。

    Args:
        input_pdf_path: 输入PDF文件路径
        output_pdf_path: 输出PDF文件路径
        target_page: 目标页码（从0开始），如果为None则对所有页面进行攻击
        hidden_text: 要注入的隐藏文本内容
    """
    doc = fitz.open(input_pdf_path)

    for page_num in range(len(doc)):
        if target_page is not None and page_num != target_page:
            continue

        page = doc[page_num]
        pw, ph = page.rect.width, page.rect.height

        # 注册 /helv 字体（Helvetica），确保内容流中的 /helv 有对应资源
        page.insert_font(fontname="helv")

        # 读取现有内容流（page.read_contents 会合并所有内容流为一段 bytes）
        existing = page.read_contents()

        # 转义隐藏文本中的 PDF 特殊字符
        safe_text = _escape_pdf_string(hidden_text)
        safe_text_right = _escape_pdf_string(f"EXTRA: {hidden_text}")

        # 构建越界文本块（包裹在 q/Q 中，重置 CTM 为单位矩阵）
        # 坐标在 MediaBox 之外：
        #   顶部越界：y = ph + 300（页面顶部上方 300pt）
        #   右侧越界：x = pw + 300（页面右侧外 300pt）
        oob_block = (
            "q\n"
            "1 0 0 1 0 0 cm\n"
            "BT\n"
            "/helv 12 Tf\n"
            f"85.05 {ph + 300:.2f} Td\n"
            f"({safe_text}) Tj\n"
            "ET\n"
            "Q\n"
            "q\n"
            "1 0 0 1 0 0 cm\n"
            "BT\n"
            "/helv 12 Tf\n"
            f"{pw + 300:.2f} 566.93 Td\n"
            f"({safe_text_right}) Tj\n"
            "ET\n"
            "Q\n"
        ).encode("latin-1")

        # 将越界文本块插入到现有内容之前（确保 CTM 为默认单位矩阵）
        new_content = oob_block + existing

        # 更新内容流：将合并后的内容写入第一个 xref，清空其余 xref
        xrefs = page.get_contents()
        if xrefs:
            doc.update_stream(xrefs[0], new_content)
            for xref in xrefs[1:]:
                doc.update_stream(xref, b"")
        else:
            # 页面无内容流，先创建一个空的再更新
            page.insert_text((0, 0), " ", fontsize=0.1, fontname="helv")
            xrefs = page.get_contents()
            if xrefs:
                doc.update_stream(xrefs[0], new_content)

    doc.save(output_pdf_path)
    doc.close()


def crop_pdf_to_hide_oob_text(input_pdf: str, output_pdf: str, target_page: int = None):
    """
    使用 pypdf 设置 CropBox：
    - MediaBox 保持原始尺寸（内容都在）
    - CropBox 与 MediaBox 一致，不裁切任何正常页面内容
    - 越界文本（page_height+300 和 page_width+300）已在可见区域外，天然不可见

    Args:
        input_pdf: 输入PDF文件路径
        output_pdf: 输出PDF文件路径
        target_page: 目标页码（从0开始），如果为None则对所有页面进行裁剪
    """
    reader = PdfReader(input_pdf)
    writer = PdfWriter()

    # 遍历所有页面
    for page_num in range(len(reader.pages)):
        page = reader.pages[page_num]

        # 只在目标页面进行裁剪
        if target_page is None or page_num == target_page:
            # 取原始页面尺寸（单位：pt）
            media_box = page.mediabox
            x0, y0, x1, y1 = media_box

            # 隐藏文本已经绘制在 page_height+300 和 page_width+300 处，
            # 远超页面可见范围，无需缩小 CropBox。
            # CropBox 保持与 MediaBox 一致，不裁切任何正常页面内容。
            page.cropbox.lower_left = (x0, y0)
            page.cropbox.upper_right = (x1, y1)

        # 总是添加页面到输出
        writer.add_page(page)

    with open(output_pdf, "wb") as f:
        writer.write(f)


if __name__ == "__main__":
    # 获取用户输入的原始 PDF 文件路径
    input_pdf_path = input("请输入原始 PDF 文件的路径：").strip()

    # 定义输出文件名，与 README.md 中描述的一致
    base_pdf = "oob_poc_base.pdf"
    cropped_pdf = "oob_poc_cropped.pdf"

    # 1. 读取用户传入的 PDF 并添加越界隐藏文本
    add_hidden_text_to_pdf(input_pdf_path, base_pdf)
    print(f"[+] Created base PDF with OOB text: {base_pdf}")

    # 2. 修改 CropBox，形成真正的 Out-of-Bound Text PoC
    crop_pdf_to_hide_oob_text(base_pdf, cropped_pdf)
    print(f"[+] Created cropped PoC PDF with OOB text: {cropped_pdf}")

    print("\n[+] 任务完成！已生成以下文件：")
    print(f"   - {base_pdf}: 基础 PDF 文件，包含正常文本和越界隐藏文本")
    print(f"   - {cropped_pdf}: 裁剪后的 PDF 文件，只显示正常文本，隐藏越界文本")
