@echo off
chcp 65001
setlocal enabledelayedexpansion

echo.
echo =======================================================
echo [环境切换] 正在激活环境: LLMSherpa
echo =======================================================
call conda activate LLMSherpa

echo.
echo [1/14] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Homoglyph_Characters/text_version.pdf" -o "Output/homoglyph_characters/SherpaResult.txt" 

echo.
echo [2/14] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/image_version.pdf" -o "Output/image/SherpaResult.txt"

echo.
echo [3/14] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Double_Layer/double_layer.pdf" -o "Output/double_layer/SherpaResult.txt"

echo.
echo [4/14] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Zero_Width/metadata/zero_width.pdf" -o "Output/zero_width/metadata/SherpaResult.txt"

echo.
echo [5/14] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Zero_Width/text/zero_width.pdf" -o "Output/zero_width/text/SherpaResult.txt"

echo.
echo [6/14] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Out_of_Box/oob_poc_base.pdf" -o "Output/out_of_box/base/SherpaResult.txt"

echo.
echo [7/14] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Out_of_Box/oob_poc_cropped.pdf" -o "Output/out_of_box/cropped/SherpaResult.txt"

echo.
echo [8/14] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Transparent_Injection/injected_document_Trans.pdf" -o "Output/transparent_injection/SherpaResult.txt"

echo.
echo [9/14] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Hidden_OCG/ocg_poc.pdf" -o "Output/hidden_ocg/SherpaResult.txt"

echo.
echo [10/14] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Zero_Size/font_0.pdf" -o "Output/zero_size/font_0/SherpaResult.txt"

echo.
echo [11/14] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Zero_Size/font_001.pdf" -o "Output/zero_size/font_001/SherpaResult.txt"

echo.
echo [12/14] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Zero_Size/font_1.pdf" -o "Output/zero_size/font_1/SherpaResult.txt"

echo.
echo [13/14] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Word_Shift/pdf_poc.pdf" -o "Output/word_shift/SherpaResult.txt"

echo.
echo [13/14] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/new/attacked_1765867970442.pdf" -o "Output/new/SherpaResult.txt"

echo.
echo =======================================================
echo [配置切换] 强制OCR
echo =======================================================

echo.
echo [1/14] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Homoglyph_Characters/text_version.pdf" -o "Output/homoglyph_characters/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [2/14] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/image_version.pdf" -o "Output/image/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [3/14] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Double_Layer/double_layer.pdf" -o "Output/double_layer/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [4/14] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Zero_Width/metadata/zero_width.pdf" -o "Output/zero_width/metadata/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [5/14] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Zero_Width/text/zero_width.pdf" -o "Output/zero_width/text/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [6/14] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Out_of_Box/oob_poc_base.pdf" -o "Output/out_of_box/base/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [7/14] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Out_of_Box/oob_poc_cropped.pdf" -o "Output/out_of_box/cropped/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [8/14] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Transparent_Injection/injected_document_Trans.pdf" -o "Output/transparent_injection/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [9/14] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Hidden_OCG/ocg_poc.pdf" -o "Output/hidden_ocg/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [10/14] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Zero_Size/font_0.pdf" -o "Output/zero_size/font_0/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [11/14] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Zero_Size/font_001.pdf" -o "Output/zero_size/font_001/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [12/14] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Zero_Size/font_1.pdf" -o "Output/zero_size/font_1/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [13/14] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Word_Shift/pdf_poc.pdf" -o "Output/word_shift/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [14/14] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/new/attacked_1765867970442.pdf" -o "Output/new/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

:: ---------------------------------------------------------
:: 结束
:: ---------------------------------------------------------
echo.
echo =======================================================
echo 所有任务已执行完毕。
pause