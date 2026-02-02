# PDF攻击工具自动运行系统

## 项目简介

auto_attack.py是一个PDF攻击方法的统一调用平台，集成了多种PDF文档攻击技术，提供了友好的交互式界面和命令行接口，方便用户快速测试和使用各种PDF攻击方法。

## 支持的攻击方法

目前系统支持以下8种PDF攻击方法：

| 编号 | 攻击方法 | 描述 |
|------|---------|------|
| 1 | Double_Layer_PDF | 双层PDF攻击，将图片层与文字层合并，实现隐藏文本 |
| 2 | OCG | Optional Content Groups攻击，利用可选内容组隐藏文本 |
| 3 | Out-of-Bound | 越界文本攻击，将文本放置在页面可见区域外 |
| 4 | Misaligned | 文本错位攻击，通过文本定位技巧隐藏内容 |
| 5 | TRM | Text Rendering Mode攻击，利用渲染模式隐藏文本 |
| 6 | Zero-Size-Font | 零大小字体攻击，使用极小字体隐藏文本 |
| 7 | Zero-Width | 零宽度字符攻击，使用不可见字符隐藏信息 |
| 8 | PDF-Mirage | 内容掩码攻击，视觉显示与文本提取内容不一致 |

## 安装和依赖

### 基本依赖
- Python 3.x

### 特定攻击方法依赖
- **Zero-Size-Font**: PyMuPDF库 (fitz) - 可通过 `pip install PyMuPDF` 安装
- **PDF-Mirage**: LaTeX环境 (TeX Live/MiKTeX) 和 ttf2tfm工具

## 使用方法

### 1. 交互式方式

直接运行脚本，按照菜单提示选择攻击方法：

```bash
python auto_attack.py
```

系统将显示攻击方法菜单：

```
==================================================
PDF攻击工具自动运行系统
==================================================
1. Double_Layer_PDF
2. OCG
3. Out-of-Bound
4. Misaligned
5. TRM
6. Zero-Size-Font
7. Zero-Width
8. PDF-Mirage（请在linux下执行）
0. 退出
==================================================
请选择攻击方法编号: 
```

输入对应的编号，然后按照提示输入必要的参数（如文件路径等）。

### 2. 命令行方式

可以直接在命令行指定攻击方法编号和参数：

```bash
python auto_attack.py -m <方法编号> -i <输入文件> -o <输出文件>
```

#### 参数说明：
- `-m` 或 `--method`: 攻击方法编号（1-8）
- `-i` 或 `--input`: 输入PDF文件路径（或其他输入文件，取决于攻击方法）
- `-o` 或 `--output`: 输出文件路径（仅部分攻击方法使用）

#### 示例：

```bash
# 使用OCG攻击方法，输入input.pdf，输出ocg_output.pdf
python auto_attack.py -m 2 -i input.pdf -o ocg_output.pdf

# 使用PDF-Mirage攻击方法，输入under.txt和show.txt
python auto_attack.py -m 8 -i under.txt -o show.txt
```

## 各攻击方法详细说明

### 1. Double_Layer_PDF攻击
- **输入**：文字层PDF文件、图片文件
- **输出**：合并后的双层PDF文件
- **效果**：视觉上显示图片内容，文本提取时得到文字层内容

### 2. OCG攻击
- **输入**：原始PDF文件
- **输出**：包含隐藏文本的OCG PDF文件
- **效果**：通过PDF阅读器的图层控制可以显示/隐藏不同内容

### 3. Out-of-Bound攻击
- **输入**：原始PDF文件
- **输出**：oob_poc_base.pdf（基础文件）和oob_poc_cropped.pdf（裁剪后的PoC文件）
- **效果**：裁剪后的PDF只显示正常文本，隐藏越界放置的文本

### 4. Misaligned攻击
- **输入**：原始PDF文件（通过交互式输入）
- **输出**：包含错位文本的PDF文件
- **效果**：利用文本定位技巧隐藏内容

### 5. TRM攻击
- **输入**：原始PDF文件
- **输出**：包含隐藏文本的PDF文件
- **选项**：提供3种不同的TRM攻击类型
  - Tr=3 + tiny text matrix
  - Tr=3 + TJ fragmented with extreme offsets
  - Tr=3 inside /Artifact marked content

### 6. Zero-Size-Font攻击
- **输入**：原始PDF文件、攻击文本
- **输出**：包含零大小字体文本的PDF文件
- **选项**：提供3种攻击类型（size0、size0.01、size1）
- **效果**：视觉上不可见的文本，但可以被文本提取工具获取

### 7. Zero-Width攻击
- **输入**：原始PDF文件（通过交互式输入）
- **输出**：包含零宽度字符的PDF文件
- **效果**：使用不可见字符隐藏信息

### 8. PDF-Mirage攻击
- **输入**：两个文本文件
  - under.txt: 隐藏内容（文本提取时得到）
  - show.txt: 显示内容（视觉上看到）
- **输出**：output/doc.pdf（包含内容掩码的PDF文件）
- **效果**：视觉显示与文本提取内容不一致

## 注意事项

1. **依赖检查**：部分攻击方法需要特定依赖，程序会自动检查并提示安装
2. **文件路径**：输入文件路径可以是相对路径或绝对路径
3. **输出位置**：不同攻击方法的输出位置可能不同，程序会显示具体输出路径
4. **安全性**：本工具仅用于研究和教育目的，请勿用于非法活动
5. **兼容性**：不同PDF阅读器对攻击的检测和显示效果可能不同