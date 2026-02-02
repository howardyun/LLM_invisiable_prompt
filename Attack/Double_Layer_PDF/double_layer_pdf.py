import os
import sys
from pathlib import Path

# 获取当前文件所在目录
current_dir = Path(__file__).parent

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from PyPDF2 import PdfReader, PdfWriter


# 创建PDF文件：从图片创建PDF

def create_image_pdf(image_path, output_file):
    c = canvas.Canvas(output_file, pagesize=letter)
    
    # 添加图片到PDF
    c.drawImage(str(image_path), 50, 500, width=500, height=500)
    
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

    # 合并页面：先是文字层，再是图片层（图片层在文字层之上）
    page_text.merge_page(page_image)

    writer.add_page(page_text)

    # 写入输出文件
    with open(output_file, "wb") as f:
        writer.write(f)


# 只有当文件被直接执行时才运行以下代码
if __name__ == "__main__":
    print("===== 双层PDF生成工具 =====")
    print("该工具将帮助您将图片和文字层PDF合并为双层PDF文件")
    print()
    
    # 交互式输入图片路径
    while True:
        image_path_str = input("请输入图片文件路径: ").strip()
        if not image_path_str:
            print("错误: 图片路径不能为空，请重新输入")
            continue
        
        image_path = Path(image_path_str)
        if not image_path.exists():
            print(f"错误: 图片文件 '{image_path}' 不存在，请重新输入")
            continue
        break
    
    print()
    
    # 交互式输入文字层PDF路径
    while True:
        text_pdf_path_str = input("请输入文字层PDF文件路径: ").strip()
        if not text_pdf_path_str:
            print("错误: 文字层PDF路径不能为空，请重新输入")
            continue
        
        text_pdf_path = Path(text_pdf_path_str)
        if not text_pdf_path.exists():
            print(f"错误: 文字层PDF文件 '{text_pdf_path}' 不存在，请重新输入")
            continue
        break
    
    print()
    
    # 交互式输入输出PDF路径（可选，有默认值）
    output_pdf_path_str = input("请输入输出PDF文件路径 (默认: merged_double_layer.pdf): ").strip()
    if not output_pdf_path_str:
        output_pdf_path = current_dir / "merged_double_layer.pdf"
        print(f"将使用默认输出路径: {output_pdf_path}")
    else:
        output_pdf_path = Path(output_pdf_path_str)
    
    print()
    print("正在处理...")
    print()
    
    # 创建临时图片层PDF
    temp_image_pdf = current_dir / "temp_image_layer.pdf"
    
    # 为图片创建PDF
    create_image_pdf(image_path, str(temp_image_pdf))
    
    # 合并PDF
    merge_pdfs(str(text_pdf_path), str(temp_image_pdf), str(output_pdf_path))
    
    # 删除临时文件
    if temp_image_pdf.exists():
        temp_image_pdf.unlink()
    
    print("[+] 图片层PDF创建成功")
    print(f"[+] 使用的文字层PDF: {text_pdf_path}")
    print(f"[+] 合并后的PDF已保存到: {output_pdf_path}")
    print("[+] 任务完成！")
    
    # 按任意键退出
    input("\n按回车键退出...")