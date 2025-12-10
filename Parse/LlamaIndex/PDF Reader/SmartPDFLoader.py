import os
import argparse
from llama_index.readers.smart_pdf_loader import SmartPDFLoader
from llama_index.core import Document  # 引入 Document 对象以便封装结果

def load_pdf_smart(input_path, output_path, api_url):
    # --- 路径处理 ---
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
        print(f"正在通过 SmartPDFLoader ({api_url}) 解析 PDF...")

        # 2. 初始化 SmartPDFLoader
        loader = SmartPDFLoader(llmsherpa_api_url=api_url)

        # --- 【核心修复】 ---
        # 问题：SmartPDFLoader 底层直接传路径会导致 Windows 上误判为 URL 报错 "No host specified"。
        # 解决：我们手动读取文件内容(bytes)，直接传给 loader 内部的 reader，强制它进行本地解析。

        with open(pdf_file_path, "rb") as f:
            pdf_bytes = f.read()

        # 调用 loader 内部的 pdf_reader，传入 contents 参数避开下载逻辑
        smart_doc = loader.pdf_reader.read_pdf(pdf_file_path, contents=pdf_bytes)

        # 3. 将结果封装回 LlamaIndex 的 Document 列表格式
        # 这样就能保持你原有的处理逻辑不变
        docs = []
        for chunk in smart_doc.chunks():
            doc = Document(
                text=chunk.to_context_text(),
                metadata={
                    "page_idx": chunk.page_idx,
                    "tag": chunk.tag,
                    "level": chunk.level
                }
            )
            docs.append(doc)

        # --- 输出内容到文件 ---
        with open(final_output_path, "w", encoding="utf-8") as f:

            header = f"文件解析结果 (SmartPDFLoader): {os.path.basename(pdf_file_path)}\n" \
                     f"保存位置: {final_output_path}\n" \
                     f"解析出的块(Chunks)数量: {len(docs)}\n" \
                     f"{'=' * 30}\n\n"

            print(header)
            f.write(header)

            for i, doc in enumerate(docs):
                # 提取内容 (LlamaIndex Document 使用 .text)
                content = doc.text

                # 提取元数据
                metadata_dict = doc.metadata
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
        import traceback
        traceback.print_exc()



if __name__ == "__main__":
    # 初始化参数解析器
    parser = argparse.ArgumentParser(description="SmartPDFLoader 解析工具")

    parser.add_argument("-i", "--input", type=str, default="../../PDF/Double_Layer/double_layer.pdf", help="输入 PDF 路径")
    parser.add_argument("-o", "--output", type=str, default="Output/SmartPDFLoader.txt", help="输出 txt 路径")
    # http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes
    parser.add_argument("--api", type=str, default="http://localhost:5001/api/parseDocument?renderFormat=all",
                        help="API 地址")

    args = parser.parse_args()

    load_pdf_smart(args.input, args.output, args.api)