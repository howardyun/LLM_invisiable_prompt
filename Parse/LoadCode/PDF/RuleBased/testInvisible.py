from langchain_community.document_loaders import PyPDFLoader


pdf_loader = PyPDFLoader('../../../../Data/PDF/pdf_poc.pdf')
pages = pdf_loader.load_and_split()
page_content = pages[0].page_content
# page_content1 = pages[1].page_content

print(page_content)
# print(page_content1)
