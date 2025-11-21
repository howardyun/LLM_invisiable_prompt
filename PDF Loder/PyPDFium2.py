from langchain_community.document_loaders import PyPDFium2Loader
import os
import sys


def load_pdf_with_pypdfium2():
    # 1. 获取用户输入路径 (本地文件模式)
    raw_path = input("请输入PDF文件的完整路径 (例如 ./data/paper.pdf): ").strip().strip('"').strip("'")
    pdf_file_path = os.path.abspath(raw_path)

    if not os.path.exists(pdf_file_path):
        print("错误：找不到该文件，请检查路径是否正确。")
        return

    try:
        # 2. 初始化 Loader 并加载文档
        print("正在使用 PyPDFium2 解析 PDF...")
        print("提示: PyPDFium2 基于 Google 的 PDFium 引擎，解析速度通常极快。")

        # 初始化 PyPDFium2Loader
        loader = PyPDFium2Loader(pdf_file_path)

        # 加载文档
        docs = loader.load()

        # 3. 确定输出文件的路径 (保存在脚本所在目录)
        if getattr(sys, 'frozen', False):
            script_dir = os.path.dirname(sys.executable)
        elif "__file__" in globals():
            script_dir = os.path.dirname(os.path.abspath(__file__))
        else:
            script_dir = os.getcwd()

        output_file_path = os.path.join(script_dir, "PyPDFium2Loader.txt")

        # 4. 输出内容和元数据到文件
        with open(output_file_path, "w", encoding="utf-8") as f:

            header = f"文件解析结果 (PyPDFium2): {os.path.basename(pdf_file_path)}\n" \
                     f"保存位置: {output_file_path}\n" \
                     f"总页数: {len(docs)}\n" \
                     f"特点: 高性能文本提取，基于 C++ PDFium 库。\n" \
                     f"{'=' * 30}\n\n"

            print(header)
            f.write(header)

            for i, doc in enumerate(docs):
                # --- 提取内容 ---
                content = doc.page_content  #

                # --- 提取元数据 ---
                # PyPDFium2 提取的 metadata 包含 title, author, creationdate 等
                metadata_dict = doc.metadata

                metadata_str = "【元数据 (Metadata)】:\n"
                for key, value in metadata_dict.items():
                    metadata_str += f"  - {key}: {value}\n"

                # --- 构造输出格式 ---
                page_header = f"--- 第 {i + 1} 页 ---\n"
                full_output = f"{page_header}{metadata_str}\n【正文内容】:\n{content}\n\n"

                # --- 输出 (控制台只打印部分) ---
                if i < 3 or i > len(docs) - 3:
                    print(full_output)
                elif i == 3:
                    print("\n... (中间页内容省略，完整内容请查看 TXT 文件) ...\n")

                f.write(full_output)

        print(f"{'=' * 30}")
        print(f"解析完成！")
        print(f"完整内容已保存在: {output_file_path}")

    except Exception as e:
        print(f"发生错误: {e}")


if __name__ == "__main__":
    load_pdf_with_pypdfium2()