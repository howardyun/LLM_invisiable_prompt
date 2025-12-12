#!/usr/bin/env python3
import subprocess
import sys
import os
import argparse

# ================= 配置区域 =================
# 输入文件 (相对路径)
INPUT_FILE = "../../PDF/Zero_Width/text/zero_width.pdf"

# 输出根目录
OUTPUT_DIR = "Output/zero_width/text"

# SmartPDF API 地址
SMART_API_BASE = "http://localhost:5001/api/parseDocument?renderFormat=all"


# ===========================================

def run_cmd(script_name, output_name, extra_args=None):
    """通用命令执行函数"""
    output_path = os.path.join(OUTPUT_DIR, output_name)

    cmd = [sys.executable, script_name, "-i", INPUT_FILE, "-o", output_path]

    if extra_args:
        cmd.extend(extra_args)

    print(f"   -> 正在运行: {script_name}")
    print(f"      输出: {output_path}")

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        print(f"   ❌ 错误: {script_name} 执行失败")


def stage_base():
    """第一组: LlamaIndex-base 环境"""
    print("\n[环境要求: LlamaIndex-base] 开始执行基础加载器...")

    # 1. PyMuPDFLoader
    run_cmd("PyMuPDFLoader.py", "PyMuPDFLoader.txt")

    # 2. PDFLoader (Standard)
    run_cmd("PDFLoader.py", "StandardPDF.txt")

    # 3. UnstructuredLoader
    run_cmd("UnstructuredLoader.py", "UnstructuredLoader.txt")

    # 4. PDFTableLoader (参数: -p "all")
    run_cmd("PDFTableLoader.py", "PDFTable.txt", ["-p", "all"])

    # 5. PaddleOCRLoader (参数: --lang en)
    run_cmd("PaddleOCRLoader.py", "PaddleOCR.txt", ["--lang", "en"])

    # 6. SmartPDFLoader (普通)
    run_cmd("SmartPDFLoader.py", "SmartPDFLoader.txt", ["--api", SMART_API_BASE])

    # 7. SmartPDFLoader (带 OCR)
    # 注意: URL 参数拼接
    ocr_api = f"{SMART_API_BASE}&applyOcr=yes"
    run_cmd("SmartPDFLoader.py", "SmartPDFLoader_apply_ocr.txt", ["--api", ocr_api])


def stage_nougat():
    """第二组: LlamaIndex-nougat 环境"""
    print("\n[环境要求: LlamaIndex-nougat] 开始执行 Nougat...")
    run_cmd("NougatOCRLoader.py", "NougatOCR.txt")


def stage_marker():
    """第三组: LlamaIndex-marker 环境"""
    print("\n[环境要求: LlamaIndex-marker] 开始执行 Marker...")
    run_cmd("PDFMarkerLoader.py", "PDFMarkerLoader.txt")


def stage_docling():
    """第四组: LlamaIndex-docling 环境"""
    print("\n[环境要求: LlamaIndex-docling] 开始执行 Docling...")
    run_cmd("DoclingLoader.py", "DoclingLoader.txt")


def main():
    # 自动创建目录
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        print(f"[INFO] 已创建输出目录: {OUTPUT_DIR}")

    parser = argparse.ArgumentParser(description="LlamaIndex PDF 解析任务运行器")
    parser.add_argument("--stage", choices=["base", "nougat", "marker", "docling"],
                        help="指定要运行的阶段 (对应不同的 Conda 环境)")
    args = parser.parse_args()

    # 如果没有提供命令行参数，显示交互式菜单
    if not args.stage:
        print("\n检测到此脚本包含需要不同环境的任务。请选择当前激活环境对应的任务：")
        print("1. LlamaIndex-base   (包含 PyMuPDF, Unstructured, PaddleOCR, SmartPDF 等)")
        print("2. LlamaIndex-nougat (包含 NougatOCRLoader)")
        print("3. LlamaIndex-marker (包含 PDFMarkerLoader)")
        print("4. LlamaIndex-docling (包含 DoclingLoader)")
        print("0. 退出")

        choice = input("\n请输入数字 [1-4]: ").strip()
        if choice == "1":
            stage_base()
        elif choice == "2":
            stage_nougat()
        elif choice == "3":
            stage_marker()
        elif choice == "4":
            stage_docling()
        else:
            print("退出。")
    else:
        # 命令行模式直接运行
        if args.stage == "base":
            stage_base()
        elif args.stage == "nougat":
            stage_nougat()
        elif args.stage == "marker":
            stage_marker()
        elif args.stage == "docling":
            stage_docling()


if __name__ == "__main__":
    main()