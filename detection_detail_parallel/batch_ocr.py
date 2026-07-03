"""Single-model RapidOCR batch inference for regional patch OCR."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class PatchOCRResult:
    """OCR output for one region patch."""

    index: int
    patch_path: str
    ocr_text: str
    ocr_error: str | None
    ocr_records: list[dict[str, Any]]
    device_summary: str
    elapsed_seconds: float
    line_count: int


class RapidOCRBatchRegionalOCR:
    """Run RapidOCR with one model instance and batched line recognition.

    RapidOCR's public API accepts one image at a time, but its classifier and
    recognizer already accept a list of cropped text-line images.  This wrapper
    keeps detection per patch, batches all detected line crops, and then
    restores the original patch order.
    """

    def __init__(
        self,
        device: str,
        cls_batch_size: int = 32,
        rec_batch_size: int = 64,
        text_score: float = 0.5,
    ) -> None:
        import torch
        from rapidocr import EngineType, LangCls, LangDet, LangRec, RapidOCR

        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested, but torch.cuda.is_available() is False.")

        use_cuda = device == "cuda"
        params = {
            "Det.engine_type": EngineType.TORCH,
            "Cls.engine_type": EngineType.TORCH,
            "Rec.engine_type": EngineType.TORCH,
            "Det.lang_type": LangDet.CH,
            "Cls.lang_type": LangCls.CH,
            "Rec.lang_type": LangRec.CH,
            "EngineConfig.torch.use_cuda": use_cuda,
            "EngineConfig.torch.cuda_ep_cfg.device_id": 0,
            "Cls.cls_batch_num": max(1, int(cls_batch_size)),
            "Rec.rec_batch_num": max(1, int(rec_batch_size)),
            "Global.text_score": float(text_score),
            "Global.return_word_box": False,
            "Global.log_level": "warning",
        }
        self.ocr = RapidOCR(params=params)
        self.device = device
        self.cls_batch_size = max(1, int(cls_batch_size))
        self.rec_batch_size = max(1, int(rec_batch_size))
        self.device_summary = (
            f"cuda:{torch.cuda.get_device_name(0)}; rapidocr_batch"
            if use_cuda
            else "cpu; rapidocr_batch"
        )

    def recognize_many(self, patch_paths: list[Path]) -> tuple[list[PatchOCRResult], dict[str, Any]]:
        """OCR many patch images while batching classifier/recognizer work."""

        from rapidocr.main import TextClsOutput, TextDetOutput, TextRecOutput

        total_started = time.time()
        patch_states: list[dict[str, Any]] = []
        all_crops: list[np.ndarray] = []
        crop_owner: list[tuple[int, int]] = []
        detect_seconds = 0.0

        for index, patch_path in enumerate(patch_paths, start=1):
            started = time.time()
            state: dict[str, Any] = {
                "index": index,
                "patch_path": patch_path,
                "started": started,
                "ori_img": None,
                "op_record": None,
                "det_res": None,
                "crops": [],
                "error": None,
            }
            try:
                ori_img = self.ocr.load_img(patch_path)
                img, op_record = self.ocr.preprocess_img(ori_img)
                det_started = time.time()
                try:
                    crops, det_res = self.ocr.detect_and_crop(img, op_record)
                except Exception as exc:
                    crops, det_res = [], TextDetOutput()
                    state["detect_note"] = f"{type(exc).__name__}: {exc}"
                detect_seconds += time.time() - det_started
                state.update(
                    {
                        "ori_img": ori_img,
                        "op_record": op_record,
                        "det_res": det_res,
                        "crops": crops,
                    }
                )
                for local_index, crop in enumerate(crops):
                    crop_owner.append((len(patch_states), local_index))
                    all_crops.append(crop)
            except Exception as exc:
                state["error"] = f"{type(exc).__name__}: {exc}"
            patch_states.append(state)

        cls_seconds = 0.0
        rec_seconds = 0.0
        cls_img_list: list[np.ndarray] = []
        cls_res_list: list[tuple[str, float]] = []
        rec_txts: tuple[str, ...] = ()
        rec_scores: list[float] = []
        rec_imgs: list[np.ndarray] = []
        rec_word_results: tuple[Any, ...] = ()

        if all_crops:
            cls_started = time.time()
            cls_out = self.ocr.text_cls(all_crops)
            cls_seconds = time.time() - cls_started
            cls_img_list = cls_out.img_list or []
            cls_res_list = cls_out.cls_res or []

            rec_started = time.time()
            rec_input = self._make_rec_input(cls_img_list)
            rec_out = self.ocr.text_rec(rec_input)
            rec_seconds = time.time() - rec_started
            rec_txts = tuple(rec_out.txts or ())
            rec_scores = list(rec_out.scores or [])
            rec_imgs = list(rec_out.imgs or cls_img_list)
            rec_word_results = tuple(rec_out.word_results or ())

        per_patch_line_ids: list[list[int]] = [[] for _ in patch_states]
        for global_index, (patch_state_index, _local_index) in enumerate(crop_owner):
            per_patch_line_ids[patch_state_index].append(global_index)

        results: list[PatchOCRResult] = []
        for state_index, state in enumerate(patch_states):
            line_ids = per_patch_line_ids[state_index]
            if state["error"]:
                results.append(self._empty_result(state, state["error"], time.time()))
                continue
            if not line_ids:
                results.append(self._empty_result(state, None, time.time()))
                continue

            det_res = state["det_res"]
            rec_out = TextRecOutput(
                imgs=[rec_imgs[i] for i in line_ids if i < len(rec_imgs)],
                txts=tuple(rec_txts[i] for i in line_ids if i < len(rec_txts)),
                scores=[rec_scores[i] for i in line_ids if i < len(rec_scores)],
                word_results=tuple(
                    rec_word_results[i] for i in line_ids if i < len(rec_word_results)
                ),
                elapse=None,
            )
            cls_out = TextClsOutput(
                img_list=[cls_img_list[i] for i in line_ids if i < len(cls_img_list)],
                cls_res=[cls_res_list[i] for i in line_ids if i < len(cls_res_list)],
                elapse=None,
            )
            det_out = TextDetOutput(
                img=getattr(det_res, "img", None),
                boxes=np.array(det_res.boxes, copy=True) if det_res.boxes is not None else None,
                scores=list(det_res.scores or []),
                elapse=getattr(det_res, "elapse", 0.0) or 0.0,
            )
            patch_crops = [state["crops"][i] for i in range(len(line_ids))]
            ocr_output = self.ocr.build_final_output(
                state["ori_img"],
                det_out,
                cls_out,
                rec_out,
                patch_crops,
                state["op_record"],
            )
            ocr_text, records = _rapid_output_to_records(ocr_output)
            results.append(
                PatchOCRResult(
                    index=state["index"],
                    patch_path=state["patch_path"].as_posix(),
                    ocr_text=ocr_text,
                    ocr_error=None,
                    ocr_records=records,
                    device_summary=self.device_summary,
                    elapsed_seconds=round(time.time() - state["started"], 4),
                    line_count=len(records),
                )
            )

        stats = {
            "batch_detect_seconds": round(detect_seconds, 3),
            "batch_cls_seconds": round(cls_seconds, 3),
            "batch_rec_seconds": round(rec_seconds, 3),
            "batch_total_seconds": round(time.time() - total_started, 3),
            "batch_line_count": len(all_crops),
            "ocr_mode": "batch",
            "ocr_cls_batch_size": self.cls_batch_size,
            "ocr_rec_batch_size": self.rec_batch_size,
        }
        return results, stats

    def _make_rec_input(self, cls_img_list: list[np.ndarray]):
        from rapidocr.main import TextRecInput

        return TextRecInput(img=cls_img_list, return_word_box=False)

    def _empty_result(
        self,
        state: dict[str, Any],
        error: str | None,
        finished: float,
    ) -> PatchOCRResult:
        return PatchOCRResult(
            index=state["index"],
            patch_path=state["patch_path"].as_posix(),
            ocr_text="",
            ocr_error=error,
            ocr_records=[],
            device_summary=self.device_summary,
            elapsed_seconds=round(finished - state["started"], 4),
            line_count=0,
        )


def _rapid_output_to_records(ocr_output: Any) -> tuple[str, list[dict[str, Any]]]:
    """Convert RapidOCR output into the local debug-record shape."""

    txts = tuple(getattr(ocr_output, "txts", None) or ())
    scores = tuple(getattr(ocr_output, "scores", None) or ())
    boxes = getattr(ocr_output, "boxes", None)
    records: list[dict[str, Any]] = []

    for item_index, text in enumerate(txts):
        value = str(text or "").strip()
        if not value:
            continue
        box = boxes[item_index] if boxes is not None and item_index < len(boxes) else None
        points = _box_to_points(box)
        left = min((point[0] for point in points), default=0.0)
        y_mid = (
            sum(point[1] for point in points) / len(points)
            if points
            else float(item_index)
        )
        records.append(
            {
                "item_index": item_index,
                "self_ref": None,
                "parent_ref": None,
                "label": "text",
                "text": value,
                "score": round(float(scores[item_index]), 6) if item_index < len(scores) else None,
                "bbox": {"points": points} if points else {},
                "coord_origin": "TOPLEFT",
                "page_no_in_patch": 1,
                "sort_key": [1, int(round(y_mid / 20.0)), left, item_index],
            }
        )

    return "\n".join(item["text"] for item in records).strip(), records


def _box_to_points(box: Any) -> list[list[float]]:
    if box is None:
        return []
    try:
        values = box.tolist() if hasattr(box, "tolist") else box
    except Exception:
        return []
    points: list[list[float]] = []
    for point in values:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        points.append([round(float(point[0]), 3), round(float(point[1]), 3)])
    return points
