@echo off
chcp 65001
setlocal enabledelayedexpansion

echo.
echo =======================================================
echo [环境切换] 正在激活环境: LlamaIndex-base
echo =======================================================
call conda activate LlamaIndex-base

echo.
echo [1/12] 正在运行 SmartPDFLoader...
python SmartPDFLoader.py -i "../../PDF/Homoglyph_Characters/text_version.pdf" -o "Output/homoglyph_characters/SmartPDFLoader_apply_ocr.txt"


echo.
echo [2/12] 正在运行 SmartPDFLoader...
python SmartPDFLoader.py -i "../../PDF/image_version.pdf" -o "Output/image/SmartPDFLoader_apply_ocr.txt"

echo.
echo [3/12] 正在运行 SmartPDFLoader...
python SmartPDFLoader.py -i "../../PDF/Double_Layer/double_layer.pdf" -o "Output/double_layer/SmartPDFLoader_apply_ocr.txt"

echo.
echo [4/12] 正在运行 SmartPDFLoader...
python SmartPDFLoader.py -i "../../PDF/Zero_Width/zero_width.pdf" -o "Output/zero_width/SmartPDFLoader_apply_ocr.txt"

echo.
echo [5/12] 正在运行 SmartPDFLoader...
python SmartPDFLoader.py -i "../../PDF/Out_of_Box/oob_poc_base.pdf" -o "Output/out_of_box/base/SmartPDFLoader_apply_ocr.txt"

echo.
echo [6/12] 正在运行 SmartPDFLoader...
python SmartPDFLoader.py -i "../../PDF/Out_of_Box/oob_poc_cropped.pdf" -o "Output/out_of_box/cropped/SmartPDFLoader_apply_ocr.txt"

echo.
echo [7/12] 正在运行 SmartPDFLoader...
python SmartPDFLoader.py -i "../../PDF/Transparent_Injection/injected_document_Trans.pdf" -o "Output/transparent_injection/SmartPDFLoader_apply_ocr.txt"

echo.
echo [8/12] 正在运行 SmartPDFLoader...
python SmartPDFLoader.py -i "../../PDF/Hidden_OCG/ocg_poc.pdf" -o "Output/hidden_ocg/SmartPDFLoader_apply_ocr.txt"

echo.
echo [9/12] 正在运行 SmartPDFLoader...
python SmartPDFLoader.py -i "../../PDF/Zero_Size/font_0.pdf" -o "Output/zero_size/font_0/SmartPDFLoader_apply_ocr.txt"

echo.
echo [10/12] 正在运行 SmartPDFLoader...
python SmartPDFLoader.py -i "../../PDF/Zero_Size/font_001.pdf" -o "Output/zero_size/font_001/SmartPDFLoader_apply_ocr.txt"

echo.
echo [11/12] 正在运行 SmartPDFLoader...
python SmartPDFLoader.py -i "../../PDF/Zero_Size/font_1.pdf" -o "Output/zero_size/font_1/SmartPDFLoader_apply_ocr.txt"

echo.
echo [12/12] 正在运行 SmartPDFLoader...
python SmartPDFLoader.py -i "../../PDF/Word_Shift/pdf_poc.pdf" -o "Output/word_shift/SmartPDFLoader_apply_ocr.txt"

:: ---------------------------------------------------------
:: 结束
:: ---------------------------------------------------------
echo.
echo =======================================================
echo 所有任务已执行完毕。
pause