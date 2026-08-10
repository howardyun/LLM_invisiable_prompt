# parse_oob_pdf_pypdf.py

from pypdf import PdfReader

pdf_path = "D:\LLM_invisiable_prompt\LLM_invisiable_prompt\Attack\Out-of-Bound\oob_poc_base.pdf"   # 换成你的 PoC 文件路径

reader = PdfReader(pdf_path)
page = reader.pages[0]

text = page.extract_text()

print("=== Raw extracted text ===")
print(repr(text))   # 用 repr 可以看到换行等隐藏字符

print("\n=== Pretty print ===")
print(text)

# 简单做个检测：看看隐藏文本是不是被解析出来了
if "HIDDEN OOB TEXT" in text:
    print("\n[+] Hidden OOB text FOUND in extracted text!")
else:
    print("\n[-] Hidden OOB text NOT found (check file or generator)")
