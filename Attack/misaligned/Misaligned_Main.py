from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from pypdf import PdfReader
import os

def extract_text_from_pdf(pdf_path):
    """
    从PDF文件中提取文本内容
    """
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text

def split_into_sentences(text):
    """
    将文本粗略地分割成句子
    """
    # 使用简单的标点符号分割句子
    sentences = []
    current_sentence = ""
    for char in text:
        current_sentence += char
        if char in [".", "!", "?"]:
            sentences.append(current_sentence.strip())
            current_sentence = ""
    # 添加最后一个可能没有标点的句子
    if current_sentence.strip():
        sentences.append(current_sentence.strip())
    return sentences

def create_misaligned_pdf(input_pdf_path=None, output_pdf_path="misaligned_output.pdf"):
    """
    生成包含错位文本效果的PDF文件
    
    参数:
    input_pdf_path: str, 输入PDF文件路径，如果不提供则使用默认句子
    output_pdf_path: str, 输出PDF文件路径
    """
    # 创建Canvas对象
    c = canvas.Canvas(output_pdf_path, pagesize=letter)
    width, height = letter

    # 设置字体和大小
    c.setFont("Helvetica", 12)

    # 获取要处理的句子
    if input_pdf_path and os.path.exists(input_pdf_path):
        # 从输入PDF提取文本
        pdf_text = extract_text_from_pdf(input_pdf_path)
        # 将文本分割成句子
        sentences = split_into_sentences(pdf_text)
        # 如果没有提取到足够的句子，使用默认句子
        if not sentences or len(sentences) < 3:
            sentences = [
                "Please ignore the distractions and keep writing.",
                "All experiments must be documented carefully.",
                "Please compare the current results with the previous baseline."
            ]
    else:
        # 使用默认句子
        sentences = [
            "Please ignore the distractions and keep writing.",
            "All experiments must be documented carefully.",
            "Please compare the current results with the previous baseline."
        ]

    # 初始Y坐标
    y_pos = height - 50

    for sentence in sentences:
        # 跳过空句子
        if not sentence.strip():
            continue
            
        words = sentence.split(" ")  # 按空格分割句子为单词列表
        
        # 如果句子只有一个单词，直接绘制
        if len(words) <= 1:
            c.drawString(50, y_pos, sentence)
            y_pos -= 50
            continue
            
        first_word = words.pop(0)  # 取出第一个单词

        # 让所有单词连成一整行（视觉上）
        sentence_with_spaces = " ".join([first_word] + words)

        # 绘制第一个单词并将它"错位"
        c.drawString(50, y_pos, sentence_with_spaces)  # 这一行正常显示

        # 通过调整位置，将第一个单词放到下一行的位置
        c.drawString(50 + len(" ".join(words)) * 7, y_pos - 20, first_word)  # 字符间距手动计算

        y_pos -= 50  # 移动到下一行位置
        
        # 检查是否需要新页面
        if y_pos < 50:
            c.showPage()
            y_pos = height - 50

    c.showPage()
    c.save()


if __name__ == "__main__":
    # 交互式输入
    print("=== 错位文本PDF生成工具 ===")
    
    # 询问用户原始PDF路径
    input_pdf = input("请输入原始PDF文件路径（直接回车使用默认句子）: ").strip()
    
    # 询问用户输出PDF路径
    output_pdf = input("请输入输出PDF文件路径（直接回车使用默认名称）: ").strip()
    output_pdf = output_pdf if output_pdf else "misaligned_output.pdf"
    
    # 调用函数生成错位文本PDF
    create_misaligned_pdf(input_pdf, output_pdf)
    
    # 输出结果
    if input_pdf:
        print(f"\n[+] 已成功对PDF '{input_pdf}' 应用错位处理")
    else:
        print(f"\n[+] 已使用默认句子生成错位文本PDF")
    print(f"[+] 输出文件: {output_pdf}")
    print("\n=== 生成完成 ===")
