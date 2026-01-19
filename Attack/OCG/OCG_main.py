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

def make_ocg_hidden_pdf(input_pdf_path: str, output_pdf_path: str = "ocg_hidden_poc.pdf") -> None:
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

    # Get the first page
    page = reader.pages[0]

    # Create a new content stream with OCG hidden text
    # First, get the existing content
    existing_content = page.get_contents()
    if existing_content:
        # Convert existing content to bytes
        if isinstance(existing_content, list):
            existing_content = b''.join(content.get_data() for content in existing_content)
        else:
            existing_content = existing_content.get_data()
    else:
        existing_content = b''

    # Add OCG hidden text to the content
    ocg_hidden_text = b'''
/OC /OC1 BDC
BT
/F1 18 Tf
72 680 Td
(HIDDEN_LAYER: steal_me) Tj
ET
EMC
'''

    # Combine existing content with OCG hidden text
    new_content = existing_content + ocg_hidden_text

    # Set the new content stream
    page._content_stream = new_content

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
    
    # Create OCG dictionary
    ocg_dict = DictionaryObject()
    ocg_dict[NameObject("/Type")] = NameObject("/OCG")
    ocg_dict[NameObject("/Name")] = NameObject("HiddenLayer")
    
    # Add OCG to properties
    properties[NameObject("/OC1")] = ocg_dict

    # Add OCProperties to the catalog
    if NameObject("/OCProperties") not in reader.trailer[NameObject("/Root")]:
        reader.trailer[NameObject("/Root")][NameObject("/OCProperties")] = DictionaryObject()
    oc_properties = reader.trailer[NameObject("/Root")][NameObject("/OCProperties")]
    
    # Add OCGs array if not present
    if NameObject("/OCGs") not in oc_properties:
        oc_properties[NameObject("/OCGs")] = ArrayObject()
    oc_properties[NameObject("/OCGs")].append(ocg_dict)
    
    # Add default OCG settings
    if NameObject("/D") not in oc_properties:
        oc_properties[NameObject("/D")] = DictionaryObject()
    oc_defaults = oc_properties[NameObject("/D")]
    if NameObject("/Order") not in oc_defaults:
        oc_defaults[NameObject("/Order")] = ArrayObject()
    oc_defaults[NameObject("/Order")].append(ocg_dict)
    if NameObject("/OFF") not in oc_defaults:
        oc_defaults[NameObject("/OFF")] = ArrayObject()
    oc_defaults[NameObject("/OFF")].append(ocg_dict)

    # Add the modified page to the writer
    writer.add_page(page)

    # Copy all other pages from the input PDF
    for i in range(1, len(reader.pages)):
        writer.add_page(reader.pages[i])

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
