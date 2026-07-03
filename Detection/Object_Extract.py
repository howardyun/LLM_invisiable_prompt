import fitz

pdf_path = "testData/org/table.pdf"

doc = fitz.open(pdf_path)

for page_id, page in enumerate(doc):
    print("=" * 100)
    print(f"Page {page_id + 1}")

    data = page.get_text("dict")

    for block in data["blocks"]:
        # print(block)
        if block["type"] != 0:
            continue

        for line in block["lines"]:
            # print(line)
            for span in line["spans"]:
                # print(span)
                text = span["text"]
                bbox = span["bbox"]
                font = span["font"]
                size = span["size"]
                color = span["color"]

                print({
                    "text": text,
                    "bbox": bbox,
                    "font": font,
                    "size": size,
                    "color": color,
                })