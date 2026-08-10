import fitz  # PyMuPDF
import re
import sys


def safe_print(text):
    """安全打印函数，处理编码问题"""
    try:
        print(text)
    except UnicodeEncodeError:
        # 如果遇到编码问题，过滤掉无法编码的字符
        safe_text = text.encode('gbk', 'ignore').decode('gbk')
        print(safe_text)


def detect_zew_injection(file_path):
    """
    检测 PDF 文件中是否存在零宽字符注入攻击
    """
    # 定义需要检测的零宽字符范围，包括可能的转换后字符
    zew_pattern = re.compile(r'[\u200B\u200C\u200D\uFEFF\xb7]')
    
    # 统计信息
    total_injected_words = 0
    injection_details = []

    try:
        doc = fitz.open(file_path)
        safe_print(f"--- 正在分析文件: {file_path} ---")

        for page_num, page in enumerate(doc):
            # 提取页面上的所有单词
            words = page.get_text("words")
            
            for w in words:
                x0, y0, x1, y1, text, block_no, line_no, word_no = w
                
                # 寻找匹配零宽字符的单词
                found_chars = zew_pattern.findall(text)
                if found_chars:
                    total_injected_words += 1
                    # 记录检测到的详细信息：页码、坐标、视觉文本、包含的特殊字符编码
                    clean_text = text.replace('\u200B','[ZWSP]').replace('\u200C','[ZWNJ]').replace('\u200D','[ZWJ]').replace('\uFEFF','[ZWNBSP]').replace('\xb7','[ZW-TO-B7]')
                    
                    injection_details.append({
                        "page": page_num + 1,
                        "visual_text": text.encode('ascii', 'ignore').decode('ascii'), # 过滤掉不可见字符看原始词
                        "encoded_text": clean_text,
                        "chars_found": [hex(ord(c)) for c in found_chars]
                    })

        doc.close()

        # 输出检测报告
        if total_injected_words > 0:
            safe_print(f"【警告】检测到攻击！在该文件中发现 {total_injected_words} 处零宽字符注入。")
            print("-" * 50)
            for detail in injection_details[:10]: # 仅展示前10处
                safe_print(f"页码 {detail['page']} | 视觉显示: {detail['visual_text']} | 编码构造: {detail['encoded_text']}")
            if len(injection_details) > 10:
                safe_print(f"... 以及其他 {len(injection_details) - 10} 处修改。")
        else:
            safe_print("【安全】未检测到零宽字符注入。")

    except Exception as e:
        safe_print(f"处理失败: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        safe_print("使用方法: python zerowidth_detector.py <PDF文件路径>")
        sys.exit(1)
    
    pdf_file_path = sys.argv[1]
    detect_zew_injection(pdf_file_path)