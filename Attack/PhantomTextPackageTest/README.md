# PhantomTextPackageTest

PhantomTextPackageTest是一个用于测试PhantomText包功能的示例项目，PhantomText是一个用于进行隐形文本注入攻击和检测的Python库。

## 功能介绍

### 隐形文本注入攻击

PhantomText库提供了多种隐形文本注入技术：

1. **零大小注入（ZeroSizeInjection）**：
   - 将文本注入为零大小，使其在视觉上不可见
   - 支持PDF和HTML等文件格式

2. **伪装注入（CamouflageInjection）**：
   - 将文本伪装成与背景相似的颜色或样式
   - 使文本在视觉上难以察觉

3. **透明注入（TransparentInjection）**：
   - 通过设置文本透明度为0，使其完全不可见
   - 支持不同的透明模式

### 恶意内容检测

库还提供了文件扫描功能，用于检测文档中的恶意隐形内容：

- 支持扫描单个文件
- 支持批量扫描目录中的文件
- 检测多种类型的隐形文本注入

## 安装方法

在运行示例代码之前，需要安装PhantomText包：

```bash
pip install phantomtext
```

## 文件说明

### Attack_Example.py

攻击示例脚本，演示如何使用PhantomText库进行隐形文本注入：

- 导入了三种注入技术：ZeroSizeInjection、CamouflageInjection、TransparentInjection
- 演示了零大小注入和透明注入的使用方法
- 支持PDF文件格式的注入

### Detect_example.py

检测示例脚本，演示如何使用PhantomText库检测恶意隐形内容：

- 导入了FileScanner类
- 演示了扫描单个PDF文件的方法
- 输出检测结果，包括是否发现恶意内容和具体的漏洞类型
- 提供了批量扫描目录的示例代码（已注释）

## 使用示例

### 进行隐形文本注入

```python
# 导入所需的注入类
from phantomtext.injection.zerosize_injection import ZeroSizeInjection
from phantomtext.injection.transparent_injection import TransparentInjection

# 创建零大小注入器
injector = ZeroSizeInjection(modality="default", file_format="pdf")

# 创建透明注入器
injector2 = TransparentInjection(modality="default", file_format="pdf")

# 应用零大小注入
injector.apply(
    input_document="DGA_IWQOS2025.pdf",
    injection="Hidden content",
    output_path="injected_document.pdf"
)

# 应用透明注入
injector2.apply(
    input_document="DGA_IWQOS2025.pdf",
    injection="Hidden content",
    output_path="injected_document_Trans.pdf"
)
```

### 检测恶意隐形内容

```python
# 导入文件扫描类
from phantomtext.file_scanning import FileScanner

# 创建扫描器实例
scanner = FileScanner()

# 扫描单个文件
result = scanner.scan_file('injected_document.pdf')

# 输出检测结果
print(f"恶意内容发现: {result['malicious_content_found']}")
print(f"漏洞: {result['vulnerabilities']}")

# 扫描整个目录（示例）
# reports = scanner.scan_dir('./output')
# for report in reports:
#     if report['malicious_content_found']:
#         print(f"⚠️ 在 {report['file_path']} 中发现问题")
#         for vulnerability in report['vulnerabilities']:
#             print(f"  - {vulnerability}")
```

## 支持的文件格式

- PDF
- HTML

## 应用场景

### 安全研究

- 研究文档安全漏洞
- 测试文档处理系统的安全性
- 开发防护机制

### 教育用途

- 学习隐形文本注入技术
- 了解文档安全的重要性
- 培养安全意识

## 注意事项

1. 本工具仅用于教育和研究目的，请勿用于非法活动
2. 请在合法授权的情况下使用本工具
3. 使用前请确保已安装所有依赖
4. 不同的注入技术在不同的查看器中可能有不同的效果

## 技术原理

### 零大小注入

将注入的文本设置为零大小，使其在视觉上不可见，但仍保留在文档的文本流中，可被文本提取工具提取。

### 透明注入

通过设置文本的透明度为0，使其完全不可见，但仍存在于文档中。

### 伪装注入

将文本的颜色、大小或样式设置为与背景相似，使其在视觉上难以区分。

## 检测机制

FileScanner通过分析文档的结构和内容，检测以下特征：

- 零大小的文本元素
- 透明度异常的文本
- 与背景相似的文本
- 其他异常的文本格式和样式

## 参考资料

- PhantomText包文档
- 文档安全相关研究论文