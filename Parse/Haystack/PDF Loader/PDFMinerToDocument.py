from haystack.components.converters import PDFMinerToDocument
from pathlib import Path
import os
import argparse


def load_pdf_pdfminer(input_path, output_path):
    # 1. 处理路径（转换为绝对路径）
    pdf_file_path = os.path.abspath(input_path)
    final_output_path = os.path.abspath(output_path)

    print(f"输入文件: {pdf_file_path}")
    print(f"输出文件: {final_output_path}")

    # 2. 自动创建输出目录
    output_dir = os.path.dirname(final_output_path)
    if output_dir and not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            print(f"【提示】检测到输出目录不存在，已自动创建: {output_dir}")
        except OSError as e:
            print(f"【错误】无法创建目录: {e}")
            return

    # 3. 检查输入文件是否存在
    if not os.path.exists(pdf_file_path):
        print(f"错误：找不到文件 '{pdf_file_path}'")
        return

    try:
        # 4. 初始化 PDFMinerToDocument 并加载文档
        print("正在初始化 Haystack PDFMinerToDocument 并解析 PDF，请稍候...")

        # 你可以在这里传递 pdfminer 的特定参数，例如 line_overlap, char_margin 等
        # 默认初始化适合大多数情况
        converter = PDFMinerToDocument()

        # run 方法接受 sources 列表 (支持 Path 对象)
        # 官方文档指出 Mandatory run variables 为 sources
        result = converter.run(sources=[Path(pdf_file_path)])
        docs = result["documents"]

        # 5. 输出内容和元数据到文件
        with open(final_output_path, "w", encoding="utf-8") as f:

            header = f"文件解析结果 (Haystack PDFMinerToDocument): {os.path.basename(pdf_file_path)}\n" \
                     f"保存位置: {final_output_path}\n" \
                     f"文档片段数: {len(docs)}\n" \
                     f"{'=' * 30}\n\n"

            print(header)
            f.write(header)

            for i, doc in enumerate(docs):
                # --- 提取内容 ---
                # Haystack Document 对象使用 .content 属性
                content = doc.content

                # --- 提取并格式化元数据 ---
                # Haystack Document 对象使用 .meta 属性
                metadata_dict = doc.meta
                metadata_str = "【元数据 (Metadata)】:\n"

                if metadata_dict:
                    for key, value in metadata_dict.items():
                        metadata_str += f"  - {key}: {value}\n"
                else:
                    metadata_str += "  (无元数据)\n"

                # --- 构造输出格式 ---
                full_page_output = f"{metadata_str}\n【正文内容】:\n{content}\n\n"
                full_page_output += f"{'-' * 20}\n\n"

                f.write(full_page_output)

        print(f"解析完成！")
        print(f"完整内容已保存在: {final_output_path}")

    except Exception as e:
        print(f"发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 初始化参数解析器
    parser = argparse.ArgumentParser(description="Haystack PDFMinerToDocument 解析工具")

    # -i 参数: 输入文件路径
    parser.add_argument(
        "-i", "--input",
        type=str,
        default="../../PDF/Zero_Width/text/zero_width.pdf",
        # default="../text_version.pdf",
        help="输入 PDF 文件的路径 (默认: ../text_version.pdf)"
    )

    # -o 参数: 输出文件路径
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="Output/Haystack_PDFMiner.txt",
        help="输出 txt 文件的路径 (默认: Output/Haystack_PDFMiner.txt)"
    )

    args = parser.parse_args()

    # 运行主逻辑
    load_pdf_pdfminer(args.input, args.output)