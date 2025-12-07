import os
import argparse
from pathlib import Path
# 1. 引入 PaddleOCR reader
from llama_index.readers.paddle_ocr import PDFPaddleOCRReader


def load_pdf_paddle(input_path, output_path, lang='en'):
    # --- 路径处理 ---
    # PaddleOCR 推荐使用 pathlib.Path 对象
    pdf_file_path = Path(input_path).resolve()
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
    if not pdf_file_path.exists():
        print(f"错误：找不到文件 '{pdf_file_path}'")
        return

    try:
        print(f"正在初始化 PDFPaddleOCR (语言: {lang})...")

        # 2. 初始化 PDFPaddleOCR
        loader = PDFPaddleOCRReader(lang=lang)

        print(f"正在解析 PDF，这可能需要一些时间（尤其是包含公式和表格时）...")

        # 3. 加载数据
        # PaddleOCR loader 的 load_data 直接返回 LlamaIndex 的 Document 对象列表
        # 注意：PaddleOCR 可能会在输入文件旁边生成同名的文件夹存放中间结果(.mmd等)
        docs = loader.load_data(file_path=pdf_file_path)

        # --- 输出内容到文件 ---
        with open(final_output_path, "w", encoding="utf-8") as f:

            header = f"文件解析结果 (PaddleOCR): {pdf_file_path.name}\n" \
                     f"保存位置: {final_output_path}\n" \
                     f"解析出的文档片段数量: {len(docs)}\n" \
                     f"{'=' * 30}\n\n"

            print(header)
            f.write(header)

            for i, doc in enumerate(docs):
                # 提取内容
                content = doc.text

                # 提取元数据 (如果有的话)
                metadata_dict = doc.metadata
                metadata_str = f"【片段索引 (Doc {i}) 元数据】:\n"
                if metadata_dict:
                    for key, value in metadata_dict.items():
                        metadata_str += f"  - {key}: {value}\n"
                else:
                    metadata_str += "  - 无元数据\n"

                # 构造输出格式
                full_page_output = f"{metadata_str}\n【正文内容】:\n{content}\n\n{'-' * 20}\n\n"
                f.write(full_page_output)

        print(f"解析完成！")
        print(f"完整内容已保存在: {final_output_path}")

        # 提示用户 PaddleOCR 的副作用
        expected_output_folder = pdf_file_path.with_suffix('')
        if expected_output_folder.exists():
            print(f"【注意】PaddleOCR 可能在源文件目录生成了中间文件夹: {expected_output_folder}")

    except Exception as e:
        print(f"发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 初始化参数解析器
    parser = argparse.ArgumentParser(description="PaddleOCR PDF 解析工具")

    parser.add_argument("-i", "--input", type=str, default="../../PDF/Double_Layer/double_layer.pdf",
                        help="输入 PDF 路径")
    parser.add_argument("-o", "--output", type=str, default="Output/PaddleOCR.txt", help="输出 txt 路径")
    parser.add_argument("--lang", type=str, default="en", help="OCR 识别语言 (en/ch)")

    args = parser.parse_args()

    load_pdf_paddle(args.input, args.output, args.lang)