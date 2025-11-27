from langchain_docling import DoclingLoader
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions, AcceleratorOptions, AcceleratorDevice, \
    RapidOcrOptions
from docling.datamodel.base_models import InputFormat
import os
import torch
import json
import argparse


def load_pdf_docling_full_meta(input_path, output_path):
    # 检查 GPU
    if not torch.cuda.is_available():
        print("【警告】：未检测到 GPU。正在使用 CPU，速度可能较慢。")
    else:
        print(f"【成功】：检测到 GPU: {torch.cuda.get_device_name(0)}")

    # 处理路径（转换为绝对路径）
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
        print(f"错误：找不到输入文件 '{pdf_file_path}'")
        return

    try:
        # 配置 Docling
        print("正在初始化 Docling ...")

        pipeline_options = PdfPipelineOptions()
        # pipeline_options.do_ocr = True
        # pipeline_options.do_table_structure = True

        # 强制OCR
        # pipeline_options.ocr_options = RapidOcrOptions(force_full_page_ocr=True)

        pipeline_options.accelerator_options = AcceleratorOptions(
            num_threads=8,
            device=AcceleratorDevice.CUDA
        )

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )

        # 加载
        print("正在解析 PDF...")
        loader = DoclingLoader(file_path=pdf_file_path, converter=converter)
        docs = loader.load()

        # 输出结果
        with open(final_output_path, "w", encoding="utf-8") as f:
            header = f"文件解析结果: {os.path.basename(pdf_file_path)}\n" \
                     f"切分块数: {len(docs)}\n" \
                     f"{'=' * 30}\n\n"
            # print(header)
            f.write(header)

            for i, doc in enumerate(docs):
                content = doc.page_content
                metadata = doc.metadata

                # 格式化 Metadata
                metadata_str = "【Metadata】:\n"
                for key, value in metadata.items():
                    if key == 'dl_meta':
                        pretty_json = json.dumps(value, ensure_ascii=False, indent=2)
                        metadata_str += f"  - {key}:\n{pretty_json}\n"
                    else:
                        metadata_str += f"  - {key}: {value}\n"

                # 写入文件
                full_output = f"【文本内容】:\n{content}\n\n"
                f.write(full_output)

                # 打印第一块的预览
                # if i == 0:
                    # print(f"--- 预览内容 ---\n{content[:200]}...\n")

        print(f"解析完成！保存至: {final_output_path}")

    except Exception as e:
        print(f"发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 初始化参数解析器
    parser = argparse.ArgumentParser(description="Docling PDF 解析工具")

    # -i 参数: 输入文件路径
    parser.add_argument(
        "-i", "--input",
        type=str,
        default="..\doc.pdf",
        help="输入 PDF 文件的路径 (默认: ..\doc.pdf)"
    )

    # -o 参数: 输出文件路径
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="Output\DoclingLoader.txt",
        help="输出 txt 文件的路径 (默认: DoclingLoader.txt)"
    )

    args = parser.parse_args()

    # 运行主逻辑
    load_pdf_docling_full_meta(args.input, args.output)