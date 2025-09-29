from paddleocr import PaddleOCR
from pdf2image import convert_from_path
import numpy as np

ocr = PaddleOCR(use_angle_cls=True, lang="ch")
images = convert_from_path("input.pdf", dpi=300)

for img in images:
    arr = np.array(img)[:, :, ::-1]  # RGB → BGR
    result = ocr.ocr(arr, cls=True)
    for line in result:
        print(line[1][0])
