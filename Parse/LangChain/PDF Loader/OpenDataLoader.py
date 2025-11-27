from langchain_opendataloader_pdf import OpenDataLoaderPDFLoader
import os
import shutil
import argparse


def load_pdf_with_opendataloader(input_path, output_path):
    # 检查 Java 环境 (OpenDataLoader 的硬性要求)
    if not shutil.which("java"):
        print("【错误】：未检测到 Java 环境。")
        print("OpenDataLoader 需要 Java 11+ 才能运行。请安装 Java 并将其添加到 PATH 环境变量。")
        return

    # 处理路径（转换为绝对路径）
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
        # 初始化 Loader 并加载文档
        print("正在使用 OpenDataLoader 解析 PDF...")
        print("提示: OpenDataLoader 在本地运行，具备 AI 安全过滤功能。")

        # 初始化 Loader
        # file_path 参数接受一个列表
        # format="markdown" 能更好地保留文档结构
        loader = OpenDataLoaderPDFLoader(
            file_path=[pdf_file_path],
            format="markdown"
        )

        # 加载文档
        docs = loader.load()

        # 输出内容和元数据到文件
        with open(final_output_path, "w", encoding="utf-8") as f:

            header = f"文件解析结果 (OpenDataLoader): {os.path.basename(pdf_file_path)}\n" \
                     f"保存位置: {final_output_path}\n" \
                     f"文档片段数: {len(docs)}\n" \
                     f"特点: 本地 Java 引擎，重构文档布局(Markdown)，内置 AI 安全过滤。\n" \
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
                # full_output = f"{metadata_str}\n【Markdown 内容】:\n{content}\n\n"
                full_output = f"【Markdown 内容】:\n{content}\n\n"

                # --- 输出 (控制台只打印部分) ---
                # if i < 3 or i > len(docs) - 3:
                #     print(full_output)
                # elif i == 3:
                #     print("\n... (中间内容省略，完整内容请查看 TXT 文件) ...\n")

                f.write(full_output)

        print(f"解析完成！")
        print(f"完整内容已保存在: {final_output_path}")

    except Exception as e:
        print(f"发生错误: {e}")
        if "java" in str(e).lower():
            print("提示: 这很可能是 Java 环境配置问题，请确保 `java -version` 在终端能正常运行。")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 初始化参数解析器
    parser = argparse.ArgumentParser(description="OpenDataLoader PDF 解析工具")

    # -i 参数: 输入文件路径
    parser.add_argument(
        "-i", "--input",
        type=str,
        default="..\doc.pdf",
        help="输入 PDF 文件的路径 (默认: ..\doc.pdf)"
    )

    # -o 参数: 输出文件路径
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="Output/OpenDataLoader.txt",
        help="输出 txt 文件的路径 (默认: Output/OpenDataLoader.txt)"
    )

    args = parser.parse_args()

    # 运行主逻辑
    load_pdf_with_opendataloader(args.input, args.output)