# Detection_New_YSX

PDF 隐式注入检测原型。当前实现把 PDF 底层绘制对象先抽象为小的 `RegionDescriptor`，再聚合为结构化 `BlockDescriptor`，最后用 parser 输出的 `ParserSpan` 去和 block 做语义级映射。

## 核心流程

```text
PDF texttrace / glyph estimate regions
        -> line aggregation
        -> structure blocks
        -> raw parser spans
        -> aggregated parser blocks
        -> parser span to block mapping
        -> risk finding
```

小 region 负责保留底层证据，例如字体、颜色、透明度、bbox、glyph drift。visual block 负责更稳定地表达“这一段视觉上是什么内容”，例如正文段落、公式、表格、图注、页眉页脚或隐藏/漂移文本。parser 侧也会从原始行级 span 聚合成 parser block，再和 visual block 做对比。

## 已实现能力

- 使用 PyMuPDF `get_texttrace()` 提取文字、bbox、font、font_size、color、opacity、seqno、layer、render type。
- 在渲染前估计视觉文字：对可疑字体解析 content stream 的 `Tf/Tj/TJ` 和 TrueType `cmap/loca/glyf`，用 glyph 轮廓匹配估计真正画出来的字符。
- 聚合结构 block：`paragraph`、`formula`、`table`、`caption`、`header_footer`、`heading`、`hidden_or_overlay_text`、`glyph_drift_text`。
- parser span 会先聚合成 parser block，然后优先映射到 visual block，而不是只映射到单个小 region，从而包容公式、表格、换行、ligature、局部符号等字符级差异。
- parser 聚合是视觉 block 引导的窗口匹配，同时会把包含 LLM-control intent 的 span 作为边界保留，避免隐藏指令被正常段落吞掉。
- PDF migrate 检测：保留 `glyph_shape_line` 证据，比较 rendered text 与 parser text 的语义漂移。
- 降误报策略：公式/表格/页眉脚/图注 block 的普通 parser mismatch 默认只进入 debug；只有命中 LLM-control intent 或强可见性异常时才进入 report。

## 使用

调试时可以直接打开 `detect.py`，修改顶部的 `FILE_CONFIG`：

```python
RUN_WITH_FILE_CONFIG = True

FILE_CONFIG = {
    "pdf": BASE_DIR.parent / "Detection" / "testData" / "Arixv" / "2212.08983v2.pdf",
    "target_parser": "pypdf",
    "out": BASE_DIR / "report.json",
    "html": BASE_DIR / "report.html",
    "debug_dir": BASE_DIR / "debug",
    "enable_block_mapping": True,
    "enable_parser_aggregation": True,
}
```

然后运行：

```bash
cd Detection_New_YSX
..\venv\Scripts\python.exe detect.py
```

命令行仍然可用：

```bash
..\venv\Scripts\python.exe detect.py ^
  --pdf ..\Detection\testData\org\pdf_migrate.pdf ^
  --target-parser pypdf ^
  --out report.json ^
  --html report.html ^
  --debug-dir debug
```

可用 `--disable-block-mapping` 回退到旧的 region 级映射。
可用 `--disable-parser-aggregation` 关闭 parser 聚合。

## 批量扫描

大范围测试时可以在 `detect.py` 顶部配置文件夹模式：

```python
FILE_CONFIG = {
    "pdf_dir": BASE_DIR.parent / "Detection" / "testData" / "Arixv",
    "batch_recursive": False,
    "target_parser": "pypdf",
    "out": BASE_DIR / "batch_report.json",
    "html": None,
    "debug_dir": None,
    "include_debug": False,
}
```

或者命令行运行：

```bash
cd Detection_New_YSX
..\venv\Scripts\python.exe detect.py ^
  --pdf-dir ..\Detection\testData\Arixv ^
  --out batch_report.json
```

递归扫描子目录：

```bash
..\venv\Scripts\python.exe detect.py ^
  --pdf-dir ..\Detection\testData ^
  --batch-recursive ^
  --out batch_report.json
```

批量模式不会写 debug/html，也不会把正常 PDF 写入 `problematic_pdfs`。输出 JSON 只记录：

- `summary.scanned`: 扫描 PDF 数量。
- `summary.problematic`: 有 finding 的 PDF 数量。
- `problematic_pdfs`: 只包含有问题的 PDF、summary、finding_summary 和 findings。
- `errors`: 解析失败或异常的 PDF，单独记录，不和正常结果混在一起。

## Debug 输出

打开 `debug_dir` 后会写出：

- `regions.json`: 小 region 层，适合看底层字体、bbox、可见性、glyph 估计。
- `structure_blocks.json`: 新增的中间层，记录每个 block 的 role、bbox、子 region、features 和聚合文本。
- `raw_parser_spans.json`: pypdf/pymupdf 原始 parser 行或片段。
- `parser_spans.json`: 用于判断的聚合 parser block/span，字段 `raw_span_ids` 可追溯到原始 parser 行。
- `mapping_results.json`: 聚合 parser span 到 visual region/block 的映射结果。
- `font_encoding_issues.json`: 字体编码/迁移类证据。
- `rendered_text_preview.html`: 把 `rendered_text_estimate` 按 bbox 摆回页面坐标。
- `structure_blocks.html`: 把 block 框画回页面坐标，适合检查段落、公式、表格是否聚合正确。
- `parser_block_alignment.html`: 并排展示 parser span、匹配到的视觉 block、假渲染文本、分数和原因。

## 关键字段

`structure_blocks.json` 里重点看：

- `block_role`: 结构类别。
- `block_role_confidence`: 结构分类置信度。
- `region_ids`: 这个 block 聚合了哪些小 region。
- `text` / `rendered_text_estimate`: block 视觉语义文本。
- `parser_text`: block 子 region 对应的 parser/字符码侧文本。
- `features`: 结构特征，例如 `math_symbol_ratio`、`inline_math_ratio`、`multi_cluster_line_ratio`、`parser_render_similarity`。

注意：正文段落中少量公式字符不会直接让整段变成 `formula`，而是保留为 `paragraph`，并在 `features.inline_math_ratio` 里记录。

## 测试

```bash
cd Detection_New_YSX
..\venv\Scripts\python.exe -m unittest discover -s tests
```
