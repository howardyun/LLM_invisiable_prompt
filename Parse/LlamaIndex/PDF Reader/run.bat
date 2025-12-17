@echo off
chcp 65001
setlocal enabledelayedexpansion

:: ================= 配置区域 =================
:: 设置输入 PDF 文件的路径 (建议使用绝对路径，或者相对于脚本的路径)
set "INPUT_FILE=../../PDF/new/attacked_1765867970442.pdf"

:: 设置输出结果的文件夹
set "OUTPUT_DIR=Output/new"

:: 设置 API 地址 (仅 SmartPDFLoader 需要)
set "SMART_API=http://localhost:5001/api/parseDocument?renderFormat=all"
:: ===========================================

echo [开始任务] 正在准备解析...
echo 输入文件: %INPUT_FILE%
echo 输出目录: %OUTPUT_DIR%
echo.

:: 创建输出目录 (虽然 Python 脚本也会创建，但这里先创建是个好习惯)
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

:: ---------------------------------------------------------
:: 第一组: LlamaIndex-base 环境 (包含 6 个脚本)
:: ---------------------------------------------------------
echo.
echo =======================================================
echo [环境切换] 正在激活环境: LlamaIndex-base
echo =======================================================
call conda activate LlamaIndex-base

echo.
echo [1/10] 正在运行 PyMuPDFLoader...
python PyMuPDFLoader.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/PyMuPDFLoader.txt"

echo.
echo [2/10] 正在运行 PDFLoader (Standard)...
python PDFLoader.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/StandardPDF.txt"

echo.
echo [3/10] 正在运行 UnstructuredLoader...
python UnstructuredLoader.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/UnstructuredLoader.txt"

echo.
echo [4/10] 正在运行 PDFTableLoader...
python PDFTableLoader.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/PDFTable.txt" -p "all"

echo.
echo [5/10] 正在运行 PaddleOCRLoader...
python PaddleOCRLoader.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/PaddleOCR.txt" --lang en

echo.
echo [6/10] 正在运行 SmartPDFLoader...
python SmartPDFLoader.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/SmartPDFLoader.txt" --api "%SMART_API%"

echo.
echo [7/10] 正在运行 SmartPDFLoader...
python SmartPDFLoader.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/SmartPDFLoader_apply_ocr.txt" --api "%SMART_API%&applyOcr=yes"

:: ---------------------------------------------------------
:: 第二组: LlamaIndex-nougat 环境 (包含 1 个脚本)
:: ---------------------------------------------------------
echo.
echo =======================================================
echo [环境切换] 正在激活环境: LlamaIndex-nougat
echo =======================================================
call conda activate LlamaIndex-nougat

echo.
echo [8/10] 正在运行 NougatOCRLoader...
python NougatOCRLoader.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/NougatOCR.txt"

:: ---------------------------------------------------------
:: 第三组: LlamaIndex-marker 环境 (包含 1 个脚本)
:: ---------------------------------------------------------
echo.
echo =======================================================
echo [环境切换] 正在激活环境: LlamaIndex-marker
echo =======================================================
call conda activate LlamaIndex-marker

echo.
echo [9/10] 正在运行 PDFMarkerLoader...
python PDFMarkerLoader.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/PDFMarkerLoader.txt"

:: ---------------------------------------------------------
:: 第四组: LlamaIndex-docling 环境 (包含 1 个脚本)
:: ---------------------------------------------------------
echo.
echo =======================================================
echo [环境切换] 正在激活环境: LlamaIndex-docling
echo =======================================================
call conda activate LlamaIndex-docling

echo.
echo [10/10] 正在运行 DoclingLoader...
python DoclingLoader.py -i "%INPUT_FILE%" -o "%OUTPUT_DIR%/DoclingLoader.txt"

:: ---------------------------------------------------------
:: 结束
:: ---------------------------------------------------------
echo.
echo =======================================================
echo 所有任务已执行完毕。
echo 请检查 %OUTPUT_DIR% 目录下的结果。
echo =======================================================
pause