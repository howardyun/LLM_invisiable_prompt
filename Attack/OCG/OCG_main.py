# ocg_poc_make.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


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


def make_ocg_hidden_pdf(path: str = "ocg_hidden_poc.pdf") -> None:
    # Object numbers:
    # 1: Catalog
    # 2: Pages
    # 3: Page
    # 4: Font (Helvetica)
    # 5: OCG (layer) dictionary
    # 6: Content stream (visible + hidden layer text)

    # OCG marked-content uses /OC /OC1 BDC ... EMC.
    # Page resources must map /OC1 -> 5 0 R in /Properties.

    # Content stream:
    # - visible text: "VISIBLE: hello"
    # - hidden text inside OCG: "HIDDEN_LAYER: steal_me"
    content_ops = b"""
BT
/F1 18 Tf
72 720 Td
(VISIBLE: hello) Tj
ET

/OC /OC1 BDC
BT
/F1 18 Tf
72 680 Td
(HIDDEN_LAYER: steal_me) Tj
ET
EMC
""".strip() + b"\n"

    # Wrap stream
    stream = (
        b"<< /Length " + str(len(content_ops)).encode("ascii") + b" >>\n"
        b"stream\n" + content_ops + b"endstream\n"
    )

    obj6 = PDFObj(6, 0, stream)

    obj4 = PDFObj(
        4, 0,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\n"
    )

    obj5 = PDFObj(
        5, 0,
        b"<< /Type /OCG /Name (HiddenLayer) >>\n"
    )

    # Page: single page, MediaBox, Resources include Font and Properties for OCG.
    obj3 = PDFObj(
        3, 0,
        b"<< /Type /Page\n"
        b"   /Parent 2 0 R\n"
        b"   /MediaBox [0 0 612 792]\n"
        b"   /Resources <<\n"
        b"       /Font << /F1 4 0 R >>\n"
        b"       /Properties << /OC1 5 0 R >>\n"
        b"   >>\n"
        b"   /Contents 6 0 R\n"
        b">>\n"
    )

    obj2 = PDFObj(
        2, 0,
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>\n"
    )

    # Catalog with OCProperties: set default OFF for that OCG.
    # Many viewers honor /D /OFF. Some also honor Usage/View/ViewState, but /OFF is the common switch.
    obj1 = PDFObj(
        1, 0,
        b"<< /Type /Catalog\n"
        b"   /Pages 2 0 R\n"
        b"   /OCProperties <<\n"
        b"       /OCGs [5 0 R]\n"
        b"       /D << /Order [5 0 R] /OFF [5 0 R] >>\n"
        b"   >>\n"
        b">>\n"
    )

    pdf_bytes = _build_pdf([obj1, obj2, obj3, obj4, obj5, obj6], root_objno=1)
    with open(path, "wb") as f:
        f.write(pdf_bytes)

    print(f"[OK] wrote {path} ({len(pdf_bytes)} bytes)")


if __name__ == "__main__":
    make_ocg_hidden_pdf()
