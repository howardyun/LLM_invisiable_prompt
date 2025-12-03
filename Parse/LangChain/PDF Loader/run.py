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

def run_command(script_name, input_target, output_filename, extra_args=None):
    """
    辅助函数：运行单个 Python 脚本并打印日志

    :param script_name: 脚本文件名
    :param input_target: 输入文件路径
    :param output_filename: 输出文件名
    :param extra_args: (可选) 额外的命令行参数列表，例如 ["--force_ocr"] 或 ["--safety", "all"]
    """
    script_path = Path(script_name)
    output_path = OUTPUT_DIR / output_filename

    # 打印简要信息
    print(f"运行 {script_path.stem} -> {output_filename} ...")

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

    # 添加额外参数
    if extra_args:
        cmd.extend(extra_args)

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

    print(f"\n[INFO] 开始自动化测试 (Mac/Cross-Platform Compatible)...")
    print(f"[INFO] 输入文件: {INPUT_FILE}")
    print(f"[INFO] 输入目录: {INPUT_DIR}")
    print(f"[INFO] 输出目录: {OUTPUT_DIR}")
    print("=" * 60)

    # 1. 运行 PyPDFLoader (基础解析)
    print("\n[1. PyPDFLoader]")
    run_command("PyPDFLoader.py", INPUT_FILE, "PyPDFLoader.txt")

    # 2. 运行 PyMuPDF (极速解析)
    print("\n[2. PyMuPDF]")
    run_command("PyMuPDF.py", INPUT_FILE, "PyMuPDFLoader.txt")

    # 3. 运行 PyMuPDF4LLM (Markdown 格式)
    print("\n[3. PyMuPDF4LLM]")
    run_command("PyMuPDF4LLM.py", INPUT_FILE, "PyMuPDF4LLMLoader.txt")

    # 4. 运行 PDFPlumber (复杂布局/表格)
    print("\n[4. PDFPlumber]")
    run_command("PDFPlumber.py", INPUT_FILE, "PDFPlumberLoader.txt")

    # 5. 运行 PyPDFium2 (Google 引擎)
    print("\n[5. PyPDFium2]")
    run_command("PyPDFium2.py", INPUT_FILE, "PyPDFium2Loader.txt")

    # 6. 运行 PDFMiner (布局分析)
    print("\n[6. PDFMiner]")
    run_command("PDFMiner.py", INPUT_FILE, "PDFMinerLoader.txt")

    # 7. 运行 Docling (多模式测试)
    print("\n[7. Docling - 多模式]")
    # 7.1 默认模式
    run_command("Docling.py", INPUT_FILE, "DoclingLoader.txt")
    # 7.2 强制 OCR 模式
    run_command("Docling.py", INPUT_FILE, "DoclingLoader_force_ocr.txt", ["--force_ocr"])

    # 8. 运行 OpenDataLoader (安全过滤测试)
    print("\n[8. OpenDataLoader - 安全过滤模式]")
    # 定义所有模式
    opendata_modes = [
        "default",
        "all",
        "hidden-text",
        "off-page",
        "tiny",
        "hidden-ocg"
    ]

    for mode in opendata_modes:
        # 构造输出文件名：如果是 default 就不加后缀，否则加 _mode
        if mode == "default":
            out_name = "OpenDataLoader.txt"
        else:
            # 将参数中的短横线 hidden-text 替换为文件名的下划线 hidden_text
            suffix = mode.replace("-", "_")
            out_name = f"OpenDataLoader_{suffix}.txt"

        run_command("OpenDataLoader.py", INPUT_FILE, out_name, ["--safety", mode])

    # 9. 运行 Unstructured (多策略测试)
    print("\n[9. Unstructured - 多策略]")
    unstructured_strategies = ["fast", "hi_res", "ocr_only"]

    for strat in unstructured_strategies:
        out_name = f"UnstructuredLoader_{strat}.txt"
        run_command("Unstructured.py", INPUT_FILE, out_name, ["--strategy", strat])

    # 10. 运行 PyPDFDirectory (批量加载目录)
    print("\n[10. PyPDFDirectory - 批量]")
    # 注意：这里传入的是 INPUT_DIR
    run_command("PyPDFDirectory.py", INPUT_DIR, "PyPDFDirectoryLoader.txt")

    print("\n" + "=" * 60)
    print("[SUCCESS] 所有任务执行完毕！")
    print(f"请查看 {OUTPUT_DIR.absolute()} 文件夹下的结果。")
    print("=" * 60)


if __name__ == "__main__":
    main()