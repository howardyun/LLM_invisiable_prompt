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
pdf_path = '../../../Demo/b289b2d04f9f64ca2ed2fd352b44628f.pdf'
pdf_document = fitz.open(pdf_path)


metadata = pdf_document.metadata
print(metadata)




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


