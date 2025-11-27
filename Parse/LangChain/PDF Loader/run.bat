@echo off
chcp 65001
setlocal

:: ================= 配置区域 =================
:: 设置 Python 解释器路径
set PYTHON_EXE=python

:: 设置输入文件路径 (支持相对路径，这里假设 doc.pdf 在上一级目录)
set "INPUT_FILE=..\PDF\image_version.pdf"

:: 设置输入目录 (供 PyPDFDirectory 使用，这里设为上一级目录)
set "INPUT_DIR=../PDF"

:: 设置输出文件夹名称
set "OUTPUT_DIR=Output/image"
:: ===========================================

echo [INFO] 开始自动化测试...
echo [INFO] 输入文件: %INPUT_FILE%
echo [INFO] 输出目录: %OUTPUT_DIR%

echo.
echo ==========================================
echo 1. 运行 PyPDFLoader (基础解析)
echo ==========================================
%PYTHON_EXE% PyPDFLoader.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%\PyPDFLoader.txt"

echo.
echo ==========================================
echo 2. 运行 PyMuPDF (极速解析)
echo ==========================================
%PYTHON_EXE% PyMuPDF.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%\PyMuPDFLoader.txt"

echo.
echo ==========================================
echo 3. 运行 PyMuPDF4LLM (Markdown 格式)
echo ==========================================
%PYTHON_EXE% PyMuPDF4LLM.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%\PyMuPDF4LLMLoader.txt"

echo.
echo ==========================================
echo 4. 运行 PDFPlumber (复杂布局/表格)
echo ==========================================
%PYTHON_EXE% PDFPlumber.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%\PDFPlumberLoader.txt"

echo.
echo ==========================================
echo 5. 运行 PyPDFium2 (Google 引擎)
echo ==========================================
%PYTHON_EXE% PyPDFium2.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%\PyPDFium2Loader.txt"

echo.
echo ==========================================
echo 6. 运行 PDFMiner (布局分析)
echo ==========================================
:: 注意：如果你保存的文件名不是 PDFMiner.py，请修改此处
if exist PDFMiner.py (
    %PYTHON_EXE% PDFMiner.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%\PDFMinerLoader.txt"
) else (
    echo [SKIP] 未找到 PDFMiner.py，跳过。
)

echo.
echo ==========================================
echo 7. 运行 Docling (OCR/文档理解)
echo ==========================================
%PYTHON_EXE% Docling.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%\DoclingLoader.txt"

echo.
echo ==========================================
echo 8. 运行 OpenDataLoader (Java/Markdown)
echo ==========================================
%PYTHON_EXE% OpenDataLoader.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%\OpenDataLoader.txt"

echo.
echo ==========================================
echo 9. 运行 Unstructured (OCR/非结构化)
echo ==========================================
%PYTHON_EXE% Unstructured.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%\UnstructuredLoader_hi_res.txt"

echo.
echo ==========================================
echo 10. 运行 PyPDFDirectory (批量加载目录)
echo ==========================================
:: 注意：这里传入的是 INPUT_DIR (文件夹路径) 而不是文件路径
%PYTHON_EXE% PyPDFDirectory.py -i "%INPUT_DIR%" -o "%OUTPUT_DIR%\PyPDFDirectoryLoader.txt"

echo.
echo ==========================================
echo [SUCCESS] 所有任务执行完毕！
echo 请查看 %OUTPUT_DIR% 文件夹下的结果。
echo ==========================================
pause