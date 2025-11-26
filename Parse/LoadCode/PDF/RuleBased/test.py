# from langchain_community.document_loaders import PyPDFLoader
#
#
# pdf_loader = PyPDFLoader('Data/DGA_IWQOS2025.pdf')
# pages = pdf_loader.load_and_split()
# page_content = pages[0].page_content
# page_content1 = pages[1].page_content
#
# print(page_content)
# print(page_content1)


import fitz  # PyMuPDF

# 打开 PDF 文件
pdf_path = '../../../../Data/PDF/DGA_IWQOS2025.pdf'
# pdf_path = '../../../Data/DGA_IWQOS2025.pdf'
# pdf_path = '../../../Data/PDF/pdf_poc.pdf'
# pdf_path = '../../../Data/testinvisiable.pdf'


doc = fitz.open(pdf_path)

# 提取每一页的文本
for page_num in range(len(doc)):
    page = doc.load_page(page_num)
    text = page.get_text()
    print(f"Page {page_num + 1} Text:")
    print(text)

    # 提取页面中的图像
    images = page.get_images(full=True)
    for img in images:
        xref = img[0]
        pix = fitz.Pixmap(doc, xref)
        pix.save(f"image_page{page_num+1}_{xref}.png")



# import fitz  # PyMuPDF
#
# def extract_invisible_text(pdf_path):
#     doc = fitz.open(pdf_path)  # 打开PDF文件
#     invisible_texts = []
#
#     # 遍历每一页
#     for page_num in range(len(doc)):
#         page = doc.load_page(page_num)
#
#         # 获取文本块和相应的属性
#         text_instances = page.get_text("dict")  # 提取文本块，返回字典
#         print(page)
#         for block in text_instances["blocks"]:
#             # 每个块可能包含多个文本片段
#             if block['type'] == 0:  # 确保是文本块
#                 for line in block["lines"]:
#                     print('#'*100)
#                     print(line)
#                     for span in line["spans"]:
#                         print(span)
#                         # 获取文本内容，颜色和透明度等属性
#                         text = span['text']
#                         color = span['color']  # 颜色
#                         alpha = span['alpha']  # 透明度
#                         size = span['size']  # 字体大小
#
#                         # 判断条件：若透明度为 0 或者颜色为背景色，视为不可见
#                         if alpha == 0 or color == 0xFFFFFF:  # 假设背景色为白色
#                             invisible_texts.append({
#                                 "page": page_num + 1,
#                                 "text": text,
#                                 "color": color,
#                                 "alpha": alpha,
#                                 "size": size
#                             })
#
#     return invisible_texts
#
# # 示例PDF路径
# pdf_path = '../../../Data/pdf_poc.pdf'
#
# # 调用函数并输出结果
# invisible_texts = extract_invisible_text(pdf_path)
#
# # 打印输出不可见的文本
# for item in invisible_texts:
#     print(f"Page {item['page']} - Text: {item['text']} | Color: {hex(item['color'])} | Alpha: {item['alpha']} | Size: {item['size']}")
#






# # 遍历 PDF 页数
# for page_num in range(pdf_document.page_count):
#     page = pdf_document.load_page(page_num)
#
#     # 获取该页的图片
#     image_list = page.get_images(full=True)
#
#     for img_index, img in enumerate(image_list):
#         xref = img[0]  # 图像的引用ID
#         image = pdf_document.extract_image(xref)
#         image_bytes = image["image"]  # 图像的字节数据
#
#         # 保存图像到本地
#         with open(f"image_page_{page_num + 1}_{img_index + 1}.png", "wb") as img_file:
#             img_file.write(image_bytes)

# 关闭 PDF 文档
# pdf_document.close()


