import os
import time
import json
import argparse
import torch
import traceback
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    AcceleratorOptions,
    AcceleratorDevice,
    RapidOcrOptions
)
from docling.datamodel.base_models import InputFormat


def get_pipeline_options(force_ocr: bool, extract_tables: bool) -> PdfPipelineOptions:
    """
    配置 Docling 的原生 Pipeline 选项
    """
    pipeline_options = PdfPipelineOptions()

    # 1. 硬件加速配置
    if torch.cuda.is_available():
        print(f"【硬件】检测到 GPU: {torch.cuda.get_device_name(0)}，已启用 CUDA 加速。")
        pipeline_options.accelerator_options = AcceleratorOptions(
            num_threads=8,
            device=AcceleratorDevice.CUDA
        )
    else:
        print("【硬件】未检测到 GPU，将使用 CPU 处理（速度可能受限）。")

    # 2. OCR 策略配置
    if force_ocr:
        print("【策略】已启用：强制全页 OCR (RapidOCR)")
        pipeline_options.ocr_options = RapidOcrOptions(force_full_page_ocr=True)
        pipeline_options.do_ocr = True
    else:
        print("【策略】默认：智能 OCR (仅在检测到扫描件时启用)")

    # 3. 表格结构提取配置
    if extract_tables:
        print("【策略】已启用：增强表格结构提取")
        pipeline_options.do_table_structure = True
    else:
        pipeline_options.do_table_structure = False

    return pipeline_options


def process_pdf(input_path, output_path, force_ocr=False, extract_tables=False):
    # 处理路径
    abs_input_path = os.path.abspath(input_path)
    abs_output_path = os.path.abspath(output_path)

    if not os.path.exists(abs_input_path):
        print(f"❌ 错误：找不到输入文件: {abs_input_path}")
        return

    # 创建输出目录
    output_dir = os.path.dirname(abs_output_path)
    if output_dir and not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            print(f"📁 已自动创建输出目录: {output_dir}")
        except OSError as e:
            print(f"❌ 无法创建目录: {e}")
            return

    try:
        print(f"\n🚀 开始处理: {os.path.basename(abs_input_path)}")
        print(f"   输入: {abs_input_path}")
        print(f"   输出: {abs_output_path}")

        # 获取配置
        pipeline_options = get_pipeline_options(force_ocr, extract_tables)

        # 初始化转换器 (原生 Docling)
        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )

        # 执行转换
        start_time = time.time()
        print("⏳ 正在解析 PDF (Native Docling)...")

        # 核心转换步骤
        result = converter.convert(abs_input_path)
        doc = result.document  # 获取 Docling 文档对象
        end_time = time.time()

        # ---------------------------------------------------------
        # 1. 准备 Metadata (仿照 LangChain 的结构)
        # ---------------------------------------------------------
        # 原生 Docling 的 export_to_dict() 包含了最完整的元数据结构，
        # 这对应了你第一个脚本中 'dl_meta' 的内容。
        dl_meta_content = doc.export_to_dict()

        # 构造一个模拟的 metadata 字典，包含 source 和 dl_meta
        mock_metadata = {
            "source": abs_input_path,
            "dl_meta": dl_meta_content
        }

        # 格式化 Metadata 字符串 (完全复用你的逻辑)
        metadata_str = "【Metadata】:\n"
        for key, value in mock_metadata.items():
            if key == 'dl_meta':
                # 这里数据量可能很大，建议根据需要决定是否缩进或只打印摘要
                pretty_json = json.dumps(value, ensure_ascii=False, indent=2)
                metadata_str += f"  - {key}:\n{pretty_json}\n"
            else:
                metadata_str += f"  - {key}: {value}\n"

        # ---------------------------------------------------------
        # 2. 准备文本内容
        # ---------------------------------------------------------
        # 使用 Markdown 导出作为主要文本内容，保留结构
        content = doc.export_to_markdown()

        # ---------------------------------------------------------
        # 3. 写入文件
        # ---------------------------------------------------------
        with open(abs_output_path, "w", encoding="utf-8") as f:
            # 写入头部信息
            header = (
                f"文件解析报告 (Native)\n"
                f"文件名: {os.path.basename(abs_input_path)}\n"
                f"耗时: {end_time - start_time:.2f} 秒\n"
                f"策略: OCR={'开启' if force_ocr else '自动'}\n"
                f"{'=' * 40}\n\n"
            )
            f.write(header)

            # 写入 Metadata
            f.write(metadata_str)
            f.write("\n")

            # 写入文本内容
            f.write("【文本内容】:\n")
            f.write(content)
            f.write("\n\n")

        print(f"✅ 解析完成！")
        print(f"   保存路径: {abs_output_path}")

    except Exception as e:
        print(f"❌ 发生异常: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Docling Native PDF 解析工具 (含Metadata)")

    # -i 参数: 输入文件路径
    parser.add_argument(
        "-i", "--input",
        type=str,
        default="../../PDF/Zero_Size/font_0.pdf",
        help="输入 PDF 文件的路径 (默认: ..\doc.pdf)"
    )

    # -o 参数: 输出文件路径
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="Output/zero_size/font_0/DoclingLoader.txt",
        help="输出 txt 文件的路径 (默认: DoclingLoader.txt)"
    )

    # 策略参数
    parser.add_argument("--ocr", action="store_true", help="强制开启 OCR")
    parser.add_argument("--table", action="store_true", help="开启增强表格提取")

    args = parser.parse_args()

    process_pdf(
        input_path=args.input,
        output_path=args.output,
        force_ocr=args.ocr,
        extract_tables=args.table
    )