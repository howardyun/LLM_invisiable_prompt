from haystack.components.converters import MultiFileConverter
from pathlib import Path
import os
import argparse


def load_with_multifile_converter(input_path, output_path):
    # 1. 处理路径（转换为绝对路径）
    file_path = os.path.abspath(input_path)
    final_output_path = os.path.abspath(output_path)

    print(f"输入文件: {file_path}")
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
    if not os.path.exists(file_path):
        print(f"错误：找不到文件 '{file_path}'")
        return

    try:
        # 4. 初始化 MultiFileConverter 并加载文档
        print("正在初始化 MultiFileConverter 并解析文件，请稍候...")

        # MultiFileConverter 是一个 SuperComponent，它会自动根据文件扩展名路由到正确的子转换器
        converter = MultiFileConverter()

        # run 方法接受 sources 列表
        result = converter.run(sources=[Path(file_path)])

        # 获取成功转换的文档列表
        docs = result.get("documents", [])

        # 获取无法识别/转换的文件列表 (MultiFileConverter 特有返回值)
        unclassified = result.get("unclassified", [])

        if unclassified:
            print(f"【注意】以下文件无法识别或解析: {unclassified}")

        if not docs:
            print("【警告】未提取到任何文档内容，请检查文件格式是否支持。")
            return

        # 5. 输出内容和元数据到文件
        with open(final_output_path, "w", encoding="utf-8") as f:

            header = f"文件解析结果 (Haystack MultiFileConverter): {os.path.basename(file_path)}\n" \
                     f"保存位置: {final_output_path}\n" \
                     f"文档片段数: {len(docs)}\n" \
                     f"{'=' * 30}\n\n"

            print(header)
            f.write(header)

            for i, doc in enumerate(docs):
                # --- 提取内容 ---
                content = doc.content

                # --- 提取并格式化元数据 ---
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
    parser = argparse.ArgumentParser(description="Haystack MultiFileConverter 通用解析工具")

    # -i 参数: 输入文件路径
    parser.add_argument(
        "-i", "--input",
        type=str,
        default="../../PDF/Zero_Width/text/zero_width.pdf",
        help="输入文件的路径 (支持 .pdf, .docx, .txt, .md, .csv 等)"
    )

    # -o 参数: 输出文件路径
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="Output/MultiFile_Result.txt",
        help="输出 txt 文件的路径 (默认: Output/MultiFile_Result.txt)"
    )

    args = parser.parse_args()

    # 运行主逻辑
    load_with_multifile_converter(args.input, args.output)