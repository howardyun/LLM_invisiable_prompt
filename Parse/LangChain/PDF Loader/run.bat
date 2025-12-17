@echo off
chcp 65001
setlocal enabledelayedexpansion

:: ================= 配置区域 =================
:: 设置 Python 解释器路径
set PYTHON_EXE=python

:: 设置输入文件路径 (支持相对路径)
set "INPUT_FILE=../../PDF/new/attacked_1765867970442.pdf"

:: 设置输入目录 (供 PyPDFDirectory 使用)
set "INPUT_DIR=../../PDF/new"

:: 设置输出文件夹名称
set "OUTPUT_DIR=Output/new"
:: ===========================================

echo [INFO] 开始全量自动化测试...
echo [INFO] 输入文件: %INPUT_FILE%
echo [INFO] 输出目录: %OUTPUT_DIR%

:: 自动创建输出目录
if not exist "%OUTPUT_DIR%" (
    md "%OUTPUT_DIR%"
)

call conda activate LangChain

echo.
echo ==========================================
echo 1. 运行 PyPDFLoader (基础解析)
echo ==========================================
%PYTHON_EXE% PyPDFLoader.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/PyPDFLoader.txt"

echo.
echo ==========================================
echo 2. 运行 PyMuPDF (极速解析)
echo ==========================================
%PYTHON_EXE% PyMuPDF.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/PyMuPDFLoader.txt"

echo.
echo ==========================================
echo 3. 运行 PyMuPDF4LLM (Markdown 格式)
echo ==========================================
%PYTHON_EXE% PyMuPDF4LLM.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/PyMuPDF4LLMLoader.txt"

echo.
echo ==========================================
echo 4. 运行 PDFPlumber (复杂布局/表格)
echo ==========================================
%PYTHON_EXE% PDFPlumber.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/PDFPlumberLoader.txt"

echo.
echo ==========================================
echo 5. 运行 PyPDFium2 (Google 引擎)
echo ==========================================
%PYTHON_EXE% PyPDFium2.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/PyPDFium2Loader.txt"

echo.
echo ==========================================
echo 6. 运行 PDFMiner (布局分析)
echo ==========================================
if exist PDFMiner.py (
    %PYTHON_EXE% PDFMiner.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/PDFMinerLoader.txt"
) else (
    echo [SKIP] 未找到 PDFMiner.py，跳过。
)

echo.
echo ==========================================
echo 7. 运行 Docling (多模式测试)
echo ==========================================
:: 7.1 默认模式
echo [Docling 1/2] Default Mode...
%PYTHON_EXE% Docling.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/DoclingLoader.txt"

:: 7.2 强制 OCR 模式
echo [Docling 2/2] Force OCR Mode...
%PYTHON_EXE% Docling.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/DoclingLoader_force_ocr.txt" --force_ocr

echo.
echo ==========================================
echo 8. 运行 OpenDataLoader (安全过滤测试)
echo ==========================================
:: 8.1 Default
echo [OpenData 1/6] Default...
%PYTHON_EXE% OpenDataLoader.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/OpenDataLoader.txt" --safety default

:: 8.2 All (关闭安全过滤)
echo [OpenData 2/6] All Safety Off...
%PYTHON_EXE% OpenDataLoader.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/OpenDataLoader_all.txt" --safety all

:: 8.3 Hidden Text
echo [OpenData 3/6] Hidden Text...
%PYTHON_EXE% OpenDataLoader.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/OpenDataLoader_hidden_text.txt" --safety hidden-text

:: 8.4 Off Page
echo [OpenData 4/6] Off Page...
%PYTHON_EXE% OpenDataLoader.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/OpenDataLoader_off_page.txt" --safety off-page

:: 8.5 Tiny Text
echo [OpenData 5/6] Tiny Text...
%PYTHON_EXE% OpenDataLoader.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/OpenDataLoader_tiny.txt" --safety tiny

:: 8.6 Hidden OCG
echo [OpenData 6/6] Hidden OCG...
%PYTHON_EXE% OpenDataLoader.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/OpenDataLoader_hidden_ocg.txt" --safety hidden-ocg

echo.
echo ==========================================
echo 9. 运行 Unstructured (多策略测试)
echo ==========================================
:: 9.1 Fast
echo [Unstructured 1/3] Fast Strategy...
%PYTHON_EXE% Unstructured.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/UnstructuredLoader_fast.txt" --strategy fast

:: 9.2 Hi_res
echo [Unstructured 2/3] Hi-Res Strategy...
%PYTHON_EXE% Unstructured.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/UnstructuredLoader_hi_res.txt" --strategy hi_res

:: 9.3 OCR Only
echo [Unstructured 3/3] OCR Only Strategy...
%PYTHON_EXE% Unstructured.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/UnstructuredLoader_ocr_only.txt" --strategy ocr_only

echo.
echo ==========================================
echo 10. 运行 PyPDFDirectory (批量加载目录)
echo ==========================================
%PYTHON_EXE% PyPDFDirectory.py -i "%INPUT_DIR%" -o "%OUTPUT_DIR%/PyPDFDirectoryLoader.txt"

echo.
echo ==========================================
echo [SUCCESS] 所有任务执行完毕！
echo 请查看 %OUTPUT_DIR% 文件夹下的结果。
echo ==========================================
pause