from langchain_unstructured import UnstructuredLoader
import os
import sys


def load_pdf_local():
    # 1. 获取用户输入路径
    raw_path = input("请输入PDF文件的完整路径 (例如 ./data/paper.pdf): ").strip().strip('"').strip("'")
    pdf_file_path = os.path.abspath(raw_path)

    if not os.path.exists(pdf_file_path):
        print("错误：找不到该文件，请检查路径是否正确。")
        return

    try:
        print("正在进行本地解析 (Local Parsing)...")
        print("提示: 本地解析依赖 Poppler 和 Tesseract，如果没有安装这些系统工具将会报错。")

        # 2. 初始化 Loader
        # 不传递 api_key 或 partition_via_api=True 即为本地模式
        # mode="elements" 是默认行为，将文档拆分为语义单元
        # strategy="hi_res" (高精度, 慢) 或 "fast" (快, 无OCR)
        loader = UnstructuredLoader(
            pdf_file_path,
            strategy="hi_res",  # 使用 'hi_res' 可以利用 Tesseract 识别图片中的文字，但速度较慢
        )

        # 开始加载 (这一步在本地消耗 CPU/内存)
        docs = loader.load()

        # 3. 确定输出路径 (脚本同级目录)
        if getattr(sys, 'frozen', False):
            script_dir = os.path.dirname(sys.executable)
        elif "__file__" in globals():
            script_dir = os.path.dirname(os.path.abspath(__file__))
        else:
            script_dir = os.getcwd()

        output_file_path = os.path.join(script_dir, "UnstructuredLoader.txt")

        # 4. 输出结果
        with open(output_file_path, "w", encoding="utf-8") as f:

            header = f"本地解析结果 (Unstructured Local): {os.path.basename(pdf_file_path)}\n" \
                     f"保存位置: {output_file_path}\n" \
                     f"识别元素数量: {len(docs)}\n" \
                     f"解析策略: hi_res (高精度)\n" \
                     f"{'=' * 30}\n\n"

            print(header)
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

                # 控制台只打印部分，文件写入全部
                if i < 3 or i > len(docs) - 3:
                    print(full_text)
                elif i == 3:
                    print("\n... (正在写入剩余内容到文件) ...\n")

                f.write(full_text)

        print(f"{'=' * 30}")
        print(f"本地解析完成！文件已保存: {output_file_path}")

    except ImportError:
        print("错误: 缺少必要的 Python 库。请运行: pip install 'LangChain-unstructured[local]'")
    except Exception as e:
        print(f"发生错误: {e}")
        if "poppler" in str(e).lower() or "tesseract" in str(e).lower():
            print("\n【关键提示】: 看起来你缺少系统级依赖。")
            print("请确保已安装 Poppler 和 Tesseract (不仅仅是 pip 包，而是操作系统软件)。")


if __name__ == "__main__":
    load_pdf_local()