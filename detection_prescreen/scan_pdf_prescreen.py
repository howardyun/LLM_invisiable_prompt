#!/usr/bin/env python3
"""Single-PDF fast pre-screen, with optional candidate-only OCR verification."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ocr_verify import verify_candidates_with_ocr
from prescreen_core import PrescreenConfig, scan_pdf_prescreen, write_prescreen_outputs


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fast PDF prompt-injection pre-screen before OCR.")
    parser.add_argument("--pdf", required=True, help="Input PDF path.")
    parser.add_argument("--out", default="./prescreen_out", help="Output root directory.")
    parser.add_argument("--max-pages", type=int, default=None, help="Only scan the first N pages.")
    parser.add_argument("--candidate-threshold", type=float, default=0.55)
    parser.add_argument("--ocr-threshold", type=float, default=0.65)
    parser.add_argument("--ocr", choices=["never", "on-hit", "always"], default="on-hit")
    parser.add_argument("--device", choices=["cuda", "auto", "cpu"], default="cuda")
    parser.add_argument("--dpi", type=int, default=180)
    parser.add_argument("--padding", type=float, default=3.0)
    parser.add_argument("--ocr-cls-batch-size", type=int, default=32)
    parser.add_argument("--ocr-rec-batch-size", type=int, default=64)
    parser.add_argument("--max-ocr-candidates", type=int, default=50)
    return parser


def run(args: argparse.Namespace) -> Path:
    pdf_path = Path(args.pdf).expanduser().resolve()
    run_dir = Path(args.out).expanduser().resolve() / pdf_path.stem
    config = PrescreenConfig(
        max_pages=args.max_pages,
        candidate_threshold=args.candidate_threshold,
        ocr_threshold=args.ocr_threshold,
    )

    print(f"[1/3] Pre-screening PDF without OCR: {pdf_path.name}")
    report = scan_pdf_prescreen(pdf_path, config)
    write_prescreen_outputs(run_dir, report)
    print(
        "      Candidates: "
        f"{report['candidate_count']} total, {report['ocr_candidate_count']} need OCR, "
        f"risk={report['risk_level']} score={report['risk_score']}"
    )

    should_ocr = args.ocr == "always" or (args.ocr == "on-hit" and report["should_run_ocr"])
    if should_ocr:
        print("[2/3] OCR-verifying selected candidates only")
        ocr_report, _recognizer = verify_candidates_with_ocr(
            pdf_path=pdf_path,
            candidates=report["candidates"],
            out_dir=run_dir,
            recognizer=None,
            device=args.device,
            dpi=args.dpi,
            padding=args.padding,
            cls_batch_size=args.ocr_cls_batch_size,
            rec_batch_size=args.ocr_rec_batch_size,
            max_candidates=args.max_ocr_candidates,
        )
        print(
            "      OCR candidates: "
            f"{ocr_report['candidate_count']}; verified_hidden={ocr_report['verified_hidden_count']}"
        )
    else:
        print("[2/3] OCR skipped")

    print(f"[3/3] Done: {run_dir / 'prescreen_report.json'}")
    return run_dir / "prescreen_report.json"


def main() -> int:
    args = build_argument_parser().parse_args()
    try:
        run(args)
        return 0
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
