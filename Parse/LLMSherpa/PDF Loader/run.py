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

# OCR 模式下使用的 API 地址
OCR_API_URL = "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"


def run_sherpa(input_file, output_folder, use_ocr_api=False):
    """
    执行 LLMSherpa.py 命令
    """
    # 1. 确定输出文件名
    # 标准模式: SherpaResult.txt
    # OCR 模式: SherpaResult_apply_ocr.txt
    filename = "SherpaResult_apply_ocr.txt" if use_ocr_api else "SherpaResult.txt"
    output_path = os.path.join(output_folder, filename)

    # 2. 构建基础命令
    # 使用 sys.executable 确保使用当前激活环境的 python
    cmd = [sys.executable, "LLMSherpa.py", "-i", input_file, "-o", output_path]

    # 3. 如果是 OCR 模式，追加 --api 参数
    if use_ocr_api:
        cmd.extend(["--api", OCR_API_URL])

    # 4. 打印进度提示
    mode_str = "[强制OCR API]" if use_ocr_api else "[标准模式]"
    print(f"{mode_str} 正在处理: {input_file} -> {output_path}")

    try:
        # 执行命令
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        print(f"❌ 错误: 处理 {input_file} 失败。")


def main():
    total_tasks = len(tasks)

    print("\n=======================================================")
    print(f"开始执行 LLMSherpa 任务 (共 {total_tasks * 2} 个步骤)")
    print("=======================================================\n")

    # --- 阶段 1: 标准运行 ---
    print("--- 阶段 1: 标准 LLMSherpa 运行 (无 API) ---")
    for index, (inp, out) in enumerate(tasks):
        print(f"[{index + 1}/{total_tasks}]", end=" ")
        run_sherpa(inp, out, use_ocr_api=False)
        print()

    print("\n=======================================================")
    print("[配置切换] 强制 OCR (调用本地 API)")
    print("=======================================================\n")

    # --- 阶段 2: 强制 OCR 运行 (带 API 参数) ---
    print("--- 阶段 2: 强制 OCR 运行 ---")
    for index, (inp, out) in enumerate(tasks):
        print(f"[{index + 1}/{total_tasks}]", end=" ")
        run_sherpa(inp, out, use_ocr_api=True)
        print()

    print("=======================================================")
    print("所有任务已执行完毕。")
    print("=======================================================")


if __name__ == "__main__":
    main()