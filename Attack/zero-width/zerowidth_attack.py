import fitz  # PyMuPDF
import random
import os

class ZeWInjector:
    def __init__(self, target_words):
        """
        :param target_words: 需要进行注入攻击的关键词列表（不区分大小写）
        """
        # 论文中常用的零宽字符
        self.zew_chars = [
            '\u200B', # Zero Width Space
            '\u200C', # Zero Width Non-Joiner
            '\u200D', # Zero Width Joiner
            '\uFEFF'  # Zero Width No-Break Space
        ]
        # 将目标词转为小写集合，方便快速匹配
        self.target_words = set(word.lower() for word in target_words)

    def inject_word(self, word, mask_type='mask2'):
        """执行零宽字符注入"""
        # 如果单词长度太短或不在目标列表中，不进行处理
        if len(word) < 2 or word.lower() not in self.target_words:
            return word

        char_to_inject = random.choice(self.zew_chars)
        
        if mask_type == 'mask1':
            # Mask1: 仅在单词正中间插入一个字符
            mid = len(word) // 2
            return word[:mid] + char_to_inject + word[mid:]
        
        else:
            # Mask2: 在每个字母之间均匀插入字符
            return char_to_inject.join(list(word))

    def process_pdf(self, input_path, output_path, mask_type='mask2'):
        """
        处理 PDF 并在目标词中注入零宽字符。
        修复：保留原始 PDF 的字体、字号、颜色、表格线、图片等全部排版，
        只对匹配到的目标词做"白底覆盖 → 重写注入文本"的局部替换。
        """
        doc = fitz.open(input_path)
        
        for page in doc:
            # 获取页面上的所有单词及其 bbox
            words = page.get_text("words")  # (x0, y0, x1, y1, text, block_no, line_no, word_no)
            
            for w in words:
                x0, y0, x1, y1, text, block_no, line_no, word_no = w
                
                processed_text = self.inject_word(text, mask_type)
                
                # 如果没改，跳过（不做任何替换）
                if processed_text == text:
                    continue
                
                # 1) 画白底矩形覆盖原词（用 bbox 稍微扩一点避免边缘露边）
                rect = fitz.Rect(x0 - 1, y0 - 1, x1 + 1, y1 + 1)
                page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1), width=0)
                
                # 2) 尝试从原位置的文本块中提取字体/字号，保持视觉一致
                fontsize = 11
                fontname = "helv"
                color = (0, 0, 0)
                try:
                    blocks = page.get_text("dict")["blocks"]
                    for b in blocks:
                        if b["type"] != 0:
                            continue
                        for line in b["lines"]:
                            for span in line["spans"]:
                                sb = span["bbox"]
                                # span bbox 与目标词 bbox 基本重合则匹配
                                overlap_x = abs(sb[0] - x0) < 3 and abs(sb[2] - x1) < 3
                                overlap_y = abs(sb[1] - y0) < 3 and abs(sb[3] - y1) < 3
                                if overlap_x and overlap_y:
                                    fontsize = span.get("size", 11)
                                    # PyMuPDF 的 font name 是字符串，我们映射到内置 14 种
                                    sf = span.get("font", "").lower()
                                    if "bold" in sf:
                                        fontname = "helv-Bold"
                                    elif "italic" in sf or "oblique" in sf:
                                        fontname = "helv-Oblique"
                                    else:
                                        fontname = "helv"
                                    # 颜色 (0-255 -> 0-1)
                                    rgb = span.get("color")
                                    if isinstance(rgb, int):
                                        color = (
                                            ((rgb >> 16) & 0xFF) / 255.0,
                                            ((rgb >> 8) & 0xFF) / 255.0,
                                            (rgb & 0xFF) / 255.0,
                                        )
                                    break
                            else:
                                continue
                            break
                        else:
                            continue
                        break
                except Exception:
                    pass
                
                # 3) 在原位写入注入后的文字
                # 基线取 y1 - (y1 - y0) * 0.22（大约相当于字体的 ascent 比例）
                baseline_y = y0 + (y1 - y0) * 0.82
                page.insert_text(
                    (x0, baseline_y),
                    processed_text,
                    fontsize=fontsize,
                    fontname=fontname,
                    color=color,
                )
        
        doc.save(output_path)
        doc.close()
        print(f"成功！已针对 {len(self.target_words)} 个关键词生成注入后的PDF: {output_path}")

# ================= 使用示例 =================
if __name__ == "__main__":
    # 1. 定义你想要"隐藏"或"破坏"的关键词列表
    my_targets = ["Apple", "Machine", "Intelligence", "Security", "Attack","this"]

    # 2. 初始化注入器
    injector = ZeWInjector(target_words=my_targets)

    # 3. 获取用户输入的PDF路径
    input_pdf = input("请输入PDF文件路径: ").strip()
    output_pdf = input("请输入输出PDF文件路径 (留空则默认保存在同一文件夹下): ").strip()

    # 如果输出路径为空，则生成默认输出路径
    if not output_pdf:
        # 获取输入文件所在目录和文件名
        input_dir = os.path.dirname(input_pdf)
        input_filename = os.path.basename(input_pdf)
        # 分离文件名和扩展名
        name, ext = os.path.splitext(input_filename)
        # 生成新的输出文件名，添加_injected后缀
        output_filename = f"{name}_injected{ext}"
        # 如果输入路径没有目录，则直接使用文件名
        if input_dir:
            output_pdf = os.path.join(input_dir, output_filename)
        else:
            output_pdf = output_filename
        print(f"输出路径未指定，默认保存为: {output_pdf}")

    # 4. 执行处理
    injector.process_pdf(input_pdf, output_pdf, mask_type='mask2')