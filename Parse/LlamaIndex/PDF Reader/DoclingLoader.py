import os
import argparse
from pathlib import Path
# 引入 DoclingReader
from llama_index.readers.docling import DoclingReader

def load_pdf_docling(input_path, output_path):
    # --- 1. 路径处理 (保持逻辑一致) ---
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
        print(f"正在初始化 DoclingReader...")

        # 2. 初始化 DoclingReader
        # 默认 export_type 为 Markdown，这能更好地保留文档结构（标题、表格等）
        loader = DoclingReader()

        print(f"正在使用 Docling 解析 PDF (可能比标准解析器稍慢，但在处理布局时更精确)...")

        # 3. 调用 load_data 解析
        # DoclingReader.load_data 接收 file_path 参数
        docs = loader.load_data(file_path=pdf_file_path)

        # --- 输出内容到文件 ---
        with open(final_output_path, "w", encoding="utf-8") as f:

            header = f"文件解析结果 (DoclingReader): {os.path.basename(pdf_file_path)}\n" \
                     f"保存位置: {final_output_path}\n" \
                     f"解析出的文档块数量: {len(docs)}\n" \
                     f"说明: Docling 默认输出 Markdown 格式，能保留表格和标题层级\n" \
                     f"{'=' * 30}\n\n"

            print(header)
            f.write(header)

            for i, doc in enumerate(docs):
                # 提取内容 (Docling 输出的是 Markdown 文本)
                content = doc.text

                # 提取元数据
                # Docling 可能会包含 'dl_doc_hash' 等特有元数据
                metadata_dict = doc.metadata
                metadata_str = f"【文档块 (Block {i}) 元数据】:\n"

                if metadata_dict:
                    for key, value in metadata_dict.items():
                        metadata_str += f"  - {key}: {value}\n"
                else:
                    metadata_str += "  - (无元数据)\n"

                # 构造输出格式
                full_page_output = f"{metadata_str}\n【正文内容 (Markdown)】:\n{content}\n\n{'-' * 20}\n\n"
                f.write(full_page_output)

        print(f"解析完成！")
        print(f"完整内容已保存在: {final_output_path}")

    except Exception as e:
        print(f"发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 初始化参数解析器
    parser = argparse.ArgumentParser(description="DoclingReader 解析工具 (Markdown/布局提取)")

    parser.add_argument("-i", "--input", type=str, default="../../PDF/Double_Layer/double_layer.pdf",
                        help="输入 PDF 路径")
    parser.add_argument("-o", "--output", type=str, default="Output/DoclingLoader.txt", help="输出 txt 路径")

    args = parser.parse_args()

    load_pdf_docling(args.input, args.output)