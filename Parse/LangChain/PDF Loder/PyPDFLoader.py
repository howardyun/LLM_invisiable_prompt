# pip install -qU LangChain-community pypdf
from langchain_community.document_loaders import PyPDFLoader
import os
import sys


def load_pdf_save_to_script_dir():
    # 1. 获取用户输入的路径
    raw_path = input("请输入PDF文件的完整路径 (例如 ./data/paper.pdf): ").strip().strip('"').strip("'")
    pdf_file_path = os.path.abspath(raw_path)

    if not os.path.exists(pdf_file_path):
        print("错误：找不到该文件，请检查路径是否正确。")
        return

    try:
        # 2. 初始化 Loader 并加载文档
        print("正在解析 PDF (含元数据)，请稍候...")
        loader = PyPDFLoader(pdf_file_path)
        docs = loader.load()  #

        # 3. 确定输出文件的路径（修改点：定位到脚本所在目录）
        # 获取当前脚本的绝对路径
        if getattr(sys, 'frozen', False):
            # 如果是打包后的 exe
            script_dir = os.path.dirname(sys.executable)
        elif "__file__" in globals():
            # 如果是正常运行的 .py 脚本
            script_dir = os.path.dirname(os.path.abspath(__file__))
        else:
            # 如果是在交互式环境（如 Jupyter）中运行
            script_dir = os.getcwd()

        output_file_path = os.path.join(script_dir, "PyPDFLoader.txt")

        # 4. 输出内容和元数据到控制台及文件
        with open(output_file_path, "w", encoding="utf-8") as f:

            header = f"文件解析结果: {os.path.basename(pdf_file_path)}\n" \
                     f"保存位置: {output_file_path}\n" \
                     f"总页数: {len(docs)}\n{'=' * 30}\n\n"

            print(header)
            f.write(header)

            for i, doc in enumerate(docs):
                # --- 提取内容 ---
                content = doc.page_content  #

                # --- 提取并格式化元数据 ---
                # metadata 包含 source, page, total_pages 等信息
                metadata_dict = doc.metadata
                metadata_str = "【元数据 (Metadata)】:\n"
                for key, value in metadata_dict.items():
                    metadata_str += f"  - {key}: {value}\n"

                # --- 构造输出格式 ---
                page_header = f"--- 第 {i + 1} 页 ---\n"
                full_page_output = f"{page_header}{metadata_str}\n【正文内容】:\n{content}\n\n"

                # --- 输出 ---
                print(full_page_output)
                f.write(full_page_output)

        print(f"{'=' * 30}")
        print(f"解析完成！")
        print(f"文件已保存在脚本同级目录: {output_file_path}")

    except Exception as e:
        print(f"发生错误: {e}")


if __name__ == "__main__":
    load_pdf_save_to_script_dir()