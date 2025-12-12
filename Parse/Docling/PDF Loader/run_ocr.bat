@echo off
chcp 65001
setlocal enabledelayedexpansion

echo.
echo =======================================================
echo [环境切换] 正在激活环境: Docling
echo =======================================================
call conda activate Docling

echo.
echo =======================================================
echo [配置切换] 强制OCR
echo =======================================================

echo.
echo [1/13] 正在运行 Docling...
python Docling.py -i "../../PDF/Homoglyph_Characters/text_version.pdf" -o "Output/homoglyph_characters/DoclingLoader_force_ocr.txt" --ocr

echo.
echo [2/13] 正在运行 Docling...
python Docling.py -i "../../PDF/image_version.pdf" -o "Output/image/DoclingLoader_force_ocr.txt" --ocr

echo.
echo [3/13] 正在运行 Docling...
python Docling.py -i "../../PDF/Double_Layer/double_layer.pdf" -o "Output/double_layer/DoclingLoader_force_ocr.txt" --ocr

echo.
echo [4/13] 正在运行 Docling...
python Docling.py -i "../../PDF/Zero_Width/metadata/zero_width.pdf" -o "Output/zero_width/metadata/DoclingLoader_force_ocr.txt" --ocr

echo.
echo [5/13] 正在运行 Docling...
python Docling.py -i "../../PDF/Zero_Width/text/zero_width.pdf" -o "Output/zero_width/text/DoclingLoader_force_ocr.txt" --ocr

echo.
echo [6/13] 正在运行 Docling...
python Docling.py -i "../../PDF/Out_of_Box/oob_poc_base.pdf" -o "Output/out_of_box/base/DoclingLoader_force_ocr.txt" --ocr

echo.
echo [7/13] 正在运行 Docling...
python Docling.py -i "../../PDF/Out_of_Box/oob_poc_cropped.pdf" -o "Output/out_of_box/cropped/DoclingLoader_force_ocr.txt" --ocr

echo.
echo [8/13] 正在运行 Docling...
python Docling.py -i "../../PDF/Transparent_Injection/injected_document_Trans.pdf" -o "Output/transparent_injection/DoclingLoader_force_ocr.txt" --ocr

echo.
echo [9/13] 正在运行 Docling...
python Docling.py -i "../../PDF/Hidden_OCG/ocg_poc.pdf" -o "Output/hidden_ocg/DoclingLoader_force_ocr.txt" --ocr

echo.
echo [10/13] 正在运行 Docling...
python Docling.py -i "../../PDF/Zero_Size/font_0.pdf" -o "Output/zero_size/font_0/DoclingLoader_force_ocr.txt" --ocr

echo.
echo [11/13] 正在运行 Docling...
python Docling.py -i "../../PDF/Zero_Size/font_001.pdf" -o "Output/zero_size/font_001/DoclingLoader_force_ocr.txt" --ocr

echo.
echo [12/13] 正在运行 Docling...
python Docling.py -i "../../PDF/Zero_Size/font_1.pdf" -o "Output/zero_size/font_1/DoclingLoader_force_ocr.txt" --ocr

echo.
echo [13/13] 正在运行 Docling...
python Docling.py -i "../../PDF/Word_Shift/pdf_poc.pdf" -o "Output/word_shift/DoclingLoader_force_ocr.txt" --ocr

:: ---------------------------------------------------------
:: 结束
:: ---------------------------------------------------------
echo.
echo =======================================================
echo 所有任务已执行完毕。
pause