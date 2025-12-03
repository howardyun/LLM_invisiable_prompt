from langchain_unstructured import UnstructuredLoader
import os
import argparse


def load_pdf_local(input_path, output_path, strategy="fast"):
    # 处理路径（转换为绝对路径）
    pdf_file_path = os.path.abspath(input_path)
    final_output_path = os.path.abspath(output_path)

    print(f"输入文件: {pdf_file_path}")
    print(f"输出文件: {final_output_path}")
    print(f"解析策略: {strategy}")

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
        print("正在进行本地解析 (Local Parsing)...")
        print("提示: 本地解析依赖 Poppler 和 Tesseract，如果没有安装这些系统工具将会报错。")

        # 初始化 Loader
        # 初始化 Loader，使用传入的 strategy 参数
        loader = UnstructuredLoader(
            pdf_file_path,
            strategy=strategy,
        )

        # 开始加载 (这一步在本地消耗 CPU/内存)
        docs = loader.load()

        # 输出结果
        with open(final_output_path, "w", encoding="utf-8") as f:

            header = f"本地解析结果 (Unstructured Local): {os.path.basename(pdf_file_path)}\n" \
                     f"保存位置: {final_output_path}\n" \
                     f"识别元素数量: {len(docs)}\n" \
                     f"解析策略: \n" \
                     f"{'=' * 30}\n\n"

            # print(header)
            f.write(header)

            for i, doc in enumerate(docs):
                content = doc.page_content
                metadata = doc.metadata

                # 提取类别 (Title, NarrativeText, Table 等)
                category = metadata.get('category', 'Unknown')
                page_num = metadata.get('page_number', '?')

                # 格式化元数据
                metadata_str = "【元数据】:\n"
                for k, v in metadata.items():
                    # if k == 'coordinates': continue  # 忽略坐标数据以保持整洁
                    metadata_str += f"  - {k}: {v}\n"

                # 构造输出
                element_info = f"--- Element {i + 1} [页码: {page_num} | 类型: {category}] ---\n"
                full_text = f"{element_info}{metadata_str}【内容】:\n{content}\n\n"
                # full_text = f"【正文内容】:\n{content}\n\n"

                f.write(full_text)

        # print(f"{'=' * 30}")
        print(f"本地解析完成！文件已保存: {final_output_path}")

    except ImportError:
        print("错误: 缺少必要的 Python 库。请运行: pip install 'LangChain-unstructured[local]'")
    except Exception as e:
        print(f"发生错误: {e}")
        if "poppler" in str(e).lower() or "tesseract" in str(e).lower():
            print("\n【关键提示】: 看起来你缺少系统级依赖。")
            print("请确保已安装 Poppler 和 Tesseract (不仅仅是 pip 包，而是操作系统软件)。")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 初始化参数解析器
    parser = argparse.ArgumentParser(description="Unstructured 解析工具")

    # -i 参数: 输入文件路径，默认 ../text_version.pdf
    parser.add_argument(
        "-i", "--input",
        type=str,
        default="../PDF/Word_Shift/pdf_poc.pdf",
        help="输入 PDF 文件的路径 (默认: ../text_version.pdf)"
    )

    # -o 参数: 输出文件路径，默认 Output/UnstructuredLoader_hi_res.txt
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="Output/word_shift/UnstructuredLoader_fast.txt",
        help="输出 txt 文件的路径 (默认: Output/UnstructuredLoader_hi_res.txt)"
    )

    # --strategy 参数: 支持 fast, hi_res, ocr_only
    parser.add_argument(
        "--strategy",
        type=str,
        default="fast",
        choices=["fast", "hi_res", "ocr_only"],
        help="解析策略: fast (快速), hi_res (高精), ocr_only (仅OCR)"
    )

    args = parser.parse_args()

    # 运行主逻辑
    load_pdf_local(args.input, args.output, args.strategy)