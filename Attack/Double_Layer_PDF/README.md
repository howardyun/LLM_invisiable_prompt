# 双层PDF生成工具

## 功能介绍

本工具用于生成包含双层内容（文字层和图片层）的PDF文件，主要实现以下功能：

1. **传统模式**：将指定图片转换为图片层PDF，然后与文字层PDF合并
2. **关键词覆盖模式**：使用图片自动覆盖文字层PDF中的指定关键词

## 文件说明

- `double_layer_pdf.py`: 主程序文件，包含生成和合并PDF的核心功能
- `case3.png`: 用于演示的示例图片文件
- `README.md`: 本说明文档

## 依赖库

程序依赖以下Python库：

- `reportlab`: 用于创建PDF文件和绘制内容
- `PyPDF2`: 用于合并PDF文件
- `PyMuPDF` (fitz): 用于提取PDF文本位置信息（关键词覆盖模式需要）

## 安装依赖

```bash
pip install reportlab PyPDF2 PyMuPDF
```

## 功能实现细节

### 1. 传统模式

- `create_image_pdf` 函数：将指定图片转换为PDF文件
  - 创建一个新的PDF页面
  - 将指定图片绘制在PDF页面上

- `merge_pdfs` 函数：合并两个PDF文件
  - 读取用户提供的文字层PDF和生成的图片层PDF
  - 将文字层合并到图片层上
  - 生成最终的双层PDF文件

### 2. 关键词覆盖模式

- `find_keyword_positions_v2` 函数：使用 PyMuPDF 内置搜索功能精确获取关键词坐标
  - 利用 PDF 渲染引擎底层支持的搜索功能
  - 直接返回关键词的精确 Rect 坐标
  - 支持跨字体、跨字间距的精确匹配

- `create_image_pdf_with_keywords` 函数：根据精确坐标创建覆盖层
  - 动态获取每一页的真实页面尺寸
  - 简单准确的坐标转换
  - 图片完全覆盖关键词区域

- `merge_pdfs_with_keyword_cover` 函数：使用图片覆盖文字层PDF中的关键词
  - 使用内置引擎搜索关键词位置
  - 创建图片层PDF
  - 合并PDF文件

## 使用方法

### 方法1：直接运行脚本

1. 确保已安装所需依赖库
2. 运行脚本：

```bash
python double_layer_pdf.py
```

3. 选择模式：
   - `1`：传统模式 - 将图片和文字层PDF合并
   - `2`：关键词覆盖模式 - 使用图片覆盖关键词

4. 根据选择的模式输入相应信息：

#### 传统模式
- 图片文件路径（可输入多个，输入'done'结束）
- 每个图片对应的页码
- 文字层PDF文件路径
- 输出PDF文件路径（可选）

#### 关键词覆盖模式
- 文字层PDF文件路径
- 用于覆盖的图片文件路径
- 要覆盖的关键词（逗号分隔，如：`This,is,a,test,PDF`）
- 覆盖区域的额外边距（默认：2）
- 输出PDF文件路径（可选）

### 方法2：通过auto_attack.py

1. 回到Attack目录
2. 运行：

```bash
python auto_attack.py
```

3. 选择攻击方法 `1`（Double_Layer_PDF）
4. 选择模式 `2`（关键词覆盖模式）
5. 按照提示输入相关信息

### 方法3：编程调用

```python
from double_layer_pdf import merge_pdfs_with_keyword_cover

# 使用图片覆盖关键词
merge_pdfs_with_keyword_cover(
    text_pdf='input.pdf',       # 文字层PDF文件路径
    image_path='cover.png',      # 用于覆盖的图片文件路径
    keywords=['kill', 'attack', 'hate'],  # 要覆盖的关键词列表
    output_file='output.pdf',    # 输出PDF文件路径
    padding=2                   # 覆盖区域的额外边距
)
```

## 注意事项

1. 确保示例图片 `case3.png` 存在于脚本同一目录下
2. 关键词覆盖模式会自动识别PDF中的文本位置，无需手动指定
3. 合并PDF时，假设两个PDF的页面大小和数量相同
4. 关键词匹配不区分大小写，支持处理标点符号
5. 图片会根据关键词的大小自动调整尺寸，确保完全覆盖

## 技术特点

- **100% 精确**：使用 PDF 渲染引擎底层支持的 search_for() 方法
- **支持复杂字体**：自动识别字体间距和 kerning（字距调整）
- **通用性强**：支持任意尺寸的 PDF（A4、letter 等）
- **完全覆盖**：去除比例锁定，确保图片完全遮盖文字矩形
- **坐标转换**：正确处理不同PDF库之间的坐标系差异
- **用户友好**：提供交互式命令行界面，支持两种模式选择