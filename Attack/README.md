# LLM Invisible Benchmark - Attack Techniques

This repository contains various attack techniques for PDF prompt injection, designed to test and benchmark LLM's ability to detect invisible or hidden content in PDF files.

## Attack Techniques Covered

| # | Technique | Category | Description |
|---|-----------|----------|-------------|
| 1 | **Double Layer PDF** | Visual Hiding | Overlays text with another layer to hide content, making it invisible to human eyes but extractable by text parsers |
| 2 | **OCG (Optional Content Group)** | Geometric Escape | Uses PDF's Optional Content Group feature to create hidden layers that are not rendered by default |
| 3 | **Out-of-Bound** | Geometric Escape | Places text at coordinates outside the visible page area, making it invisible but still present in the PDF |
| 4 | **TRM (Text Rendering Mode)** | Visual Hiding | Uses PDF's text rendering mode to create invisible text by setting rendering mode to invisible |
| 5 | **Zero Size Font** | Visual Hiding | Uses extremely small font sizes (e.g., 0pt or 0.01pt) to make text invisible |
| 6 | **Zero Width** | Presentation Layer Encoding | Uses zero-width Unicode characters to hide content within normal text |
| 7 | **Misaligned** | Parsing Order/Multi-view Inconsistency | Injects malicious instructions and changes the parsing order by drawing the first word of each line last, maintaining visual appearance while altering text extraction order |
| 8 | **White Text** | Visual Hiding | Uses white text on white background to make content invisible to human eyes but extractable by text parsers |

## Attack Categories

### 1. Visual Hiding
Techniques that make text invisible through visual manipulation:
- Double Layer PDF
- TRM (Text Rendering Mode)
- Zero Size Font
- White Text

### 2. Geometric Escape
Techniques that hide text by manipulating its spatial position:
- OCG (Optional Content Group)
- Out-of-Bound

### 3. Presentation Layer Encoding
Techniques that use text encoding to hide content:
- Zero Width

### 4. Parsing Order/Multi-view Inconsistency
Techniques that exploit differences in parsing behavior:
- Misaligned

## Auto Attack Tool

The `auto_attack.py` script provides an automated way to apply all attack techniques to PDF files. It supports:

- Batch processing of multiple PDF files
- Random selection of attack pages
- CSV logging of attack details
- Automatic generation of malicious prompts

### Usage

```bash
python auto_attack.py <input_directory> <output_directory> [--methods <attack_methods>] [--csv <csv_file>]
```

### Example

```bash
python auto_attack.py test output --methods white_text ocg zero_width
```

## Dependencies

- PyPDF2
- PyMuPDF (fitz)
- reportlab
- argparse
- os
- random
- Pathlib

## Disclaimer

This repository is for educational and research purposes only. The attack techniques demonstrated here should not be used for malicious purposes. Always obtain proper authorization before testing these techniques on any system.
