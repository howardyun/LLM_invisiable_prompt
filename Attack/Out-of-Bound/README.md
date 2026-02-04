# Out-of-Bound（越界）隐藏文本PDF生成工具

## 功能介绍

本工具用于生成包含"越界隐藏文本"的PDF文件，主要实现以下功能：

1. 读取用户提供的输入PDF文件
2. 在PDF中添加越界隐藏文本（绘制在正常可见区域外）
3. 通过修改PDF的CropBox属性，裁剪可见区域，只显示正常文本
4. 提供解析工具验证隐藏文本是否能被提取

## 文件说明

- `OutOfBoundmain.py`: 主程序文件，用于生成包含越界隐藏文本的PDF文件
- `parse.py`: 解析工具，用于验证生成的PDF中隐藏文本是否能被提取
- `oob_poc_base.pdf`: 程序运行后生成的基础PDF文件（未裁剪）
- `oob_poc_cropped.pdf`: 程序运行后生成的裁剪PDF文件（隐藏了越界文本）
- `README.md`: 本说明文档

## 技术原理

### PDF页面边界
PDF文档中的页面有多个边界定义：
- **MediaBox**: 定义页面的物理尺寸
- **CropBox**: 定义页面的可见区域

### 越界隐藏技术
本工具利用PDF的这一特性，将隐藏文本绘制在MediaBox内但CropBox外的区域：
1. 在基础PDF中，同时绘制正常可见文本和越界隐藏文本
2. 通过修改CropBox，将可见区域缩小，裁剪掉越界的隐藏文本
3. 视觉上，用户只能看到CropBox内的正常文本
4. 但PDF解析工具仍然可以提取到整个MediaBox内的所有文本，包括越界的隐藏文本

## 依赖库

程序依赖以下Python库：

- `reportlab`: 用于创建PDF文件
- `pypdf` 或 `PyPDF2`: 用于修改PDF的CropBox属性

## 安装依赖

```bash
pip install reportlab pypdf
```

## 使用方法

### 生成包含越界隐藏文本的PDF

1. 确保已安装所需依赖库
2. 运行主程序：

```bash
python OutOfBoundmain.py
```

3. 按照提示输入原始PDF文件的路径

4. 运行后将生成两个文件：
   - `oob_poc_base.pdf`: 添加了越界隐藏文本的基础PDF文件
   - `oob_poc_cropped.pdf`: 裁剪后的PDF文件，只显示正常文本，隐藏越界文本

### 验证隐藏文本

1. 运行解析工具：

```bash
python parse.py
```

2. 工具将提取PDF中的所有文本，并检查是否包含隐藏的越界文本

## 生成的PDF内容

### 基础PDF（oob_poc_base.pdf）

- **越界隐藏文本**：
  - 页面顶部外显示 "HIDDEN OOB TEXT: e.g., phishing URL, fake contract terms, or malicious content."
  - 页面右侧外显示 "ANOTHER HIDDEN OOB TEXT placed far to the right."

### 裁剪后的PDF（oob_poc_cropped.pdf）

- **视觉效果**：只显示中间的正常文本，顶部和右侧的越界文本被裁剪掉
- **实际内容**：PDF文件中仍然包含所有文本，包括越界的隐藏文本

## 代码结构

### `OutOfBoundmain.py`

1. **`add_hidden_text_to_pdf`函数**：
   - 读取用户提供的输入PDF文件
   - 获取页面尺寸信息
   - 创建临时画布来绘制越界隐藏文本
   - 在页面可见区域外绘制隐藏文本
   - 将包含隐藏文本的内容合并到原始PDF页面

2. **`crop_pdf_to_hide_oob_text`函数**：
   - 读取添加了隐藏文本的PDF
   - 获取原始页面尺寸
   - 修改页面的CropBox属性，裁剪可见区域
   - 保存裁剪后的PDF文件

### `parse.py`

- 使用pypdf读取PDF文件
- 提取所有文本内容
- 检查是否包含隐藏的越界文本
- 输出提取结果

## 注意事项

1. 不同的PDF查看器对越界内容的处理方式可能不同
2. 某些PDF查看器可能会显示所有内容，而不遵守CropBox的限制
3. 可以根据需要修改代码中的文本内容、位置和裁剪区域
4. 如果使用的是PyPDF2库，需要修改代码中的导入语句