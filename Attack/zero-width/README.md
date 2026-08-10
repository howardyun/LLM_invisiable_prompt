# Zero-Width 零宽字符攻击工具

Zero-Width 是一种利用零宽字符的隐形文本注入攻击技术，通过在 PDF 文档中插入不可见的零宽字符，使文本在视觉上保持不变，但破坏 NLP 模型的分词和语义识别。

## 功能介绍

### 攻击功能 (zerowidth_attack.py)

创建包含零宽字符的 PDF 文件，支持以下攻击模式：

1. **Mask1**: 在关键词中间插入一个零宽字符，轻微混淆分词
2. **Mask2**: 在关键词每个字符间插入零宽字符，彻底破坏分词

主要特性：
- 支持两种攻击模式
- 支持自定义关键词列表
- 支持页面内容注入
- 交互式命令行界面


### 攻击模式详解

| 模式 | 攻击方式 | 效果 |
|------|----------|------|
| **Mask1** | 关键词中间插入1个零宽字符 | `"kill"` → `"ki​ll"` |
| **Mask2** | 关键词每个字符间插入零宽字符 | `"kill"` → `"k‌i‌l‌l"` |

## 依赖环境

- Python 3.x
- PyMuPDF (fitz): 用于 PDF 操作

## 安装依赖

```bash
pip install pymupdf
```

## 文件说明

```
zero-width/
├── zerowidth_attack.py    # 零宽字符攻击工具
├── zerowidth_detector.py  # 零宽字符检测工具
└── README.md              # 说明文档
```

## 使用方法

### 攻击工具使用

```bash
python zerowidth_attack.py
```

按照提示操作：

1. **输入 PDF 文件路径**: 指定要攻击的 PDF 文件
2. **输入输出文件路径**: 指定输出路径（留空则默认在同一文件夹下生成 `原始文件名_injected.pdf`）
3. 程序会自动处理 PDF 文件，对指定的关键词注入零宽字符

### 检测工具使用

```bash
python zerowidth_detector.py <PDF文件路径>
```

检测结果会显示是否存在零宽字符注入，以及注入的详细信息。

## 攻击流程

1. **初始化注入器**: 指定目标关键词列表
2. **打开输入 PDF**: 读取原始 PDF 文件
3. **提取单词**: 获取页面上的所有单词及其坐标
4. **注入零宽字符**: 对目标单词执行零宽字符注入
5. **重新写入**: 在相同位置重新写入注入后的文本
6. **保存输出**: 生成包含零宽字符的 PDF 文件

## 攻击效果示例

### Mask1 模式

```
原始文本: "I wanna kill you"
攻击后:   "I wanna ki​ll you"
视觉上:   完全相同
机器识别: "ki​ll" 被识别为未知词
```

### Mask2 模式

```
原始文本: "attack the target"
攻击后:   "a‌t‌t‌a‌c‌k the target"
视觉上:   完全相同
机器识别: "a‌t‌t‌a‌c‌k" 被完全破坏
```

## 使用的零宽字符

| Unicode | 名称 | 用途 |
|---------|------|------|
| U+200B | 零宽空格 (Zero Width Space) | 用于注入 |
| U+200C | 零宽非连接符 (Zero Width Non-Joiner) | 用于注入 |
| U+200D | 零宽连接符 (Zero Width Joiner) | 用于注入 |
| U+FEFF | 零宽不换行空格 (Zero Width No-Break Space) | 用于注入 |

## 检测机制

检测工具会扫描 PDF 文件中的文本，识别以下模式：
- 原始零宽字符（U+200B, U+200C, U+200D, U+FEFF）
- 转换后的零宽字符（0xB7，中间点，可能在 PDF 处理过程中产生）

检测结果会显示注入位置、视觉文本和编码构造，帮助识别零宽字符注入攻击。

## 示例关键词

默认的目标关键词包括：
- Apple
- Machine
- Intelligence
- Security
- Attack

可以根据需要修改代码中的 `my_targets` 列表来自定义关键词。