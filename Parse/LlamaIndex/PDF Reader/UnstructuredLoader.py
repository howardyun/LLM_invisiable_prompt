import os
import argparse
from pathlib import Path
from llama_index.readers.file import UnstructuredReader


def load_pdf_unstructured(input_path, output_path):
    # --- 1. 路径处理 ---
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
        print(f"正在初始化 UnstructuredReader...")

        # 2. 初始化 UnstructuredReader
        # Unstructured 作为一个通用读取器，这里我们不需要传入太复杂的参数
        # 它可以处理 PDF, DOCX, PPTX 等多种格式
        loader = UnstructuredReader()

        print(f"正在解析文件 (使用 Unstructured 引擎)...")

        # 3. 调用 load_data 解析
        # UnstructuredReader.load_data 接收 Path 对象
        docs = loader.load_data(file=Path(pdf_file_path))

        # --- 输出内容到文件 ---
        with open(final_output_path, "w", encoding="utf-8") as f:

            header = f"文件解析结果 (UnstructuredReader): {os.path.basename(pdf_file_path)}\n" \
                     f"保存位置: {final_output_path}\n" \
                     f"解析出的元素数量: {len(docs)}\n" \
                     f"说明: Unstructured 擅长识别文档结构元素（标题、正文、列表等）\n" \
                     f"{'=' * 30}\n\n"

            print(header)
            f.write(header)

            for i, doc in enumerate(docs):
                # 提取内容
                content = doc.text

                # 提取元数据
                # Unstructured 通常会尝试提取文件名等基本信息
                metadata_dict = doc.metadata
                metadata_str = f"【元素 (Element {i}) 元数据】:\n"

                if metadata_dict:
                    for key, value in metadata_dict.items():
                        metadata_str += f"  - {key}: {value}\n"
                else:
                    metadata_str += "  - (无元数据)\n"

                # 构造输出格式
                full_page_output = f"{metadata_str}\n【内容】:\n{content}\n\n{'-' * 20}\n\n"
                f.write(full_page_output)

        print(f"解析完成！")
        print(f"完整内容已保存在: {final_output_path}")

    except Exception as e:
        print(f"发生错误: {e}")
        print("提示: Unstructured 可能需要安装系统级依赖 (如 tesseract, poppler)。")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 初始化参数解析器
    parser = argparse.ArgumentParser(description="UnstructuredReader 解析工具 (通用结构化解析)")

    parser.add_argument("-i", "--input", type=str, default="../../PDF/Double_Layer/double_layer.pdf",
                        help="输入文件路径 (支持 PDF/DOCX/PPTX 等)")
    parser.add_argument("-o", "--output", type=str, default="Output/UnstructuredLoader.txt", help="输出 txt 路径")

    args = parser.parse_args()

    load_pdf_unstructured(args.input, args.output)