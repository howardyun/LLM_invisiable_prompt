import fitz
from typing import List, Dict, Any

#无法检测size=0的攻击，pymupdf会忽略大小为0的文本，只能检测大于0.01pt的文本
class ZeroSizeFontDetector:
    """
    检测 PDF 中的 zero-size font 攻击文本
    """

    def __init__(self, size_threshold: float = 1.0):
        """
        参数:
            size_threshold: 小于等于此字体大小的文本将被判定为可疑
                            1.0 对应你的攻击类型: size0, size0.01, size1
        """
        self.size_threshold = size_threshold

    def detect(self, pdf_path: str) -> Dict[int, List[Dict[str, Any]]]:
        """
        检测PDF并返回所有使用 zero-size font 的可疑文本

        返回结构:
        {
           page_number: [
               {
                  "text": "...",
                  "font": "helv",
                  "size": 0.0,
                  "bbox": (x1, y1, x2, y2)
               },
               ...
           ]
        }
        """
        doc = fitz.open(pdf_path)
        suspicious = {}

        for page_idx in range(len(doc)):
            page = doc[page_idx]
            blocks = page.get_text("dict")["blocks"]

            for b in blocks:
                if "lines" not in b:
                    continue

                for line in b["lines"]:
                    for span in line["spans"]:
                        size = span.get("size", -1)
                        text = span.get("text", "").strip()

                        # 判定攻击文本：字体尺寸太小 且 文本非空
                        if size <= self.size_threshold and text:
                            suspicious.setdefault(page_idx, []).append({
                                "text": text,
                                "font": span.get("font"),
                                "size": size,
                                "bbox": span.get("bbox")
                            })

        doc.close()
        return suspicious


def print_detection_result(result: Dict[int, List[Dict[str, Any]]]):
    """
    以良好格式打印检测结果
    """
    if not result:
        print("\n✔ 未检测到 zero-size font 攻击文本\n")
        return

    print("\n⚠ 检测到 Zero-Size Font 可疑文本:\n")
    for page, spans in result.items():
        print(f"--- Page {page} ---")
        for item in spans:
            print(f"  [text]  {item['text']}")
            print(f"  [font]  {item['font']}")
            print(f"  [size]  {item['size']}")
            print(f"  [bbox]  {item['bbox']}")
            print("")


def main():
    detector = ZeroSizeFontDetector(size_threshold=1.0)

    pdf_path = input("请输入要检测的 PDF 路径: ").strip()
    print("\n正在扫描 PDF...\n")

    result = detector.detect(pdf_path)
    print_detection_result(result)


if __name__ == "__main__":
    main()
