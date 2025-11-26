from langchain_opendataloader_pdf import OpenDataLoaderPDFLoader
import os
import sys
import shutil


def load_pdf_with_opendataloader():
    # 0. 检查 Java 环境 (因为这是 OpenDataLoader 的硬性要求)
    if not shutil.which("java"):
        print("【错误】：未检测到 Java 环境。")
        print("OpenDataLoader 需要 Java 11+ 才能运行。请安装 Java 并将其添加到 PATH 环境变量。")
        return

    # 1. 获取用户输入路径 (本地文件模式)
    raw_path = input("请输入PDF文件的完整路径 (例如 ./data/paper.pdf): ").strip().strip('"').strip("'")
    pdf_file_path = os.path.abspath(raw_path)

    if not os.path.exists(pdf_file_path):
        print("错误：找不到该文件，请检查路径是否正确。")
        return

    try:
        # 2. 初始化 Loader 并加载文档
        print("正在使用 OpenDataLoader 解析 PDF...")
        print("提示: OpenDataLoader 在本地运行，具备 AI 安全过滤功能 (如过滤 Prompt 注入内容)。")

        # 初始化 Loader
        # file_path 参数接受一个列表
        # format="markdown" 能更好地保留文档结构（标题、表格），适合 LLM/RAG
        loader = OpenDataLoaderPDFLoader(
            file_path=[pdf_file_path],
            format="markdown"
        )

        # 加载文档
        docs = loader.load()

        # 3. 确定输出文件的路径 (保存在脚本所在目录)
        if getattr(sys, 'frozen', False):
            script_dir = os.path.dirname(sys.executable)
        elif "__file__" in globals():
            script_dir = os.path.dirname(os.path.abspath(__file__))
        else:
            script_dir = os.getcwd()

        output_file_path = os.path.join(script_dir, "OpenDataLoader.txt")

        # 4. 输出内容和元数据到文件
        with open(output_file_path, "w", encoding="utf-8") as f:

            header = f"文件解析结果 (OpenDataLoader): {os.path.basename(pdf_file_path)}\n" \
                     f"保存位置: {output_file_path}\n" \
                     f"文档片段数: {len(docs)}\n" \
                     f"特点: 本地 Java 引擎，重构文档布局(Markdown)，内置 AI 安全过滤。\n" \
                     f"{'=' * 30}\n\n"

            print(header)
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
                page_header = f"--- 片段 {i + 1} ---\n"
                full_output = f"{page_header}{metadata_str}\n【Markdown 内容】:\n{content}\n\n"

                # --- 输出 (控制台只打印部分) ---
                if i < 3 or i > len(docs) - 3:
                    print(full_output)
                elif i == 3:
                    print("\n... (中间内容省略，完整内容请查看 TXT 文件) ...\n")

                f.write(full_output)

        print(f"{'=' * 30}")
        print(f"解析完成！")
        print(f"完整内容已保存在: {output_file_path}")

    except Exception as e:
        print(f"发生错误: {e}")
        if "java" in str(e).lower():
            print("提示: 这很可能是 Java 环境配置问题，请确保 `java -version` 在终端能正常运行。")


if __name__ == "__main__":
    load_pdf_with_opendataloader()