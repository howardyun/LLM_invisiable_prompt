import sys, os
from shutil import copyfile

under_text_path = sys.argv[1]
show_text_path = sys.argv[2]
under_text = []
show_text = []
latex_text = []
usedFont = []

punctuation = {
    "!": "Exclam",
    "\"": "Quotedbl",
    "#": "Numbersign",
    "$": "Dollar",
    "%": "Percent",
    "&": "Ampersand",
    "\'": "Quotesingle",
    "(": "Parenleft",
    ")": "parenright",
    "*": "Asterisk",
    "+": "Plus",
    ",": "Comma",
    "-": "Minus",
    ".": "Period",
    "/": "Slash",
    ":": "Colon",
    ";": "Semicolon",
    "<": "Less",
    ">": "Greater",
    "=": "Equal",
    "?": "Question",
    "@": "At",
    "[": "Bracketleft",
    "]": "Bracketright",
    "\\": "Backslash",
    "^": "Asciicirum"
}


def readFiles():
    # read files and split word into lists
    with open(under_text_path, 'r') as f:
        for line in f:
            for word in line.split():
                under_text.append(word)
    with open(show_text_path, 'r') as f:
        for line in f:
            for word in line.split():
                show_text.append(word)


def appendWordAndFont(under, show, c):
    tmp_code = ""
    if c == "c1":
        if show in punctuation.keys():
            show = punctuation.get(show)
        if show.isupper():
            show = show + show
        tmp_code += r"\cus" + show + r"{" + under + "}"
        if show not in usedFont:
            usedFont.append(show)
    if c == "c2":
        if show in punctuation.keys():
            show = punctuation.get(show)
        if show.isupper():
            show = show + show
        tmp_code += r"\cus" + show + r"{\_}"
        if show not in usedFont:
            usedFont.append(show)
    if c == "c3":
        tmp_code += r"\cusempty{" + under + "}"
        if "empty" not in usedFont:
            usedFont.append("empty")
    return tmp_code


def pairTwoWorlds(under, show):
    latex_code = r"\RemoveSpaces{"
    if len(under) < len(show):
        for i in range(len(show)):
            if i < len(under):
                # latex_code += r"\cus"+show[i]+r"{"+under[i]+"}"
                latex_code += appendWordAndFont(under[i], show[i], "c1")
            else:
                # latex_code += r"\cus"+show[i]+r"{\_}"
                latex_code += appendWordAndFont("", show[i], "c2")
    # latex_code += r"}"
    # latex_text.append(latex_code)
    else:
        for i in range(len(under)):
            if i < len(show):
                # latex_code += r"\cus"+show[i]+r"{"+under[i]+"}"
                latex_code += appendWordAndFont(under[i], show[i], "c1")
            else:
                # latex_code += r"\cusempty{"+under[i]+"}"
                latex_code += appendWordAndFont(under[i], "", "c3")
    latex_code += r"}"
    latex_text.append(latex_code)


def hideUnderWold(word):
    latex_code = r"\RemoveSpaces{"
    for i in word:
        # latex_code += r"\cusempty{"+i+"}"
        latex_code += appendWordAndFont(i, "", "c3")
    latex_code += r"}"
    latex_text.append(latex_code)


def showWord(word):
    latex_code = r"\RemoveSpaces{"
    for i in word:
        # latex_code += r"\cus"+i+r"{\_}"
        latex_code += appendWordAndFont("", i, "c2")
    latex_code += r"}"
    latex_text.append(latex_code)


def pair():
    # get the shortest length

    if len(show_text) < len(under_text):
        idx = 0
        for i in range(len(show_text)):
            idx += 1
            pairTwoWorlds(under_text[i], show_text[i])
        for i in range(len(under_text) - idx):
            hideUnderWold(under_text[i + idx])

    else:
        idx = 0
        for i in range(len(under_text)):
            idx += 1
            pairTwoWorlds(under_text[i], show_text[i])
        for i in range(len(show_text) - idx):
            showWord(show_text[i + idx])


def generateLatex():
    os.system('rm -rf output')
    os.system('mkdir output')

    # copy used font file
    os.system("cp src/fonts/T1-WGL4.enc output")
    os.system("cp src/doc.tex output")

    # generate latex code and font files
    latex_code = ""

    # 首先定义所有字体命令
    for i in usedFont:
        font_path = r"src/fonts/" + i + ".ttf"
        os.system("cp " + font_path + " output")

        # 修改字体定义，确保正确转义
        latex_code += r"\newcommand{\cus" + i + r"}[1]{{\fontencoding{T1}\fontfamily{" + i + r"}\selectfont #1}}" + "\n"

        # 生成字体描述文件
        font_code = r"\ProvidesFile{T1" + i + r".fd}" + "\n" + \
                    r"\DeclareFontFamily{T1}{" + i + r"}{}" + "\n" + \
                    r"\DeclareFontShape{T1}{" + i + r"}{m}{n}{ <-> " + i + r"}{}" + "\n" + \
                    r"\pdfmapline{+" + i + r" <" + i + r".ttf <T1-WGL4.enc}" + "\n"

        font_file = open("output/T1" + i + ".fd", "w")
        font_file.write(font_code)
        font_file.close()

    # 生成字体映射
    for i in usedFont:
        cmd = f"cd output && ttf2tfm {i}.ttf -p T1-WGL4.enc"
        os.system(cmd)

    # 构建文档内容
    latex_code += r"\begin{document}" + "\n"
    for i in latex_text:
        latex_code += i + " "
    latex_code += r"\end{document}" + "\n"

    # 写入主文档
    doc_file = open("output/doc.tex", "w")
    doc_file.write(latex_code)
    doc_file.close()

    # 生成 PDF
    os.chdir("output")
    os.system("pdflatex -interaction=nonstopmode doc.tex")


def main():
    readFiles()
    pair()
    generateLatex()


main()