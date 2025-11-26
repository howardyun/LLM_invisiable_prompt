### Before You Run this Script , please install package  phantomtext
### pip install phantomtext

from phantomtext.file_scanning import FileScanner

scanner = FileScanner()

# Scan a single file
# result = scanner.scan_file('../Data/PDF/pdf_poc.pdf')
result = scanner.scan_file('../Data/PDF/DGA_IWQOS2025Malicious.pdf')
# result = scanner.scan_file('injected_document.pdf')
# result = scanner.scan_file('injected_document_Trans.pdf')

print(f"Malicious content found: {result['malicious_content_found']}")
print(f"Vulnerabilities: {result['vulnerabilities']}")



# # Scan an entire directory
# reports = scanner.scan_dir('./output')
# for report in reports:
#     if report['malicious_content_found']:
#         print(f"⚠️ Issues found in {report['file_path']}")
#         for vulnerability in report['vulnerabilities']:
#             print(f"  - {vulnerability}")