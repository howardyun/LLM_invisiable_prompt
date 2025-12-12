import os
import argparse
import traceback
from llmsherpa.readers import LayoutPDFReader


def load_pdf(input_path, output_path, api_url):
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
        print(f"正在通过原生 LayoutPDFReader ({api_url}) 解析 PDF...")

        # --- 2. 初始化 Reader (对应 file_reader.py) ---
        pdf_reader = LayoutPDFReader(api_url)

        # --- 3. 读取文件内容 ---
        # 手动读取二进制内容，避免路径被误判为 URL 或服务端无法访问本地路径的问题
        with open(pdf_file_path, "rb") as f:
            pdf_bytes = f.read()

        # 调用 read_pdf，传入 contents 参数 (参考 file_reader.py 中的定义)
        # 这会直接触发 _parse_pdf 发送 POST 请求给你的 Docker 服务
        doc = pdf_reader.read_pdf(pdf_file_path, contents=pdf_bytes)

        # 获取所有的 chunks (智能分块结果)
        chunks = doc.chunks()

        # --- 4. 输出内容到文件 ---
        with open(final_output_path, "w", encoding="utf-8") as f:

            header = f"文件解析结果 (Native LLMSherpa): {os.path.basename(pdf_file_path)}\n" \
                     f"保存位置: {final_output_path}\n" \
                     f"解析出的块(Chunks)数量: {len(chunks)}\n" \
                     f"{'=' * 30}\n\n"

            print(header)
            f.write(header)

            for i, chunk in enumerate(chunks):
                # 提取内容
                # to_context_text() 会包含父级标题层级结构，适合 RAG (参考 layout_reader.py)
                content = chunk.to_context_text()

                # 提取元数据
                # 在原生库中，这些属性直接挂载在 Block 对象上 (参考 layout_reader.py 的 Block 类定义)
                metadata_dict = {
                    "page_idx": chunk.page_idx,
                    "level": chunk.level,
                    "tag": chunk.tag,
                    "block_idx": chunk.block_idx,
                    "top": chunk.top,  # 坐标信息
                    "left": chunk.left,  # 坐标信息
                    # "bbox": chunk.bbox    # 如果你需要包围盒坐标，可以解开此注释
                }

                metadata_str = f"【块索引 (Chunk {i}) 元数据】:\n"
                for key, value in metadata_dict.items():
                    metadata_str += f"  - {key}: {value}\n"

                # 构造输出格式
                full_page_output = f"{metadata_str}\n【正文内容】:\n{content}\n\n{'-' * 20}\n\n"
                f.write(full_page_output)

        print(f"解析完成！")
        print(f"完整内容已保存在: {final_output_path}")

    except Exception as e:
        print(f"发生错误: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    # 初始化参数解析器
    parser = argparse.ArgumentParser(description="LLMSherpa 原生解析工具")

    # -i 参数: 输入文件路径
    parser.add_argument(
        "-i", "--input",
        type=str,
        default="../../PDF/Zero_Size/font_0.pdf",
        help="输入 PDF 文件的路径 (默认: ..\doc.pdf)"
    )

    # -o 参数: 输出文件路径
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="Output/zero_size/font_0/SherpaResult.txt",
        help="输出 txt 文件的路径 (默认: SherpaResult.txt)"
    )
    # 默认地址指向本地 Docker 部署的 nlm-ingestor 服务
    # http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes
    parser.add_argument("--api", type=str, default="http://localhost:5001/api/parseDocument?renderFormat=all",
                        help="API 地址 (例如: http://localhost:5001/api/parseDocument?renderFormat=all)")

    args = parser.parse_args()

    load_pdf(args.input, args.output, args.api)