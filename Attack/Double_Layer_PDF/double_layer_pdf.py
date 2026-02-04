import os
import sys
from pathlib import Path

# 获取当前文件所在目录
current_dir = Path(__file__).parent

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from PyPDF2 import PdfReader, PdfWriter


# 创建PDF文件：从图片创建PDF（支持多张图片）
def create_image_pdf(image_pages, output_file):
    """
    创建包含多张图片的PDF文件
    :param image_pages: 列表，每个元素是 (image_path, page_num) 元组
    :param output_file: 输出PDF文件路径
    """
    c = canvas.Canvas(output_file, pagesize=letter)
    
    # 按页码排序
    sorted_image_pages = sorted(image_pages, key=lambda x: x[1])
    
    # 为每张图片创建对应的页面
    current_page = 1
    for image_path, page_num in sorted_image_pages:
        # 如果当前页码小于目标页码，创建空白页面
        while current_page < page_num:
            c.showPage()
            current_page += 1
        
        # 在目标页面添加图片
        c.drawImage(str(image_path), 50, 500, width=500, height=500)
        c.showPage()
        current_page += 1
    
    c.save()


# 合并两个PDF：一个是文字层，另一个是图片层
def merge_pdfs(text_pdf, image_pdf, output_file):
    reader_text = PdfReader(text_pdf)
    reader_image = PdfReader(image_pdf)

    writer = PdfWriter()

    # 获取文字层PDF的页数
    num_pages = len(reader_text.pages)

    # 遍历所有页面，进行合并
    for i in range(num_pages):
        # 获取文字层页面
        page_text = reader_text.pages[i]
        
        # 检查图片层PDF是否有对应的页面
        if i < len(reader_image.pages):
            page_image = reader_image.pages[i]
            # 合并页面：图片层在文字层之上
            page_text.merge_page(page_image)
        
        writer.add_page(page_text)

    # 写入输出文件
    with open(output_file, "wb") as f:
        writer.write(f)


# 只有当文件被直接执行时才运行以下代码
if __name__ == "__main__":
    print("===== 双层PDF生成工具 =====")
    print("该工具将帮助您将图片和文字层PDF合并为双层PDF文件")
    print("支持添加多张图片并指定每张图片对应的页码")
    print()
    
    # 交互式输入图片和页码
    image_pages = []
    while True:
        image_path_str = input("请输入图片文件路径 (输入 'done' 结束): ").strip()
        if image_path_str.lower() == "done":
            break
        
        if not image_path_str:
            print("错误: 图片路径不能为空，请重新输入")
            continue
        
        image_path = Path(image_path_str)
        if not image_path.exists():
            print(f"错误: 图片文件 '{image_path}' 不存在，请重新输入")
            continue
        
        # 输入页码
        while True:
            page_num_str = input(f"请输入 '{image_path.name}' 对应的页码: ").strip()
            if not page_num_str.isdigit():
                print("错误: 页码必须是数字，请重新输入")
                continue
            page_num = int(page_num_str)
            if page_num < 1:
                print("错误: 页码必须大于等于 1，请重新输入")
                continue
            break
        
        image_pages.append((image_path, page_num))
        print(f"已添加: {image_path.name} -> 第 {page_num} 页")
        print()
    
    # 检查是否添加了至少一张图片
    if not image_pages:
        print("错误: 至少需要添加一张图片，请重新运行程序")
        input("\n按回车键退出...")
        exit(1)
    
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
    create_image_pdf(image_pages, str(temp_image_pdf))
    
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