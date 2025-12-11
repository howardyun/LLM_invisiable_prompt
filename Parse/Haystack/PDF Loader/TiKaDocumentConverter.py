import os
import argparse
from pathlib import Path
from haystack.components.converters import TikaDocumentConverter


def load_pdf_with_tika(input_path, output_path, tika_url):
    # 处理路径（转换为绝对路径）
    file_path = os.path.abspath(input_path)
    final_output_path = os.path.abspath(output_path)

    print(f"输入文件: {file_path}")
    print(f"输出文件: {final_output_path}")
    print(f"Tika URL: {tika_url}")

    # 1. 自动创建输出目录
    output_dir = os.path.dirname(final_output_path)
    if output_dir and not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            print(f"【提示】检测到输出目录不存在，已自动创建: {output_dir}")
        except OSError as e:
            print(f"【错误】无法创建目录: {e}")
            return

    # 2. 检查输入文件是否存在
    if not os.path.exists(file_path):
        print(f"错误：找不到文件 '{file_path}'")
        return

    try:
        # 初始化组件
        print("正在连接本地 Tika Server 解析 PDF...")
        print("提示: Tika 擅长提取极其详细的文档元数据 (Metadata)。")

        # 初始化 TikaDocumentConverter
        # tika_url 默认为 http://localhost:9998/tika
        converter = TikaDocumentConverter(tika_url=tika_url)

        # 运行转换
        # 注意：TikaDocumentConverter 的参数名是 'sources'，且推荐传入 Path 对象
        result = converter.run(sources=[Path(file_path)])
        docs = result["documents"]

        if not docs:
            print("警告: Tika 未提取到任何内容。")
            return

        # 3. 输出内容和元数据到文件
        with open(final_output_path, "w", encoding="utf-8") as f:

            header = f"文件解析结果 (Apache Tika): {os.path.basename(file_path)}\n" \
                     f"保存位置: {final_output_path}\n" \
                     f"文档数量: {len(docs)}\n" \
                     f"Tika Server: {tika_url}\n" \
                     f"{'=' * 30}\n\n"

            f.write(header)

            for i, doc in enumerate(docs):
                # --- 提取内容 ---
                content = doc.content

                # --- 提取元数据 ---
                # Tika 通常会返回非常丰富的元数据（如 Content-Type, Creation-Date 等）
                metadata_dict = doc.meta

                metadata_str = f"【文档 {i + 1} 元数据 (Meta)】:\n"
                for key, value in metadata_dict.items():
                    # 某些元数据值可能很长，做个简单的截断展示优化
                    str_val = str(value)
                    if len(str_val) > 100:
                        str_val = str_val[:100] + "..."
                    metadata_str += f"  - {key}: {str_val}\n"

                # --- 构造输出格式 ---
                full_output = f"{metadata_str}\n【正文内容】:\n{content}\n\n"

                # 分隔符
                full_output += f"{'-' * 20}\n\n"

                f.write(full_output)

        print(f"解析完成！")
        print(f"完整内容已保存在: {final_output_path}")

    except Exception as e:
        print(f"发生错误: {e}")
        print("💡 常见错误检查：")
        print("1. 确保 Docker 容器已启动: docker run -d -p 9998:9998 apache/tika:latest")
        print("2. 确保安装了依赖库: pip install tika")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 初始化参数解析器
    parser = argparse.ArgumentParser(description="Apache Tika (Haystack) 解析工具")

    # -i 参数: 输入文件
    parser.add_argument(
        "-i", "--input",
        type=str,
        default="../../PDF/Zero_Width/text/zero_width.pdf",
        # default="../text_version.pdf",
        help="输入文件的路径 (默认: ../text_version.pdf)"
    )

    # -o 参数: 输出文件
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="Output/TikaConverter.txt",
        help="输出 txt 文件的路径 (默认: Output/TikaConverter.txt)"
    )

    # --url 参数: Tika Server 地址
    parser.add_argument(
        "--url",
        type=str,
        default="http://localhost:9998/tika",
        help="Tika Server 地址 (默认: http://localhost:9998/tika)"
    )

    args = parser.parse_args()

    # 运行主逻辑
    load_pdf_with_tika(args.input, args.output, args.url)