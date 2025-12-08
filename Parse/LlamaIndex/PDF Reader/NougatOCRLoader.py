import os
import sys
import shutil  # 引入 shutil 用于清理文件夹
import argparse
from pathlib import Path
from llama_index.readers.nougat_ocr import PDFNougatOCR


def load_pdf_nougat(input_path, output_path):
    # --- 路径处理 ---
    pdf_file_path = os.path.abspath(input_path)
    final_output_path = os.path.abspath(output_path)

    print(f"输入文件: {pdf_file_path}")
    print(f"输出文件: {final_output_path}")

    # 自动创建输出目录
    output_dir = os.path.dirname(final_output_path)
    if output_dir and not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            print(f"【提示】检测到输出目录不存在，已自动创建: {output_dir}")
        except OSError as e:
            print(f"【错误】无法创建目录: {e}")
            return

    # 检查输入文件是否存在
    if not os.path.exists(pdf_file_path):
        print(f"错误：找不到文件 '{pdf_file_path}'")
        return

    try:
        print(f"正在初始化 Nougat OCR 模型 (首次运行可能需要下载模型)...")
        # 1. 初始化 PDFNougatOCR
        loader = PDFNougatOCR()

        print(f"正在解析 PDF (Nougat OCR 速度较慢，请耐心等待)...")

        # 2. 调用 load_data 解析
        docs = loader.load_data(Path(pdf_file_path))

        # 保护检查
        if docs is None:
            print("【严重错误】Nougat 解析失败，未返回任何数据。")
            return

        # --- 输出内容到文件 ---
        with open(final_output_path, "w", encoding="utf-8") as f:
            header = f"文件解析结果 (NougatOCR): {os.path.basename(pdf_file_path)}\n" \
                     f"保存位置: {final_output_path}\n" \
                     f"解析出的文档对象数量: {len(docs)}\n" \
                     f"说明: Nougat 擅长提取公式(LaTeX)和表格格式\n" \
                     f"{'=' * 30}\n\n"

            print(header)
            f.write(header)

            for i, doc in enumerate(docs):
                content = doc.text
                metadata_dict = doc.metadata
                metadata_str = f"【文档块 (Document {i}) 元数据】:\n"
                if metadata_dict:
                    for key, value in metadata_dict.items():
                        metadata_str += f"  - {key}: {value}\n"
                else:
                    metadata_str += "  - (无元数据)\n"

                full_page_output = f"{metadata_str}\n【正文内容 (Markdown/LaTeX)】:\n{content}\n\n{'-' * 20}\n\n"
                f.write(full_page_output)

        print(f"解析完成！")
        print(f"完整内容已保存在: {final_output_path}")

        # --- 【新增功能】清理 .mmd 中间文件 ---
        print("正在清理中间文件...")

        # 1. 定义可能生成的 mmd 文件名
        mmd_filename = Path(pdf_file_path).stem + ".mmd"

        # 2. 定义 Nougat 可能存放 mmd 的位置 (通常是 output 文件夹或当前目录)
        possible_paths = [
            Path("output") / mmd_filename,  # 默认 output 文件夹内
            Path(pdf_file_path).with_suffix('.mmd'),  # 输入文件同级
            Path(mmd_filename)  # 脚本运行目录同级
        ]

        cleaned_file = False
        for p in possible_paths:
            if p.exists():
                try:
                    os.remove(p)
                    print(f"【清理】已删除中间文件: {p}")
                    cleaned_file = True
                except Exception as e:
                    print(f"【警告】无法删除文件 {p}: {e}")

        # 3. 尝试清理可能产生的 output 文件夹 (如果它变空了)
        nougat_output_dir = Path("output")
        if nougat_output_dir.exists() and nougat_output_dir.is_dir():
            try:
                # 只有当文件夹为空时 os.rmdir 才会执行删除，安全
                os.rmdir(nougat_output_dir)
                print(f"【清理】已移除空的临时目录: {nougat_output_dir}")
            except OSError:
                # 文件夹非空，说明里面还有别的东西，不删
                pass

        if not cleaned_file:
            print("【提示】未发现残留的 .mmd 文件 (可能已经被自动清理)")

    except Exception as e:
        print(f"发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nougat OCR PDF 解析工具")
    parser.add_argument("-i", "--input", type=str, default="../../PDF/Double_Layer/double_layer.pdf",
                        help="输入 PDF 路径")
    parser.add_argument("-o", "--output", type=str, default="Output/NougatOCR.txt", help="输出 txt 路径")

    args = parser.parse_args()

    load_pdf_nougat(args.input, args.output)