import fitz  # PyMuPDF
import os
import argparse


def analyze_pdf_layer_type(file_path):
    """
    分析 PDF 是纯图片、双层PDF（正常）、还是双层PDF（空白/劣质文本层）
    """
    if not os.path.exists(file_path):
        return f"Error: 文件不存在 - {file_path}"

    try:
        doc = fitz.open(file_path)
    except Exception as e:
        return f"Error: 无法打开文件 - {e}"

    print(f"\n正在分析文件: {os.path.basename(file_path)}")
    print("-" * 60)

    total_pages = len(doc)
    img_only_pages = 0
    empty_layer_pages = 0
    normal_pages = 0

    # 为了效率，只检查前 5 页
    pages_to_check = range(min(total_pages, 5))

    for page_num in pages_to_check:
        page = doc[page_num]

        # 1. 获取页面上的文本 (去除首尾空格)
        text = page.get_text()
        stripped_text = text.strip()

        # 2. 获取页面上的图片数量
        images = page.get_images()
        has_images = len(images) > 0

        # 3. 【核心判断】获取页面引用的字体资源列表
        # 纯图片 PDF 通常没有任何字体资源 (fonts 列表为空)
        # 空白文本层通常会有字体资源，但没有实际字符
        fonts = page.get_fonts()
        has_fonts = len(fonts) > 0

        print(f"Page {page_num + 1}: 图片数={len(images)}, 字体引用={len(fonts)}, 有效文本长度={len(stripped_text)}")

        # --- 判定逻辑 ---

        # 情况 A: 纯图片 PDF
        if has_images and len(stripped_text) == 0 and not has_fonts:
            print(f"  -> [纯图片]: 无文本，无字体资源 -> 需 OCR")
            img_only_pages += 1

        # 情况 B: 带有空白/无效文本层的双层 PDF (你关心的“覆膜”情况)
        elif has_images and len(stripped_text) == 0 and has_fonts:
            print(f"  -> [无效文本层]: 无文本，但有字体资源 (扫描仪空壳层) -> 需强制 OCR")
            empty_layer_pages += 1

        # 情况 C: 正常文档
        elif len(stripped_text) > 5:  # 稍微给个阈值，由1改为5，防止只有页码的情况
            print(f"  -> [正常/双层PDF]: 含有效文本")
            normal_pages += 1

        # 其他情况 (如无图无字空白页)
        else:
            print(f"  -> [空白/未知页]: 可能是只有页码或噪点")

    print("-" * 60)

    # --- 最终建议 ---
    # 只要发现有正常文本页，我们通常倾向于认为这是可搜索 PDF (除非你要求非常严格)
    if normal_pages > 0:
        return "Normal"
    elif empty_layer_pages > 0:
        return "ForceOCR"  # 明确检测到了空壳层
    elif img_only_pages > 0:
        return "ForceOCR"  # 纯图片
    else:
        return "Unknown"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="检测 PDF 类型")
    parser.add_argument("-i", "--input", type=str, default="text_version.pdf", help="输入 PDF 路径")
    args = parser.parse_args()

    result = analyze_pdf_layer_type(args.input)
    print(f"\n【最终建议处理方式】: {result}")
