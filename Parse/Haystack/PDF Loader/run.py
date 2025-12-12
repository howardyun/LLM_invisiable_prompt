#!/usr/bin/env python3
import subprocess
import sys
import os

# ================= 配置区域 =================
# 输入文件路径 (保持相对路径)
INPUT_FILE = "../../PDF/Double_Layer/double_layer.pdf"

# 输出文件夹名称
OUTPUT_DIR = "Output/double_layer"

# 定义需要运行的转换器脚本列表 (按执行顺序)
# 这些脚本名将直接用于生成输出文件名 (例如: PyPDFToDocument.txt)
converters = [
    "PyPDFToDocument.py",
    "MultiFileConverter.py",
    "PDFMinerToDocument.py",
    "UnstructuredFileConverter.py",
    "TiKaDocumentConverter.py"
]


# ===========================================

def run_converter(script_name, input_file, output_folder):
    """
    运行单个转换器脚本
    """
    # 构造输出文件名：脚本名去掉 .py 后加上 .txt
    # 例如: PyPDFToDocument.py -> PyPDFToDocument.txt
    file_basename = os.path.splitext(script_name)[0]
    output_filename = f"{file_basename}.txt"
    output_path = os.path.join(output_folder, output_filename)

    # 构建命令
    cmd = [sys.executable, script_name, "-i", input_file, "-o", output_path]

    print(f"------------------------------------------")
    print(f"正在运行: {script_name}")
    print(f"输出目标: {output_path}")

    try:
        subprocess.run(cmd, check=True)
        print(f"✅ {script_name} 执行成功")
    except subprocess.CalledProcessError:
        print(f"❌ 错误: {script_name} 执行失败")


def main():
    # 1. 打印基础信息
    print("\n[INFO] 开始全量自动化测试...")
    print(f"[INFO] 输入文件: {INPUT_FILE}")
    print(f"[INFO] 输出目录: {OUTPUT_DIR}\n")

    # 2. 自动创建输出目录
    if not os.path.exists(OUTPUT_DIR):
        try:
            os.makedirs(OUTPUT_DIR)
            print(f"[INFO] 已创建输出目录: {OUTPUT_DIR}")
        except OSError as e:
            print(f"❌ 无法创建目录: {e}")
            return

    # 3. 循环运行所有转换器
    total_tools = len(converters)
    for index, tool in enumerate(converters):
        print(f"\n任务 [{index + 1}/{total_tools}]")
        run_converter(tool, INPUT_FILE, OUTPUT_DIR)

    # 4. 结束
    print("\n==========================================")
    print("[SUCCESS] 所有任务执行完毕！")
    print(f"请查看 {OUTPUT_DIR} 文件夹下的结果。")
    print("==========================================")


if __name__ == "__main__":
    main()