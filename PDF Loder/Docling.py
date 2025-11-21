from langchain_docling import DoclingLoader
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions, AcceleratorOptions, AcceleratorDevice
from docling.datamodel.base_models import InputFormat
import os
import sys
import torch
import json  # 引入 json 库用于格式化输出


def load_pdf_docling_full_meta():
    # 0. 检查 GPU 环境
    if not torch.cuda.is_available():
        print("【警告】：未检测到 GPU。正在使用 CPU，速度可能较慢。")
    else:
        print(f"【成功】：检测到 GPU: {torch.cuda.get_device_name(0)}")

    # 1. 获取输入路径
    raw_path = input("请输入PDF文件的完整路径 (例如 ./data/paper.pdf): ").strip().strip('"').strip("'")
    pdf_file_path = os.path.abspath(raw_path)

    if not os.path.exists(pdf_file_path):
        print("错误：找不到该文件。")
        return

    try:
        # 2. 配置 Docling (开启 GPU + OCR + 表格识别)
        print("正在初始化 Docling (Full Metadata 模式)...")

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True
        pipeline_options.accelerator_options = AcceleratorOptions(
            num_threads=8,
            device=AcceleratorDevice.CUDA
        )

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )

        # 3. 加载文档
        print("正在解析 PDF...")
        loader = DoclingLoader(file_path=pdf_file_path, converter=converter)
        docs = loader.load()  #

        # 4. 输出完整结果到文件
        if getattr(sys, 'frozen', False):
            script_dir = os.path.dirname(sys.executable)
        elif "__file__" in globals():
            script_dir = os.path.dirname(os.path.abspath(__file__))
        else:
            script_dir = os.getcwd()

        output_file_path = os.path.join(script_dir, "DoclingLoader.txt")

        with open(output_file_path, "w", encoding="utf-8") as f:
            header = f"文件解析结果 (Docling Full Meta): {os.path.basename(pdf_file_path)}\n" \
                     f"切分块数: {len(docs)}\n" \
                     f"说明: 下方包含了完整的 dl_meta 数据 (坐标、层级、JSON指针)\n" \
                     f"{'=' * 30}\n\n"
            print(header)
            f.write(header)

            for i, doc in enumerate(docs):
                content = doc.page_content
                metadata = doc.metadata

                # --- 构造元数据字符串 (重点修改部分) ---
                metadata_str = "【完整元数据 (Metadata)】:\n"

                for key, value in metadata.items():
                    if key == 'dl_meta':
                        # 使用 json.dumps 将字典格式化为漂亮的 JSON 字符串
                        # ensure_ascii=False 保证中文不乱码
                        # indent=2 增加缩进，方便阅读
                        pretty_json = json.dumps(value, ensure_ascii=False, indent=2)
                        metadata_str += f"  - {key}:\n{pretty_json}\n"
                    else:
                        metadata_str += f"  - {key}: {value}\n"

                # --- 写入文件 ---
                page_header = f"--- Block {i + 1} ---\n"
                full_output = f"{page_header}{metadata_str}\n【文本内容】:\n{content}\n\n"

                f.write(full_output)

                # 控制台只打印简略信息，防止刷屏
                if i == 0:
                    print(f"--- 预览第 1 块的元数据 (完整内容请看 TXT) ---\n{metadata_str[:500]}...\n")

        print(f"{'=' * 30}")
        print(f"解析完成！")
        print(f"完整元数据已保存至: {output_file_path}")
        print("现在你可以在 txt 文件中搜索 'bbox' 或 'prov' 来查看详细坐标了。")

    except Exception as e:
        print(f"发生错误: {e}")


if __name__ == "__main__":
    load_pdf_docling_full_meta()