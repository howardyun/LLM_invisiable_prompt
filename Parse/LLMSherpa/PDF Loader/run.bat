@echo off
chcp 65001
setlocal enabledelayedexpansion

echo.
echo =======================================================
echo [环境切换] 正在激活环境: LLMSherpa
echo =======================================================
call conda activate LLMSherpa

echo.
echo [1/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Homoglyph_Characters/text_version.pdf" -o "Output/homoglyph_characters/SherpaResult.txt"

echo.
echo [2/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/image_version.pdf" -o "Output/image/SherpaResult.txt"

echo.
echo [3/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Double_Layer/double_layer.pdf" -o "Output/double_layer/SherpaResult.txt"

echo.
echo [4/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Zero_Width/metadata/zero_width.pdf" -o "Output/zero_width/metadata/SherpaResult.txt"

echo.
echo [5/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Zero_Width/text/zero_width.pdf" -o "Output/zero_width/text/SherpaResult.txt"

echo.
echo [6/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Out_of_Box/oob_poc_base.pdf" -o "Output/out_of_box/base/SherpaResult.txt"

echo.
echo [7/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Out_of_Box/oob_poc_cropped.pdf" -o "Output/out_of_box/cropped/SherpaResult.txt"

echo.
echo [8/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Transparent_Injection/injected_document_Trans.pdf" -o "Output/transparent_injection/SherpaResult.txt"

echo.
echo [9/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Hidden_OCG/ocg_poc.pdf" -o "Output/hidden_ocg/SherpaResult.txt"

echo.
echo [10/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Zero_Size/font_0.pdf" -o "Output/zero_size/font_0/SherpaResult.txt"

echo.
echo [11/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Zero_Size/font_001.pdf" -o "Output/zero_size/font_001/SherpaResult.txt"

echo.
echo [12/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Zero_Size/font_1.pdf" -o "Output/zero_size/font_1/SherpaResult.txt"

echo.
echo [13/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Word_Shift/pdf_poc.pdf" -o "Output/word_shift/SherpaResult.txt"

echo.
echo [14/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/new/attacked_1765867970442.pdf" -o "Output/new/SherpaResult.txt"

echo.
echo [15/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Shadow/32953_EGGS_Expert_Guided_Frame.pdf" -o "Output/shadow/SherpaResult.txt"

echo.
echo [16/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/TRM3/text_render_mode_3_invisible_text_poc.pdf" -o "Output/TRM3/SherpaResult.txt"

echo.
echo [17/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/TRM3/poc_tr3_tj_fragmented.pdf" -o "Output/TRM3/tj_fragmented/SherpaResult.txt"

echo.
echo [18/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/TRM3/poc_tr3_tiny_matrix.pdf" -o "Output/TRM3/tiny_matrix/SherpaResult.txt"

echo.
echo [19/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/TRM3/poc_tr3_marked_content_artifact.pdf" -o "Output/TRM3/marked_content_artifact/SherpaResult.txt"

echo.
echo [20/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/OCG/ocg_hidden_poc.pdf" -o "Output/ocg/SherpaResult.txt"

echo.
echo =======================================================
echo [配置切换] 强制OCR
echo =======================================================

echo.
echo [1/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Homoglyph_Characters/text_version.pdf" -o "Output/homoglyph_characters/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [2/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/image_version.pdf" -o "Output/image/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [3/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Double_Layer/double_layer.pdf" -o "Output/double_layer/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [4/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Zero_Width/metadata/zero_width.pdf" -o "Output/zero_width/metadata/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [5/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Zero_Width/text/zero_width.pdf" -o "Output/zero_width/text/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [6/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Out_of_Box/oob_poc_base.pdf" -o "Output/out_of_box/base/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [7/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Out_of_Box/oob_poc_cropped.pdf" -o "Output/out_of_box/cropped/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [8/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Transparent_Injection/injected_document_Trans.pdf" -o "Output/transparent_injection/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [9/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Hidden_OCG/ocg_poc.pdf" -o "Output/hidden_ocg/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [10/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Zero_Size/font_0.pdf" -o "Output/zero_size/font_0/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [11/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Zero_Size/font_001.pdf" -o "Output/zero_size/font_001/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [12/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Zero_Size/font_1.pdf" -o "Output/zero_size/font_1/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [13/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Word_Shift/pdf_poc.pdf" -o "Output/word_shift/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [14/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/new/attacked_1765867970442.pdf" -o "Output/new/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [15/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/Shadow/32953_EGGS_Expert_Guided_Frame.pdf" -o "Output/shadow/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [16/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/TRM3/text_render_mode_3_invisible_text_poc.pdf" -o "Output/TRM3/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [17/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/TRM3/poc_tr3_tj_fragmented.pdf" -o "Output/TRM3/tj_fragmented/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [18/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/TRM3/poc_tr3_tiny_matrix.pdf" -o "Output/TRM3/tiny_matrix/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [19/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/TRM3/poc_tr3_marked_content_artifact.pdf" -o "Output/TRM3/marked_content_artifact/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

echo.
echo [20/20] 正在运行 LLMSherpa...
python LLMSherpa.py -i "../../PDF/OCG/ocg_hidden_poc.pdf" -o "Output/ocg/SherpaResult_apply_ocr.txt" --api "http://localhost:5001/api/parseDocument?renderFormat=all&applyOcr=yes"

:: ---------------------------------------------------------
:: 结束
:: ---------------------------------------------------------
echo.
echo =======================================================
echo 所有任务已执行完毕。
pause