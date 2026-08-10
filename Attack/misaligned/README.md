# 错位文本PDF攻击工具

## 功能介绍

本工具用于生成包含视觉正常但解析顺序错位的PDF文件，主要实现以下功能：

1. 打开并处理现有的PDF文件
2. 在PDF中注入恶意指令文本
3. 通过调整文本绘制顺序实现错位攻击
4. 保持视觉正常的同时改变解析顺序

## 文件说明

- `Misaligned_Main.py`: 主程序文件，包含生成错位文本PDF的核心功能
- `README.md`: 本说明文档

## 依赖库

程序依赖以下Python库：

- `fitz` (PyMuPDF): 用于操作PDF文件和绘制文本内容

## 安装依赖

```bash
pip install pymupdf
```

## 功能实现细节

### 1. 攻击原理

`create_misaligned_pdf` 函数用于创建包含错位文本效果的PDF文件：

- 打开输入PDF文件
- 定义要注入的恶意指令文本
- 对目标页面应用错位攻击
- 保持非目标页面不变

### 2. 文本错位处理

程序对每个注入的句子执行以下错位处理：

1. 将句子按空格分割成单词列表
2. 先绘制除去第一个单词后的剩余部分
3. 将所有句子的第一个单词延迟到最后绘制
4. 这样在PDF对象的TextContent逻辑顺序中，这些单词全部排在最后
5. 视觉上保持正常，但解析顺序发生变化

### 3. 坐标计算

- 使用fitz库计算文本宽度
- 计算合适的行高和起始位置
- 确保文本绘制在页面可见区域内

## 使用方法

### 作为独立工具使用

1. 确保已安装所需依赖库
2. 在Python代码中导入并调用函数：

```python
from misaligned.Misaligned_Main import create_misaligned_pdf

# 对所有页面进行攻击
create_misaligned_pdf('input.pdf', 'output.pdf')

# 只对特定页面进行攻击（0-based）
create_misaligned_pdf('input.pdf', 'output.pdf', target_page=0)
```

### 作为auto_attack的一部分使用

该工具已集成到auto_attack.py中，可以通过指定攻击方法来使用：

```bash
python auto_attack.py input_dir output_dir --methods misaligned
```

## 注意事项

1. 本工具仅用于安全研究和教育目的
2. 注入的恶意指令文本可以根据需要修改
3. 可以通过调整font_size和line_height参数来改变文本显示效果
4. 目标页面参数为0-based索引

## 攻击效果

生成的PDF文件在视觉上看起来正常，但在解析时，每行的第一个单词会被解析器最后处理。这种错位攻击可能会被某些PDF解析器或LLM处理PDF的方式利用，从而导致安全问题。