import os
import argparse
from haystack_integrations.components.converters.unstructured import UnstructuredFileConverter


def load_pdf_with_unstructured(input_path, output_path, api_url):
    # 处理路径（转换为绝对路径）
    file_path = os.path.abspath(input_path)
    final_output_path = os.path.abspath(output_path)

    print(f"输入文件: {file_path}")
    print(f"输出文件: {final_output_path}")
    print(f"API 地址: {api_url}")

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
    if not os.path.exists(file_path):
        print(f"错误：找不到文件 '{file_path}'")
        return

    try:
        # 初始化 Loader 并加载文档
        print("正在使用 Haystack UnstructuredFileConverter (Docker) 解析...")
        print("提示: Unstructured 擅长处理复杂布局，依赖本地 Docker 容器运行。")

        # 初始化 UnstructuredFileConverter
        # document_creation_mode 可选: "one-doc-per-file", "one-doc-per-page", "one-doc-per-element"
        converter = UnstructuredFileConverter(
            api_url=api_url,
            document_creation_mode="one-doc-per-file"
        )

        # 运行转换
        result = converter.run(paths=[file_path])
        docs = result["documents"]

        if not docs:
            print("警告: 未提取到任何内容。")
            return

        # 输出内容和元数据到文件
        with open(final_output_path, "w", encoding="utf-8") as f:

            header = f"文件解析结果 (Unstructured-Docker): {os.path.basename(file_path)}\n" \
                     f"保存位置: {final_output_path}\n" \
                     f"文档片段数: {len(docs)}\n" \
                     f"API URL: {api_url}\n" \
                     f"{'=' * 30}\n\n"

            f.write(header)

            for i, doc in enumerate(docs):
                # --- 提取内容 ---
                # Haystack 的文档内容属性是 .content
                content = doc.content

                # --- 提取元数据 ---
                # Haystack 的文档元数据属性是 .meta (不同于 LangChain 的 .metadata)
                metadata_dict = doc.meta

                metadata_str = f"【片段 {i + 1} 元数据 (Meta)】:\n"
                for key, value in metadata_dict.items():
                    metadata_str += f"  - {key}: {value}\n"

                # --- 构造输出格式 ---
                full_output = f"{metadata_str}\n【正文内容】:\n{content}\n\n"

                # 分隔符
                full_output += f"{'-' * 20}\n\n"

                f.write(full_output)

        print(f"解析完成！")
        print(f"完整内容已保存在: {final_output_path}")

    except Exception as e:
        print(f"发生错误: {e}")
        print("💡 如果报错 'Connection refused'，请检查 Docker 是否已启动：")
        print(
            "docker run -p 8000:8000 -d --rm --name unstructured-api quay.io/unstructured-io/unstructured-api:latest --port 8000 --host 0.0.0.0")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 初始化参数解析器
    parser = argparse.ArgumentParser(description="Unstructured (Haystack) 解析工具")

    # -i 参数: 输入文件路径
    parser.add_argument(
        "-i", "--input",
        type=str,
        default="../../PDF/Zero_Width/text/zero_width.pdf",
        # default="../text_version.pdf",
        help="输入文件的路径 (默认: ../text_version.pdf)"
    )

    # -o 参数: 输出文件路径
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="Output/UnstructuredConverter.txt",
        help="输出 txt 文件的路径 (默认: Output/UnstructuredConverter.txt)"
    )

    # 可选参数: Docker API 地址
    parser.add_argument(
        "--api",
        type=str,
        default="http://localhost:8000/general/v0/general",
        help="本地 Docker API 地址"
    )

    args = parser.parse_args()

    # 运行主逻辑
    load_pdf_with_unstructured(args.input, args.output, args.api)