from langchain_community.document_loaders import PDFPlumberLoader
import os
import argparse


def load_pdf_with_pdfplumber(input_path, output_path):
    # 处理路径（转换为绝对路径）
    pdf_file_path = os.path.abspath(input_path)
    final_output_path = os.path.abspath(output_path)

    print(f"输入文件: {pdf_file_path}")
    print(f"输出文件: {final_output_path}")

    # 关键逻辑：自动创建输出目录
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
        # 初始化 Loader 并加载文档
        print("正在使用 PDFPlumber 解析 PDF...")
        print("提示: PDFPlumber 在处理多栏排版（如论文）时，通常比 PyPDF 更准确。")

        # 初始化 PDFPlumberLoader
        loader = PDFPlumberLoader(pdf_file_path)

        # 加载文档
        docs = loader.load()

        # 3. 输出内容和元数据到文件
        with open(final_output_path, "w", encoding="utf-8") as f:

            header = f"文件解析结果 (PDFPlumber): {os.path.basename(pdf_file_path)}\n" \
                     f"保存位置: {final_output_path}\n" \
                     f"总页数: {len(docs)}\n" \
                     f"特点: 擅长提取复杂布局文本，提供详细的 PDF 元数据。\n" \
                     f"{'=' * 30}\n\n"

            # print(header)
            f.write(header)

            for i, doc in enumerate(docs):
                # --- 提取内容 ---
                content = doc.page_content

                # --- 提取元数据 ---
                metadata_dict = doc.metadata

                metadata_str = "【元数据 (Metadata)】:\n"
                for key, value in metadata_dict.items():
                    metadata_str += f"  - {key}: {value}\n"

                # --- 构造输出格式 ---
                full_output = f"{metadata_str}\n【正文内容】:\n{content}\n\n"
                # full_output = f"【正文内容】:\n{content}\n\n"

                f.write(full_output)

        print(f"解析完成！")
        print(f"完整内容已保存在: {final_output_path}")

    except Exception as e:
        print(f"发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 初始化参数解析器
    parser = argparse.ArgumentParser(description="PDFPlumber 解析工具")

    # -i 参数: 输入文件路径，默认 ../text_version.pdf
    parser.add_argument(
        "-i", "--input",
        type=str,
        default="../text_version.pdf",
        help="输入 PDF 文件的路径 (默认: ../text_version.pdf)"
    )

    # -o 参数: 输出文件路径，默认 Output/PDFPlumberLoader.txt
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="Output/PDFPlumberLoader.txt",
        help="输出 txt 文件的路径 (默认: Output/PDFPlumberLoader.txt)"
    )

    args = parser.parse_args()

    # 运行主逻辑
    load_pdf_with_pdfplumber(args.input, args.output)