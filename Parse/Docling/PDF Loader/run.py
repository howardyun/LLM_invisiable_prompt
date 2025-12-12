#!/usr/bin/env python3
import subprocess
import sys
import os

# 定义任务列表：(输入文件路径, 输出文件夹路径)
# 对应 batch 文件中的 [1/13] 到 [13/13]
tasks = [
    ("../../PDF/Homoglyph_Characters/text_version.pdf", "Output/homoglyph_characters"),
    ("../../PDF/image_version.pdf", "Output/image"),
    ("../../PDF/Double_Layer/double_layer.pdf", "Output/double_layer"),
    ("../../PDF/Zero_Width/metadata/zero_width.pdf", "Output/zero_width/metadata"),
    ("../../PDF/Zero_Width/text/zero_width.pdf", "Output/zero_width/text"),
    ("../../PDF/Out_of_Box/oob_poc_base.pdf", "Output/out_of_box/base"),
    ("../../PDF/Out_of_Box/oob_poc_cropped.pdf", "Output/out_of_box/cropped"),
    ("../../PDF/Transparent_Injection/injected_document_Trans.pdf", "Output/transparent_injection"),
    ("../../PDF/Hidden_OCG/ocg_poc.pdf", "Output/hidden_ocg"),
    ("../../PDF/Zero_Size/font_0.pdf", "Output/zero_size/font_0"),
    ("../../PDF/Zero_Size/font_001.pdf", "Output/zero_size/font_001"),
    ("../../PDF/Zero_Size/font_1.pdf", "Output/zero_size/font_1"),
    ("../../PDF/Word_Shift/pdf_poc.pdf", "Output/word_shift")
]


def run_docling(input_file, output_folder, force_ocr=False):
    """
    执行 Docling.py 命令
    """
    # 确定输出文件名
    filename = "DoclingLoader_force_ocr.txt" if force_ocr else "DoclingLoader.txt"
    output_path = os.path.join(output_folder, filename)

    # 构建命令
    # 使用 sys.executable 确保使用当前激活环境的 python 解释器
    cmd = [sys.executable, "Docling.py", "-i", input_file, "-o", output_path]

    if force_ocr:
        cmd.append("--ocr")

    # 打印进度提示
    mode_str = "[强制OCR]" if force_ocr else "[标准模式]"
    print(f"{mode_str} 正在处理: {input_file} -> {output_path}")

    try:
        # 执行命令
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ 错误: 处理 {input_file} 失败。")
        # 如果你不希望单个错误中断整个脚本，可以将下面的 raise 注释掉
        # raise e


def main():
    total_tasks = len(tasks)

    print("\n=======================================================")
    print(f"开始执行自动化任务 (共 {total_tasks * 2} 个步骤)")
    print("=======================================================\n")

    # 第一阶段：标准运行
    print("--- 阶段 1: 标准 Docling 运行 ---")
    for index, (inp, out) in enumerate(tasks):
        print(f"[{index + 1}/{total_tasks}]", end=" ")
        run_docling(inp, out, force_ocr=False)
        print()  # 空行

    print("\n=======================================================")
    print("[配置切换] 强制 OCR 模式")
    print("=======================================================\n")

    # 第二阶段：强制 OCR 运行
    print("--- 阶段 2: 强制 OCR 运行 ---")
    for index, (inp, out) in enumerate(tasks):
        print(f"[{index + 1}/{total_tasks}]", end=" ")
        run_docling(inp, out, force_ocr=True)
        print()  # 空行

    print("=======================================================")
    print("所有任务已执行完毕。")
    print("=======================================================")


if __name__ == "__main__":
    main()