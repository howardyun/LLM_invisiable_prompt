@echo off
chcp 65001
setlocal enabledelayedexpansion

:: ================= 配置区域 =================
:: 设置 Python 解释器路径
set PYTHON_EXE=python

:: 设置输入文件路径 (支持相对路径)
set "INPUT_FILE=../../PDF/OCG/ocg_hidden_poc.pdf"

:: 设置输出文件夹名称
set "OUTPUT_DIR=Output/ocg"
:: ===========================================

echo [INFO] 开始全量自动化测试...
echo [INFO] 输入文件: %INPUT_FILE%
echo [INFO] 输出目录: %OUTPUT_DIR%

:: 自动创建输出目录
if not exist "%OUTPUT_DIR%" (
    md "%OUTPUT_DIR%"
)

call conda activate Haystack-base

echo.
echo ==========================================
echo 1. 运行 PyPDFToDocument
echo ==========================================
%PYTHON_EXE% PyPDFToDocument.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/PyPDFToDocument.txt"

echo.
echo ==========================================
echo 2. 运行 MultiFileConverter
echo ==========================================
%PYTHON_EXE% MultiFileConverter.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/MultiFileConverter.txt"

echo.
echo ==========================================
echo 3. 运行 PDFMinerToDocument
echo ==========================================
%PYTHON_EXE% PDFMinerToDocument.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/PDFMinerToDocument.txt"

echo.
echo ==========================================
echo 4. 运行 UnstructuredFileConverter
echo ==========================================
%PYTHON_EXE% UnstructuredFileConverter.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/UnstructuredFileConverter.txt"

echo.
echo ==========================================
echo 5. 运行 TiKaDocumentConverter
echo ==========================================
%PYTHON_EXE% TiKaDocumentConverter.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/TiKaDocumentConverter.txt"


echo.
echo ==========================================
echo [SUCCESS] 所有任务执行完毕！
echo 请查看 %OUTPUT_DIR% 文件夹下的结果。
echo ==========================================
pause