# # demo_rlo_console.py
# text_logical = "ABC123"                 # 存储顺序（逻辑顺序）
# rlo = "\u202e"                          # Unicode RLO 控制字符
# text_with_rlo = "前缀-" + rlo + "ABC123"
#
# print("逻辑字符串 repr: ", repr(text_with_rlo))
# print("实际打印效果  : ", text_with_rlo)
# for ch in text_with_rlo:
#     print(f"U+{ord(ch):04X}", ch)
#
# rlo_pdf_demo.py
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

def create_rlo_pdf(filename="rlo_demo.pdf"):
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4

    # 1) 普通文本（对照）
    normal_text = "正常文本：ABC123"
    c.drawString(50, height - 50, normal_text)

    # 2) 带 RLO 的文本
    # 思路：逻辑编码还是 "ABC123"，但渲染时顺序反转
    rlo = "\u202e"   # 从右到左覆盖
    logical_payload = "ABC123"
    display_prefix = "带RLO文本："

    text_with_rlo = display_prefix + rlo + logical_payload

    c.drawString(50, height - 80, text_with_rlo)

    # 3) 再来一行更“欺骗感”一点的
    #   逻辑编码仍然是真实字符串 real_code
    #   但因为 RLO，视觉顺序会被“倒过来”显示
    real_code = "CODE-SECRET-001"
    text_with_rlo_2 = "视觉正常但编码被调序：" + rlo + real_code
    c.drawString(50, height - 110, text_with_rlo_2)

    c.showPage()
    c.save()
    print(f"已生成：{filename}")

if __name__ == "__main__":
    create_rlo_pdf()
