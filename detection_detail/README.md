# Docling Layout + PyMuPDF Text + Docling OCR 检测流程

这个目录里的代码用于扫描 PDF 中“PDF 文本层能解析到，但视觉 OCR 看不到”的文本。它适合检测隐藏 prompt injection，也会把非恶意但不可见的 parser-only 文本报出来。

## 当前核心思路

```text
PDF
  -> Docling 解析视觉 layout，得到 region bbox / label / page_no
  -> PyMuPDF 在每个 Docling bbox 内提取 PDF 文本，得到 pymupdf_text
  -> PyMuPDF 同时导出全页 blocks / words，记录原始文本层坐标
  -> 渲染 PDF 页面，把每个候选 region 裁成图片 patch
  -> Docling RapidOCR 对 patch 做 OCR，得到 ocr_text
  -> 比较 pymupdf_text 和 ocr_text
  -> 如果发现 PyMuPDF 有、OCR 没有的 gap：
       用 PyMuPDF words 重新定位这段 gap 的原始 bbox
       裁一个更紧的小图
       再跑一次 Docling OCR
       如果二次 OCR 能读到，就认为是可见文本，不报 suspicious
       如果二次 OCR 仍然读不到，才输出 pymupdf_only gap
```

简单说：Docling 负责 layout 和 OCR；PyMuPDF 负责 PDF 文本层和文本坐标；二次 OCR 负责降低 layout 切块不一致导致的误报。

## 文件结构

- `scan_pdf.py`：命令行入口，只负责解析参数和启动流程。
- `detector_pipeline.py`：主流程编排。
- `detector_docling.py`：Docling layout 与 Docling/RapidOCR OCR。
- `detector_pymupdf.py`：PyMuPDF 文本、blocks、words、gap bbox 定位。
- `detector_matching.py`：OCR/PyMuPDF 对比、gap 二次验证、风险分类。
- `detector_text.py`：文本归一化、相似度、gap 提取、intent pattern。
- `detector_images.py`：页面渲染、区域裁剪、bbox 可视化。
- `detector_io.py`：JSON/CSV 输出。
- `detector_config.py`：阈值和规则配置。
- `detector_models.py`：数据结构。

## 风险类型

- `trusted`：PyMuPDF 和 OCR 能对上，或者初次 OCR 漏读但二次 tight crop OCR 已验证可见。
- `parser_only`：PyMuPDF 能解析到，但 OCR 和二次 OCR 都看不到；不一定恶意，但需要检查。
- `control_intent`：在 parser-only 或 mismatch 的基础上，还命中类似 `ignore previous instructions` 的控制型文本。
- `visual_mismatch`：PyMuPDF 和 OCR 内容明显不一致。
- `ocr_only`：OCR 看到了文字，但 PyMuPDF 文本层没有。
- `ambiguous`：OCR 失败或复杂区域导致无法可靠判断。

注意：intent 现在不会单独触发 suspicious。只要 PyMuPDF 和 OCR 能对上，即使文本里有类似 “prompt / tool” 的词，也会是 `trusted`。

## 运行

```bash
bash detection_detail/run.sh input.pdf
```

指定输出目录和扫描页数：

```bash
bash detection_detail/run.sh input.pdf ./out 3
```

直接运行 Python：

```bash
python detection_detail/scan_pdf.py --pdf input.pdf --out ./out --device cuda --max-pages 3
```

Batch scan a folder of PDFs:

```bash
bash detection_detail/run_batch.sh ./pdf_folder ./out
```

On Windows PowerShell, avoid WSL/bash and use:

```powershell
.\detection_detail\run_batch.ps1 .\pdf_folder .\out
```

Limit every PDF to the first 3 pages:

```bash
bash detection_detail/run_batch.sh ./pdf_folder ./out 3
```

PowerShell version:

```powershell
.\detection_detail\run_batch.ps1 .\pdf_folder .\out 3
```

Batch-level summary files:

```text
out/batch_summary.csv
out/batch_summary.json
```

## 输出

```text
out/<pdf-name>/
  report.json                    # 总报告
  regional_ocr_results.json      # 全部 region 结果 JSON
  regional_ocr_results.csv       # 全部 region 结果 CSV
  suspicious_regions.csv         # 非 trusted 结果 CSV
  layout_regions.json            # Docling region + PyMuPDF-only outside-layout region
  pymupdf_blocks.json            # PyMuPDF blocks 与 Docling 覆盖关系
  pymupdf_words.json             # PyMuPDF words 与坐标，二次 OCR 定位会用它
  ocr_items.json                 # OCR 原始 item 记录
  matching_debug.json            # gap 初筛、二次 OCR 验证、仍缺失文本记录
  docling_raw.json
  docling.md
  pages/                         # 渲染后的页面图
  patches/                       # region patch 和 gap verify patch
  visualization/                 # bbox 可视化图
```

## 看结果时优先看什么

1. 先看 `suspicious_regions.csv`，这是最终需要人工看的行。
2. 如果某一行是 `*_gap01`，看 `parent_region_id` 找它来自哪个 Docling region。
3. 到 `matching_debug.json` 里查同一个 parent，可以看到：
   - `initial_gaps`：初次 region OCR 漏掉的文本；
   - `verified_visible_gaps`：二次 tight crop OCR 已经读到、因此被压掉的文本；
   - `still_missing_gaps`：二次 OCR 仍读不到、最终报 suspicious 的文本。
4. 如果想看图片，打开 `patch_path` 对应的 png。

## 依赖

```bash
pip install -r detection_detail/requirements.txt
```

CUDA 环境下请先确保 PyTorch CUDA 可用；脚本默认 `--device cuda`。

## 公式区域 compromise

当前版本暂时不做公式 TeX 语义比较。Docling 标为 `formula` 的区域会走 intent-only 分支：

```text
formula region
  -> 保留 PyMuPDF 文本和普通 OCR 文本作为 debug
  -> 不用普通 OCR gap 产生 parser_only
  -> 不因为公式 OCR/Unicode 不一致报 suspicious
  -> 只在公式区域里发现 control-like 指令且 OCR 没有可见验证时，报 control_intent
```

这样可以先压住公式 OCR 的误报。之后如果要检测公式本身是否被篡改，再重新接入 Pix2Text / UniMERNet 等公式识别模型做 LaTeX 或 math-token 级比较。

## ???? compromise

????????? Docling ?? `picture` / `figure` / `image` / `chart` / `diagram` ??????

```text
picture-like region
  -> ?? PyMuPDF ??? OCR ???? debug
  -> ???? parser/OCR gap ????
  -> ???????? OCR/PyMuPDF ???? suspicious
```

?????????????????????? `detector_picture.py` ? `analyze_picture_region()` ???????


## Table mode compromise

The detector now uses Docling `table` bounding boxes as table context. A region is handled by table mode when it is either:

```text
- a Docling region with label=table
- a small text/cell region whose bbox is mostly inside a Docling table bbox
```

Current policy:

```text
table / table-child region
  -> keep PyMuPDF text and OCR text as debug evidence
  -> suppress short cells, numbers, symbols, checkmarks, dashes, arrows, headers, and math fragments
  -> do not run normal parser/OCR gap verification for table cells
  -> still report control_intent if hidden parser text contains prompt-control instructions
```

Additional output:

```text
out/<pdf-name>/table_debug.csv
matching_debug.json -> table_regions
```

The implementation entry point is `detector_table.py`, especially `analyze_table_region()`.


## Visible ink and ASCII math suppression

Two extra false-positive suppressions are now applied after second-pass gap OCR:

```text
suppressed_visible_ink
  -> the tight verification crop has visible dark foreground pixels
  -> the gap has no control-like instruction
  -> treated as an OCR miss, not hidden text

suppressed_inline_math
  -> the gap looks like inline math or paper notation
  -> supports both Unicode math and ASCII formula patterns such as f(2), g(?), argmax, hat-z, T+2P-D(K-1)
  -> no control-like instruction means debug-only
```

These records are still written to `gap_verification_results.csv` and `matching_debug.json`; they are not emitted to `suspicious_regions.csv`.
