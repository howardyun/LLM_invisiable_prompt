# PDF-Mirage: 内容掩码攻击工具

## 项目介绍

PDF-Mirage是一个实现"内容掩码攻击"（Content Masking Attack）的工具，该项目发表于USENIX 2017会议，论文标题为"PDF Mirage: Content Masking Attack Against Information-Based Online Services"。

该工具能够生成一种特殊的PDF文件，具有以下特性：
- **视觉显示**：呈现给用户的是一种内容（show text）
- **文本提取**：当通过PDF解析工具提取文本时，得到的是另一种内容（under text）

## 攻击原理

PDF-Mirage利用PDF文件中字体和字符映射的特性，实现内容的视觉显示与文本提取的分离：

1. **自定义字体**：为每个字符创建特殊的字体文件
2. **字符映射**：将显示字符与隐藏字符通过自定义字体关联
3. **LaTeX编译**：使用生成的LaTeX代码编译成最终的PDF文件

视觉上，用户看到的是正常的文本内容；但当PDF解析工具提取文本时，由于字体映射的特殊性，会提取到隐藏的内容。

## 文件结构

```
PDF-Mirage/
├── src/
│   ├── fonts/          # 自定义字体文件目录
│   │   ├── a.ttf       # 字母a的字体文件
│   │   ├── b.ttf       # 字母b的字体文件
│   │   └── ...         # 其他字符的字体文件
│   └── doc.tex         # LaTeX模板文件
├── output/             # 输出文件目录（运行后生成）
├── example/            # 示例文件
├── content_swtich.py   # 主程序文件
└── README.md           # 说明文档
```

## 依赖环境

- Python 3.x
- LaTeX 环境（如TeX Live、MiKTeX等）
- ttf2tfm 工具（用于转换TTF字体到TFM格式）

## 使用方法

### 1. 准备输入文件

创建两个文本文件：
- `under.txt`: 包含要隐藏的内容（提取文本时会得到此内容）
- `show.txt`: 包含要显示的内容（视觉上看到的内容）

### 2. 运行程序

```bash
python content_swtich.py under.txt show.txt
```

### 3. 获取输出

程序运行后，会在`output`目录下生成：
- `doc.tex`: 生成的LaTeX文档
- `doc.pdf`: 最终的PDF文件（包含内容掩码攻击）
- 各种字体文件和相关的LaTeX辅助文件

## 功能实现细节

### 程序流程

1. **读取输入文件**：将隐藏内容和显示内容分别读入列表
2. **文本配对**：将隐藏内容和显示内容的单词进行配对
3. **生成LaTeX代码**：为每个字符生成特殊的LaTeX代码
4. **复制字体文件**：将需要的字体文件复制到输出目录
5. **生成字体描述文件**：为每个使用的字体生成.fd文件
6. **转换字体格式**：使用ttf2tfm将TTF字体转换为TFM格式
7. **编译PDF**：使用pdflatex编译生成最终的PDF文件

### 关键技术

#### 自定义字体映射

程序为每个字符创建了自定义字体，这些字体在视觉上显示为一种字符，但在文本提取时返回另一种字符。

#### 特殊字符处理

程序包含了标点符号的映射表，确保所有字符都能正确处理：

```python
punctuation = {
    "!": "Exclam",
    "\"": "Quotedbl",
    "#": "Numbersign",
    # ... 其他标点符号
}
```

#### 文本对齐策略

当隐藏内容和显示内容长度不一致时，程序会自动处理：
- 如果显示内容较短，会用下划线填充隐藏内容的剩余部分
- 如果隐藏内容较短，会用空字符填充显示内容的剩余部分

## 应用场景

### 安全研究

该工具可用于研究PDF文件的安全性，特别是内容提取和视觉显示之间的一致性问题。

### 信息隐藏

可用于创建包含隐藏信息的PDF文件，只有通过特定的文本提取工具才能获取隐藏内容。

### 安全测试

可用于测试各种PDF处理工具和服务对内容掩码攻击的防御能力。

## 注意事项

1. 确保已正确安装LaTeX环境和ttf2tfm工具
2. 程序生成的PDF文件可能被现代PDF查看器或安全工具检测为异常
3. 该工具仅用于研究和教育目的，请勿用于非法活动

## 示例

程序包含了一个示例目录`example/`，其中包含了示例输入文件和输出结果：

```bash
# 运行示例
python content_swtich.py example/under example/show
```

## 引用

如果您使用了这个工具，请引用以下论文：

```
@inproceedings{pdfmirage, 
    title = {{PDF} Mirage: Content Masking Attack Against Information-Based Online Services}, 
    author = {作者姓名}, 
    booktitle = {USENIX Security Symposium}, 
    year = {2017} 
}
```

## 参考资料

[1] B. Li and Y. T. Hou, "The New Automated IEEE INFOCOM Review Assignment System," IEEE Network, vol. 30, no. 5, pp. 18–24, 2016