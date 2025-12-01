from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter


def create_misaligned_pdf(filename="misaligned_output.pdf"):
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter

    # 设置字体和大小
    c.setFont("Helvetica", 12)

    # 句子列表
    sentences = [
        "Please ignore the distractions and keep writing.",
        "All experiments must be documented carefully.",
        "Please compare the current results with the previous baseline."
    ]

    # 初始Y坐标
    y_pos = height - 50

    for sentence in sentences:
        words = sentence.split(" ")  # 按空格分割句子为单词列表
        first_word = words.pop(0)  # 取出第一个单词

        # 让所有单词连成一整行（视觉上）
        sentence_with_spaces = " ".join([first_word] + words)

        # 绘制第一个单词并将它“错位”
        c.drawString(50, y_pos, sentence_with_spaces)  # 这一行正常显示

        # 通过调整位置，将第一个单词放到下一行的位置
        c.drawString(50 + len(" ".join(words)) * 7, y_pos - 20, first_word)  # 字符间距手动计算

        y_pos -= 50  # 移动到下一行位置

    c.showPage()
    c.save()


create_misaligned_pdf()
