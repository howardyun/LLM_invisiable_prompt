from langchain_community.document_loaders import PyPDFDirectoryLoader
import os
import argparse


def load_pdfs_from_directory(input_dir, output_path):
    # 处理路径（转换为绝对路径）
    dir_path = os.path.abspath(input_dir)
    final_output_path = os.path.abspath(output_path)

    print(f"输入目录: {dir_path}")
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

    # 检查输入目录是否存在且为文件夹
    if not os.path.exists(dir_path):
        print(f"错误：找不到目录 '{dir_path}'")
        return
    if not os.path.isdir(dir_path):
        print(f"错误：路径 '{dir_path}' 不是一个文件夹。")
        return

    try:
        # 初始化 Loader 并加载文档
        print(f"正在扫描目录 '{dir_path}' 下的所有 PDF...")
        print("提示: PyPDFDirectoryLoader 会递归或遍历加载该目录下的所有 .pdf 文件。")

        # 初始化 PyPDFDirectoryLoader
        loader = PyPDFDirectoryLoader(dir_path)

        # 加载文档 (会遍历目录下所有 PDF)
        docs = loader.load()

        if not docs:
            print("提示：该目录下没有找到可解析的 PDF 文件。")
            return

        # 输出内容和元数据到文件
        with open(final_output_path, "w", encoding="utf-8") as f:

            # 获取涉及的文件名列表（去重）
            sources = set(doc.metadata.get('source', 'unknown') for doc in docs)

            header = f"批量解析结果 (PyPDFDirectory): {os.path.basename(dir_path)}\n" \
                     f"保存位置: {final_output_path}\n" \
                     f"涉及文件数: {len(sources)}\n" \
                     f"总页数 (所有文件合计): {len(docs)}\n" \
                     f"特点: 批量加载目录下所有 PDF，底层使用 pypdf 解析。\n" \
                     f"{'=' * 30}\n\n"

            # print(header)
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
                full_output = f"{current_file}\n{page_header}{metadata_str}\n【正文内容】:\n{content}\n\n"
                # full_output = f"文件: {current_file}\n【正文内容】:\n{content}\n\n"

                f.write(full_output)

        print(f"解析完成！")
        print(f"完整内容已保存在: {final_output_path}")

    except Exception as e:
        print(f"发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 初始化参数解析器
    parser = argparse.ArgumentParser(description="PyPDFDirectory 批量解析工具")

    # -i 参数: 输入目录路径，默认 ../ (扫描上级目录)
    parser.add_argument(
        "-i", "--input",
        type=str,
        default="../",
        help="输入 PDF 所在的文件夹路径 (默认: ../)"
    )

    # -o 参数: 输出文件路径，默认 Output/PyPDFDirectoryLoader.txt
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="Output/PyPDFDirectoryLoader.txt",
        help="输出 txt 文件的路径 (默认: Output/PyPDFDirectoryLoader.txt)"
    )

    args = parser.parse_args()

    # 运行主逻辑
    load_pdfs_from_directory(args.input, args.output)