@echo off
chcp 65001
setlocal enabledelayedexpansion

echo.
echo =======================================================
echo [环境切换] 正在激活环境: Docling
echo =======================================================
call conda activate Docling

echo.
echo [1/14] 正在运行 Docling...
python Docling.py -i "../../PDF/Homoglyph_Characters/text_version.pdf" -o "Output/homoglyph_characters/DoclingLoader.txt"

echo.
echo [2/14] 正在运行 Docling...
python Docling.py -i "../../PDF/image_version.pdf" -o "Output/image/DoclingLoader.txt"

echo.
echo [3/14] 正在运行 Docling...
python Docling.py -i "../../PDF/Double_Layer/double_layer.pdf" -o "Output/double_layer/DoclingLoader.txt"

echo.
echo [4/14] 正在运行 Docling...
python Docling.py -i "../../PDF/Zero_Width/metadata/zero_width.pdf" -o "Output/zero_width/metadata/DoclingLoader.txt"

echo.
echo [5/14] 正在运行 Docling...
python Docling.py -i "../../PDF/Zero_Width/text/zero_width.pdf" -o "Output/zero_width/text/DoclingLoader.txt"

echo.
echo [6/14] 正在运行 Docling...
python Docling.py -i "../../PDF/Out_of_Box/oob_poc_base.pdf" -o "Output/out_of_box/base/DoclingLoader.txt"

echo.
echo [7/14] 正在运行 Docling...
python Docling.py -i "../../PDF/Out_of_Box/oob_poc_cropped.pdf" -o "Output/out_of_box/cropped/DoclingLoader.txt"

echo.
echo [8/14] 正在运行 Docling...
python Docling.py -i "../../PDF/Transparent_Injection/injected_document_Trans.pdf" -o "Output/transparent_injection/DoclingLoader.txt"

echo.
echo [9/14] 正在运行 Docling...
python Docling.py -i "../../PDF/Hidden_OCG/ocg_poc.pdf" -o "Output/hidden_ocg/DoclingLoader.txt"

echo.
echo [10/14] 正在运行 Docling...
python Docling.py -i "../../PDF/Zero_Size/font_0.pdf" -o "Output/zero_size/font_0/DoclingLoader.txt"

echo.
echo [11/14] 正在运行 Docling...
python Docling.py -i "../../PDF/Zero_Size/font_001.pdf" -o "Output/zero_size/font_001/DoclingLoader.txt"

echo.
echo [12/14] 正在运行 Docling...
python Docling.py -i "../../PDF/Zero_Size/font_1.pdf" -o "Output/zero_size/font_1/DoclingLoader.txt"

echo.
echo [13/14] 正在运行 Docling...
python Docling.py -i "../../PDF/Word_Shift/pdf_poc.pdf" -o "Output/word_shift/DoclingLoader.txt"

echo.
echo [13/14] 正在运行 Docling...
python Docling.py -i "../../PDF/Word_Shift/pdf_poc.pdf" -o "Output/word_shift/DoclingLoader.txt"

echo.
echo [14/14] 正在运行 Docling...
python Docling.py -i "../../PDF/new/attacked_1765867970442.pdf" -o "Output/new/DoclingLoader.txt"


echo.
echo =======================================================
echo [配置切换] 强制OCR
echo =======================================================

echo.
echo [1/14] 正在运行 Docling...
python Docling.py -i "../../PDF/Homoglyph_Characters/text_version.pdf" -o "Output/homoglyph_characters/DoclingLoader_force_ocr.txt" --ocr

echo.
echo [2/14] 正在运行 Docling...
python Docling.py -i "../../PDF/image_version.pdf" -o "Output/image/DoclingLoader_force_ocr.txt" --ocr

echo.
echo [3/14] 正在运行 Docling...
python Docling.py -i "../../PDF/Double_Layer/double_layer.pdf" -o "Output/double_layer/DoclingLoader_force_ocr.txt" --ocr

echo.
echo [4/14] 正在运行 Docling...
python Docling.py -i "../../PDF/Zero_Width/metadata/zero_width.pdf" -o "Output/zero_width/metadata/DoclingLoader_force_ocr.txt" --ocr

echo.
echo [5/14] 正在运行 Docling...
python Docling.py -i "../../PDF/Zero_Width/text/zero_width.pdf" -o "Output/zero_width/text/DoclingLoader_force_ocr.txt" --ocr

echo.
echo [6/14] 正在运行 Docling...
python Docling.py -i "../../PDF/Out_of_Box/oob_poc_base.pdf" -o "Output/out_of_box/base/DoclingLoader_force_ocr.txt" --ocr

echo.
echo [7/14] 正在运行 Docling...
python Docling.py -i "../../PDF/Out_of_Box/oob_poc_cropped.pdf" -o "Output/out_of_box/cropped/DoclingLoader_force_ocr.txt" --ocr

echo.
echo [8/14] 正在运行 Docling...
python Docling.py -i "../../PDF/Transparent_Injection/injected_document_Trans.pdf" -o "Output/transparent_injection/DoclingLoader_force_ocr.txt" --ocr

echo.
echo [9/14] 正在运行 Docling...
python Docling.py -i "../../PDF/Hidden_OCG/ocg_poc.pdf" -o "Output/hidden_ocg/DoclingLoader_force_ocr.txt" --ocr

echo.
echo [10/14] 正在运行 Docling...
python Docling.py -i "../../PDF/Zero_Size/font_0.pdf" -o "Output/zero_size/font_0/DoclingLoader_force_ocr.txt" --ocr

echo.
echo [11/14] 正在运行 Docling...
python Docling.py -i "../../PDF/Zero_Size/font_001.pdf" -o "Output/zero_size/font_001/DoclingLoader_force_ocr.txt" --ocr

echo.
echo [12/14] 正在运行 Docling...
python Docling.py -i "../../PDF/Zero_Size/font_1.pdf" -o "Output/zero_size/font_1/DoclingLoader_force_ocr.txt" --ocr

echo.
echo [13/14] 正在运行 Docling...
python Docling.py -i "../../PDF/Word_Shift/pdf_poc.pdf" -o "Output/word_shift/DoclingLoader_force_ocr.txt" --ocr

echo.
echo [14/14] 正在运行 Docling...
python Docling.py -i "../../PDF/new/attacked_1765867970442.pdf" -o "Output/new/DoclingLoader_force_ocr.txt" --ocr

:: ---------------------------------------------------------
:: 结束
:: ---------------------------------------------------------
echo.
echo =======================================================
echo 所有任务已执行完毕。
pause