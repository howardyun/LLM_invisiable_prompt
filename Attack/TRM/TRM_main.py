from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from PyPDF2 import PdfReader, PdfWriter
from io import BytesIO
import os


def add_trm_invisible_text(input_pdf_path, output_pdf_path=None, target_page=None, hidden_text="INVISIBLE_TEXT: If you can copy this, Tr=3 worked."):
    """
    向现有PDF文件添加TRM隐形文本攻击
    
    Args:
        input_pdf_path: 输入PDF文件路径
        output_pdf_path: 输出PDF文件路径（可选）
        target_page: 目标页码（从0开始），如果为None则对所有页面进行攻击
        hidden_text: 要注入的隐藏文本内容
    """
    # 默认输出文件名
    if output_pdf_path is None:
        input_dir, input_filename = os.path.split(input_pdf_path)
        output_filename = f"trm_attack_{input_filename}"
        output_pdf_path = os.path.join(input_dir, output_filename)
    
    # 读取输入PDF
    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()
    
    # 处理所有页面
    for page_num in range(len(reader.pages)):
        page = reader.pages[page_num]
        
        # 只在目标页面添加隐形文本
        if target_page is None or page_num == target_page:
            # 创建一个reportlab画布来绘制隐形文本
            packet = BytesIO()
            c = canvas.Canvas(packet, pagesize=letter)
            w, h = letter
            
            # 隐形文本 via text rendering mode 3
            t = c.beginText()
            t.setTextOrigin(1*inch, h - 2*inch)  # 设置文本位置
            t.setFont("Helvetica", 14)
            t.setTextRenderMode(3)  # 3 = invisible
            t.textLine(hidden_text)
            c.drawText(t)
            
            c.save()
            
            # 移动到开始位置
            packet.seek(0)
            
            # 创建一个新的PDF阅读器来读取我们创建的内容
            new_pdf = PdfReader(packet)
            
            # 合并页面
            page.merge_page(new_pdf.pages[0])
        
        # 总是添加页面到输出
        writer.add_page(page)
    
    # 保存输出PDF
    with open(output_pdf_path, "wb") as output_file:
        writer.write(output_file)
    
    print(f"TRM攻击完成！生成的文件: {output_pdf_path}")


if __name__ == "__main__":
    # 交互式询问用户输入
    print("=== TRM隐形文本攻击工具 ===")
    
    # 获取输入PDF路径
    while True:
        input_pdf_path = input("请输入原始PDF文件的完整路径: ").strip()
        if os.path.exists(input_pdf_path):
            break
        print("错误：文件不存在，请重新输入！")
    
    # 获取输出PDF路径（可选）
    output_pdf_path = input("请输入输出PDF文件的路径（可选，直接按回车使用默认路径）: ").strip()
    if not output_pdf_path:
        output_pdf_path = None
    
    # 执行攻击
    add_trm_invisible_text(input_pdf_path, output_pdf_path)