import os
import sys
import subprocess
from pathlib import Path

# ================= 配置区域 =================
# 使用当前运行此脚本的 Python 解释器
PYTHON_EXE = sys.executable

# 设置输入文件路径 (只需要修改这一个路径即可)
INPUT_FILE = Path("../PDF/Zero_Width/zero_width.pdf")

# 【自动获取】输入目录直接设为输入文件所在的文件夹
INPUT_DIR = INPUT_FILE.parent

# 设置输出文件夹名称
OUTPUT_DIR = Path("Output/zero_width/zero_width")


# ===========================================

def run_command(script_name, input_target, output_filename):
    """
    辅助函数：运行单个 Python 脚本并打印日志
    """
    script_path = Path(script_name)
    output_path = OUTPUT_DIR / output_filename

    print(f"\n==========================================")
    print(f"运行 {script_path.stem}...")
    print(f"==========================================")

    if not script_path.exists():
        print(f"[SKIP] 未找到 {script_name}，跳过。")
        return

    # 构建命令
    cmd = [
        PYTHON_EXE,
        str(script_path),
        "-i", str(input_target),
        "-o", str(output_path)
    ]

    try:
        # 运行命令，check=True 会在命令出错时抛出异常
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] {script_name} 执行失败，错误代码: {e.returncode}")
    except Exception as e:
        print(f"[ERROR] 发生未知错误: {e}")


def main():
    # 确保输出目录存在
    if not OUTPUT_DIR.exists():
        print(f"[INFO] 创建输出目录: {OUTPUT_DIR}")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] 开始自动化测试...")
    print(f"[INFO] 输入文件: {INPUT_FILE}")
    print(f"[INFO] 输入目录 (自动识别): {INPUT_DIR}")
    print(f"[INFO] 输出目录: {OUTPUT_DIR}")

    # 1. 运行 PyPDFLoader (基础解析)
    run_command("PyPDFLoader.py", INPUT_FILE, "PyPDFLoader.txt")

    # 2. 运行 PyMuPDF (极速解析)
    run_command("PyMuPDF.py", INPUT_FILE, "PyMuPDFLoader.txt")

    # 3. 运行 PyMuPDF4LLM (Markdown 格式)
    run_command("PyMuPDF4LLM.py", INPUT_FILE, "PyMuPDF4LLMLoader.txt")

    # 4. 运行 PDFPlumber (复杂布局/表格)
    run_command("PDFPlumber.py", INPUT_FILE, "PDFPlumberLoader.txt")

    # 5. 运行 PyPDFium2 (Google 引擎)
    run_command("PyPDFium2.py", INPUT_FILE, "PyPDFium2Loader.txt")

    # 6. 运行 PDFMiner (布局分析)
    run_command("PDFMiner.py", INPUT_FILE, "PDFMinerLoader.txt")

    # 7. 运行 Docling (OCR/文档理解)
    run_command("Docling.py", INPUT_FILE, "DoclingLoader.txt")

    # 8. 运行 OpenDataLoader (Java/Markdown)
    run_command("OpenDataLoader.py", INPUT_FILE, "OpenDataLoader.txt")

    # 9. 运行 Unstructured (OCR/非结构化)
    run_command("Unstructured.py", INPUT_FILE, "UnstructuredLoader_hi_res.txt")

    # 10. 运行 PyPDFDirectory (批量加载目录)
    # 注意：这里传入的是自动获取的 INPUT_DIR
    run_command("PyPDFDirectory.py", INPUT_DIR, "PyPDFDirectoryLoader.txt")

    print("\n==========================================")
    print("[SUCCESS] 所有任务执行完毕！")
    print(f"请查看 {OUTPUT_DIR.absolute()} 文件夹下的结果。")
    print("==========================================")


if __name__ == "__main__":
    main()