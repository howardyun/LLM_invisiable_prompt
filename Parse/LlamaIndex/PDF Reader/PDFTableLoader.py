import os
import argparse
from pathlib import Path
from llama_index.readers.pdf_table import PDFTableReader


def load_pdf_table(input_path, output_path, pages):
    # --- 路径处理 ---
    pdf_file_path = os.path.abspath(input_path)
    final_output_path = os.path.abspath(output_path)

    print(f"输入文件: {pdf_file_path}")
    print(f"输出文件: {final_output_path}")
    print(f"目标页码范围: {pages}")

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
        print(f"正在初始化 PDFTableReader...")

        # 1. 初始化 PDFTableReader
        loader = PDFTableReader()

        print(f"正在提取表格 (这可能需要几秒钟，取决于表格复杂度和页数)...")

        # 2. 调用 load_data 解析
        # 该加载器专门提取表格数据，pages 参数支持 'all', '1,2', '5-10' 等格式
        docs = loader.load_data(file=Path(pdf_file_path), pages=pages)

        # --- 输出内容到文件 ---
        with open(final_output_path, "w", encoding="utf-8") as f:

            header = f"文件解析结果 (PDFTableReader): {os.path.basename(pdf_file_path)}\n" \
                     f"保存位置: {final_output_path}\n" \
                     f"页码范围: {pages}\n" \
                     f"提取到的表格数量: {len(docs)}\n" \
                     f"{'=' * 30}\n\n"

            print(header)
            f.write(header)

            if len(docs) == 0:
                msg = "【警告】未在指定页面检测到表格。请检查页码范围或确认PDF是否包含可选中的表格层。\n"
                print(msg)
                f.write(msg)

            for i, doc in enumerate(docs):
                # 提取内容 (PDFTableReader 通常返回表格的文本表示，有时可能是 HTML 或 CSV 格式的字符串)
                content = doc.text

                # 提取元数据
                metadata_dict = doc.metadata
                metadata_str = f"【表格 (Table {i}) 元数据】:\n"

                if metadata_dict:
                    for key, value in metadata_dict.items():
                        metadata_str += f"  - {key}: {value}\n"
                else:
                    metadata_str += "  - (无元数据)\n"

                # 构造输出格式
                full_page_output = f"{metadata_str}\n【表格内容】:\n{content}\n\n{'-' * 20}\n\n"
                f.write(full_page_output)

        print(f"解析完成！")
        print(f"完整内容已保存在: {final_output_path}")

    except Exception as e:
        print(f"发生错误: {e}")
        print("提示: 此加载器通常依赖系统安装 Ghostscript，请检查是否已安装该环境。")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 初始化参数解析器
    parser = argparse.ArgumentParser(description="PDF Table 解析工具 (提取 PDF 中的表格)")

    parser.add_argument("-i", "--input", type=str, default="../../PDF/Double_Layer/double_layer.pdf",
                        help="输入 PDF 路径")
    parser.add_argument("-o", "--output", type=str, default="Output/PDFTable.txt", help="输出 txt 路径")

    # 新增 pages 参数
    parser.add_argument("-p", "--pages", type=str, default="all",
                        help="页码范围 (例如: 'all', '1', '1,3,5', '10-20')")

    args = parser.parse_args()

    load_pdf_table(args.input, args.output, args.pages)