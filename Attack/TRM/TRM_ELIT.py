import os, subprocess
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from PyPDF2 import PdfReader, PdfWriter
from io import BytesIO


def pdf_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def add_tr3_tiny_matrix(input_pdf_path, output_pdf_path=None):
    """向现有PDF添加Tr=3 + tiny text matrix攻击"""
    # 默认输出文件名
    if output_pdf_path is None:
        input_dir, input_filename = os.path.split(input_pdf_path)
        output_filename = f"elit_tr3_tiny_matrix_{input_filename}"
        output_pdf_path = os.path.join(input_dir, output_filename)
    
    # 读取输入PDF
    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()
    
    # 处理所有页面
    for page_num in range(len(reader.pages)):
        page = reader.pages[page_num]
        
        # 创建一个reportlab画布来绘制隐形文本
        packet = BytesIO()
        c = canvas.Canvas(packet, pagesize=letter)
        w, h = letter
        
        payload1 = "P1_INVISIBLE_TINY_TM: Tr=3 + Tm scale ~1e-5."
        t = c.beginText()
        t.setTextTransform(1e-5, 0, 0, 1e-5, 1*inch, h - 2*inch)
        t.setFont("Helvetica", 14)
        t.setTextRenderMode(3)
        t.textLine(payload1)
        c.drawText(t)
        
        c.save()
        
        # 移动到开始位置
        packet.seek(0)
        
        # 创建一个新的PDF阅读器来读取我们创建的内容
        new_pdf = PdfReader(packet)
        
        # 合并页面
        page.merge_page(new_pdf.pages[0])
        writer.add_page(page)
    
    # 保存输出PDF
    with open(output_pdf_path, "wb") as output_file:
        writer.write(output_file)
    
    print(f"Tr=3 + tiny text matrix攻击完成！生成的文件: {output_pdf_path}")


def add_tr3_tj_fragmented(input_pdf_path, output_pdf_path=None):
    """向现有PDF添加Tr=3 + TJ fragmented with extreme offsets攻击"""
    # 默认输出文件名
    if output_pdf_path is None:
        input_dir, input_filename = os.path.split(input_pdf_path)
        output_filename = f"elit_tr3_tj_fragmented_{input_filename}"
        output_pdf_path = os.path.join(input_dir, output_filename)
    
    # 读取输入PDF
    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()
    
    # 处理所有页面
    for page_num in range(len(reader.pages)):
        page = reader.pages[page_num]
        
        # 创建一个reportlab画布来绘制隐形文本
        packet = BytesIO()
        c = canvas.Canvas(packet, pagesize=letter)
        w, h = letter
        
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
        
        x = 1*inch
        y = h - 2*inch
        
        c._code.append("q")
        c._code.append("BT")
        c._code.append("/F1 14 Tf")
        c._code.append("3 Tr")
        c._code.append(f"1 0 0 1 {x:.2f} {y:.2f} Tm")
        c._code.append(tj_array)
        c._code.append("ET")
        c._code.append("Q")
        
        c.save()
        
        # 移动到开始位置
        packet.seek(0)
        
        # 创建一个新的PDF阅读器来读取我们创建的内容
        new_pdf = PdfReader(packet)
        
        # 合并页面
        page.merge_page(new_pdf.pages[0])
        writer.add_page(page)
    
    # 保存输出PDF
    with open(output_pdf_path, "wb") as output_file:
        writer.write(output_file)
    
    print(f"Tr=3 + TJ fragmented攻击完成！生成的文件: {output_pdf_path}")


def add_tr3_artifact(input_pdf_path, output_pdf_path=None):
    """向现有PDF添加Tr=3 inside /Artifact marked content攻击"""
    # 默认输出文件名
    if output_pdf_path is None:
        input_dir, input_filename = os.path.split(input_pdf_path)
        output_filename = f"elit_tr3_artifact_{input_filename}"
        output_pdf_path = os.path.join(input_dir, output_filename)
    
    # 读取输入PDF
    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()
    
    # 处理所有页面
    for page_num in range(len(reader.pages)):
        page = reader.pages[page_num]
        
        # 创建一个reportlab画布来绘制隐形文本
        packet = BytesIO()
        c = canvas.Canvas(packet, pagesize=letter)
        w, h = letter
        
        c.setFont("Helvetica", 14)
        payload3 = "P3_ARTIFACT_TR3: invisible text in /Artifact BMC ... EMC"
        x = 1*inch
        y = h - 2*inch
        
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
        
        c.save()
        
        # 移动到开始位置
        packet.seek(0)
        
        # 创建一个新的PDF阅读器来读取我们创建的内容
        new_pdf = PdfReader(packet)
        
        # 合并页面
        page.merge_page(new_pdf.pages[0])
        writer.add_page(page)
    
    # 保存输出PDF
    with open(output_pdf_path, "wb") as output_file:
        writer.write(output_file)
    
    print(f"Tr=3 inside /Artifact攻击完成！生成的文件: {output_pdf_path}")


if __name__ == "__main__":
    # 交互式询问用户输入
    print("=== TRM ELIT隐形文本攻击工具 ===")
    
    # 获取攻击类型
    attack_types = {
        "1": "tiny_matrix",
        "2": "tj_fragmented",
        "3": "artifact"
    }
    
    while True:
        print("\n请选择攻击类型：")
        print("1. Tr=3 + tiny text matrix")
        print("2. Tr=3 + TJ fragmented with extreme offsets")
        print("3. Tr=3 inside /Artifact marked content")
        
        choice = input("请输入数字 (1-3): ").strip()
        if choice in attack_types:
            attack_type = attack_types[choice]
            break
        print("错误：无效的选择，请重新输入！")
    
    # 获取输入PDF路径
    while True:
        input_pdf_path = input("\n请输入原始PDF文件的完整路径: ").strip()
        if os.path.exists(input_pdf_path):
            break
        print("错误：文件不存在，请重新输入！")
    
    # 获取输出PDF路径（可选）
    output_pdf_path = input("请输入输出PDF文件的路径（可选，直接按回车使用默认路径）: ").strip()
    if not output_pdf_path:
        output_pdf_path = None
    
    # 执行相应的攻击
    print(f"\n正在执行{attack_type}攻击...")
    
    if attack_type == "tiny_matrix":
        add_tr3_tiny_matrix(input_pdf_path, output_pdf_path)
    elif attack_type == "tj_fragmented":
        add_tr3_tj_fragmented(input_pdf_path, output_pdf_path)
    elif attack_type == "artifact":
        add_tr3_artifact(input_pdf_path, output_pdf_path)
    else:
        print(f"未知的攻击类型: {attack_type}")