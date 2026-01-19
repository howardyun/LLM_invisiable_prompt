# 双层PDF生成工具

## 功能介绍

本工具用于生成包含双层内容（文字层和图片层）的PDF文件，主要实现以下功能：

1. 将指定图片转换为图片层PDF
2. 合并用户提供的文字层PDF和生成的图片层PDF
3. 生成最终的双层PDF文件

## 文件说明

- `double_layer_pdf.py`: 主程序文件，包含生成和合并PDF的核心功能
- `case3.png`: 用于演示的示例图片文件
- `README.md`: 本说明文档

## 依赖库

程序依赖以下Python库：

- `reportlab`: 用于创建PDF文件和绘制内容
- `PyPDF2`: 用于合并PDF文件

## 安装依赖

```bash
pip install reportlab PyPDF2
```

## 功能实现细节

### 1. 创建图片层PDF

`create_image_pdf` 函数用于将指定图片转换为PDF文件：

- 创建一个新的PDF页面
- 将指定图片绘制在PDF页面上

### 2. 合并PDF文件

`merge_pdfs` 函数用于合并两个PDF文件：

- 首先读取用户提供的文字层PDF和生成的图片层PDF
- 然后将文字层合并到图片层上
- 最后生成最终的双层PDF文件

## 使用方法

1. 确保已安装所需依赖库
2. 运行脚本：

```bash
python double_layer_pdf.py
```

3. 按照提示输入：
   - 图片文件路径
   - 文字层PDF文件路径
   - 输出PDF文件路径（可选，默认使用 `merged_double_layer.pdf`）

4. 运行后将生成最终的双层PDF文件

## 注意事项

1. 确保示例图片 `case3.png` 存在于脚本同一目录下
2. 可以根据需要修改文字内容、字体、位置和图片路径
3. 合并PDF时，假设两个PDF的页面大小和数量相同