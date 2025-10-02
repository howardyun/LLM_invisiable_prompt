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
pdf_path = '../../../Data/DGA_IWQOS2025.pdf'

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
pdf_document.close()


