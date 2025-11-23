from langchain_community.document_loaders import PyPDFDirectoryLoader
import os
import sys


def load_pdfs_from_directory():
    # 1. 获取用户输入 (注意：这里需要文件夹路径)
    print("【注意】：PyPDFDirectoryLoader 用于加载指定目录下的所有 PDF 文件。")
    raw_path = input("请输入PDF所在的文件夹路径 (例如 ./data/): ").strip().strip('"').strip("'")

    dir_path = os.path.abspath(raw_path)

    if not os.path.exists(dir_path):
        print("错误：找不到该目录，请检查路径是否正确。")
        return

    if not os.path.isdir(dir_path):
        print("错误：输入的路径不是一个目录。")
        return

    try:
        # 2. 初始化 Loader 并加载文档
        print(f"正在扫描目录 '{dir_path}' 下的所有 PDF...")

        # 初始化 PyPDFDirectoryLoader
        loader = PyPDFDirectoryLoader(dir_path)

        # 加载文档 (会遍历目录下所有 PDF)
        docs = loader.load()

        if not docs:
            print("提示：该目录下没有找到可解析的 PDF 文件。")
            return

        # 3. 确定输出文件的路径 (保存在脚本所在目录)
        if getattr(sys, 'frozen', False):
            script_dir = os.path.dirname(sys.executable)
        elif "__file__" in globals():
            script_dir = os.path.dirname(os.path.abspath(__file__))
        else:
            script_dir = os.getcwd()

        output_file_path = os.path.join(script_dir, "PyPDFDirectoryLoader.txt")

        # 4. 输出内容和元数据到文件
        with open(output_file_path, "w", encoding="utf-8") as f:

            # 获取涉及的文件名列表（去重）
            sources = set(doc.metadata.get('source', 'unknown') for doc in docs)

            header = f"批量解析结果 (PyPDFDirectory): {os.path.basename(dir_path)}\n" \
                     f"保存位置: {output_file_path}\n" \
                     f"涉及文件数: {len(sources)}\n" \
                     f"总页数 (所有文件合计): {len(docs)}\n" \
                     f"特点: 批量加载目录下所有 PDF，底层使用 pypdf 解析。\n" \
                     f"{'=' * 30}\n\n"

            print(header)
            f.write(header)

            for i, doc in enumerate(docs):
                # --- 提取内容 ---
                content = doc.page_content

                # --- 提取元数据 ---
                # PyPDFDirectoryLoader 的 metadata 包含 source (文件路径), page, total_pages 等
                metadata_dict = doc.metadata

                # 重点：在批量模式下，'source' 字段非常关键，用于区分内容属于哪个文件
                current_file = os.path.basename(metadata_dict.get('source', 'unknown_file'))
                current_page = metadata_dict.get('page', 0) + 1  # page 从 0 开始

                metadata_str = "【元数据 (Metadata)】:\n"
                for key, value in metadata_dict.items():
                    metadata_str += f"  - {key}: {value}\n"

                # --- 构造输出格式 ---
                # 增加文件名显示，以便区分不同文件的内容
                page_header = f"--- 序号 {i + 1} | 文件: {current_file} | 第 {current_page} 页 ---\n"
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
    load_pdfs_from_directory()