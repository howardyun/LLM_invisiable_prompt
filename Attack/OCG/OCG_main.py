# ocg_poc_make.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.generic import NameObject, DictionaryObject, ArrayObject


@dataclass
class PDFObj:
    objno: int
    gen: int
    body: bytes  # bytes without 'obj/endobj'


def _build_pdf(objects: List[PDFObj], root_objno: int) -> bytes:
    # Build PDF file with correct xref offsets.
    header = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"
    out = bytearray()
    out += header

    offsets: List[Tuple[int, int, int]] = []  # (objno, gen, offset)

    for obj in objects:
        offsets.append((obj.objno, obj.gen, len(out)))
        out += f"{obj.objno} {obj.gen} obj\n".encode("ascii")
        out += obj.body
        if not obj.body.endswith(b"\n"):
            out += b"\n"
        out += b"endobj\n"

    xref_offset = len(out)
    max_objno = max(o.objno for o in objects)

    # xref: include obj 0 free entry
    out += b"xref\n"
    out += f"0 {max_objno + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"

    # create lookup for offsets
    off_map = {objno: (gen, off) for (objno, gen, off) in offsets}
    for i in range(1, max_objno + 1):
        if i in off_map:
            gen, off = off_map[i]
            out += f"{off:010d} {gen:05d} n \n".encode("ascii")
        else:
            # unused object number
            out += b"0000000000 65535 f \n"

    trailer = (
        b"trailer\n"
        + b"<<\n"
        + f"/Size {max_objno + 1}\n".encode("ascii")
        + f"/Root {root_objno} 0 R\n".encode("ascii")
        + b">>\n"
        + b"startxref\n"
        + f"{xref_offset}\n".encode("ascii")
        + b"%%EOF\n"
    )
    out += trailer
    return bytes(out)


import os

def make_ocg_hidden_pdf(input_pdf_path: str, output_pdf_path: str = "ocg_hidden_poc.pdf", target_page: int = None, hidden_text: str = "HIDDEN_LAYER: steal_me") -> None:
    """
    生成包含OCG隐藏内容的PDF
    
    Args:
        input_pdf_path: 输入PDF文件路径
        output_pdf_path: 输出PDF文件路径
        target_page: 目标页码（从0开始），如果为None则对所有页面进行攻击
        hidden_text: 要注入的隐藏文本内容
    """
    # Validate input file exists
    if not os.path.exists(input_pdf_path):
        print(f"Error: Input file '{input_pdf_path}' does not exist")
        return
    
    # Validate input file is a PDF
    if not input_pdf_path.lower().endswith('.pdf'):
        print(f"Error: Input file '{input_pdf_path}' is not a PDF file")
        return
    
    # Read the input PDF file
    try:
        reader = PdfReader(input_pdf_path)
        writer = PdfWriter()
    except Exception as e:
        print(f"Error reading input PDF: {e}")
        return

    # 1. 创建 OCG 字典并将其注册为间接对象
    ocg_dict = DictionaryObject()
    ocg_dict[NameObject("/Type")] = NameObject("/OCG")
    ocg_dict[NameObject("/Name")] = NameObject("/HiddenLayer")
    # 关键：获取该对象的引用
    ocg_ref = writer._add_object(ocg_dict)
    
    # 2. 获取或创建 OCProperties 字典
    if not hasattr(writer, '_root_object'):
        writer._root_object = DictionaryObject()
    
    root = writer._root_object
    if NameObject("/OCProperties") not in root:
        root[NameObject("/OCProperties")] = DictionaryObject()
    oc_properties = root[NameObject("/OCProperties")]
    
    # 3. 设置 OCGs 数组 - 使用引用
    ocgs_array = ArrayObject([ocg_ref])
    oc_properties[NameObject("/OCGs")] = ocgs_array
    
    # 4. 设置默认配置（默认关闭 OCG 图层）
    # 用 /BaseState /OFF 直接声明默认所有 OCG 关闭，比 /BaseState /ON + /OFF 数组的
    # “覆盖式”写法更直接，兼容性更好；同时保留 /OFF 数组作为双保险。
    oc_defaults = DictionaryObject()
    oc_defaults[NameObject("/Name")] = NameObject("/Default")
    oc_defaults[NameObject("/BaseState")] = NameObject("/OFF")  # 基准为关：默认所有 OCG 关闭
    oc_defaults[NameObject("/OFF")] = ArrayObject([ocg_ref])    # 双保险：明确指定该层关闭
    oc_defaults[NameObject("/Order")] = ArrayObject([ocg_ref])   # 保持顺序
    oc_properties[NameObject("/D")] = oc_defaults

    # Process all pages to preserve them
    for page_num in range(len(reader.pages)):
        # Get current page
        page = reader.pages[page_num]
        
        # Only modify the target page if specified
        if target_page is None or page_num == target_page:
            # Create a new content stream with OCG hidden text
            # First, get the existing content
            existing_content = page.get_contents()
            if existing_content:
                # Convert existing content to bytes (PyPDF2 3.0+ compatible)
                try:
                    if isinstance(existing_content, list):
                        # For list of content streams
                        content_parts = []
                        for content in existing_content:
                            if hasattr(content, 'get_data'):
                                content_parts.append(content.get_data())
                            elif hasattr(content, 'get_bytes'):
                                content_parts.append(content.get_bytes())
                            else:
                                content_parts.append(bytes(content))
                        existing_content = b''.join(content_parts)
                    elif hasattr(existing_content, 'get_data'):
                        # For ContentStream object
                        existing_content = existing_content.get_data()
                    elif hasattr(existing_content, 'get_bytes'):
                        existing_content = existing_content.get_bytes()
                    else:
                        existing_content = bytes(existing_content)
                except Exception:
                    existing_content = b''
            else:
                existing_content = b''

            # Add OCG hidden text to the content
            # Only add hidden text, no visible text
            # 用 q/Q 包裹以隔离图形状态；并插入到 existing_content 之前。
            # 原因：PDF 的 cm 操作符是“右乘拼接”而非“设置”，无法把 existing_content
            # 末尾残留的 CTM（典型为 y 轴翻转 1 0 0 -1 0 H cm）重置回单位矩阵。
            # 而内容流开头 CTM 一定是页面默认的单位矩阵，故把 OCG 块放前面可保证
            # 文字方向正常；q/Q 隔离后 existing_content 仍在单位矩阵下执行，不受影响。
            ocg_hidden_text = f'''
q
/OC /OC1 BDC
BT
/F1 18 Tf
72 680 Td
({hidden_text}) Tj
ET
EMC
Q
'''.encode('utf-8')

            # 把 OCG 内容插入到 existing_content 之前，保证文字方向正常
            new_content = ocg_hidden_text + existing_content

            # Set the new content stream using PyPDF2's proper method
            # Create a new content stream object
            from PyPDF2.generic import DecodedStreamObject
            
            # Create a proper content stream
            content_stream = DecodedStreamObject()
            content_stream.set_data(new_content)
            
            # Replace the page's content with our new content
            page[NameObject("/Contents")] = content_stream

            # Add necessary resources for OCG
            if NameObject("/Resources") not in page:
                page[NameObject("/Resources")] = DictionaryObject()
            resources = page[NameObject("/Resources")]
            
            # Add font if not present
            if NameObject("/Font") not in resources:
                resources[NameObject("/Font")] = DictionaryObject()
            font_resources = resources[NameObject("/Font")]
            if NameObject("/F1") not in font_resources:
                font_dict = DictionaryObject()
                font_dict[NameObject("/Type")] = NameObject("/Font")
                font_dict[NameObject("/Subtype")] = NameObject("/Type1")
                font_dict[NameObject("/BaseFont")] = NameObject("/Helvetica")
                font_resources[NameObject("/F1")] = font_dict
            
            # Add OCG properties
            if NameObject("/Properties") not in resources:
                resources[NameObject("/Properties")] = DictionaryObject()
            properties = resources[NameObject("/Properties")]
            
            # Add OCG to properties - 使用同一个引用
            properties[NameObject("/OC1")] = ocg_ref

        # Always add the page to the writer (modified or not)
        writer.add_page(page)

    # Write the output PDF
    with open(output_pdf_path, 'wb') as f:
        writer.write(f)

    print(f"[OK] Modified PDF with OCG hidden content written to {output_pdf_path}")


if __name__ == "__main__":
    # Interactive mode: ask user for input and output paths
    print("OCG Hidden Content PDF Generator")
    print("==================================")
    
    # Ask for input PDF path
    input_pdf = input("Enter the path to the input PDF file: ").strip()
    
    # Ask for output PDF path, use default if empty
    output_pdf = input("Enter the path for the output PDF file (default: ocg_hidden_poc.pdf): ").strip()
    if not output_pdf:
        output_pdf = "ocg_hidden_poc.pdf"
    
    # Generate the PDF with OCG hidden content
    make_ocg_hidden_pdf(input_pdf, output_pdf)
