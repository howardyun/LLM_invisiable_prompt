from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from .schema import PDFObject


@dataclass(frozen=True, slots=True)
class LoaderProfile:
    name: str
    consume_text: bool
    consume_metadata: bool
    consume_annotations: str
    consume_forms: str
    consume_ocg_hidden: str
    consume_images: str
    consume_embedded_files: str


PROFILES: Dict[str, LoaderProfile] = {
    "generic_t1": LoaderProfile("generic_t1", True, True, "no", "no", "yes", "no", "no"),
    "langchain_pypdf": LoaderProfile("langchain_pypdf", True, True, "no", "no", "yes", "no", "no"),
    "langchain_pymupdf": LoaderProfile("langchain_pymupdf", True, True, "no", "no", "uncertain", "no", "no"),
    "pdfminer": LoaderProfile("pdfminer", True, True, "no", "no", "yes", "no", "no"),
    "unstructured_fast": LoaderProfile(
        "unstructured_fast", True, True, "uncertain", "uncertain", "uncertain", "no", "uncertain"
    ),
    "unstructured_hires": LoaderProfile(
        "unstructured_hires", True, True, "freetext_only", "uncertain", "uncertain", "ocr", "uncertain"
    ),
}


def get_loader_profile(name: str) -> LoaderProfile:
    key = name.strip()
    if key not in PROFILES:
        available = ", ".join(sorted(PROFILES))
        raise ValueError(f"Unknown loader profile '{name}'. Available profiles: {available}")
    return PROFILES[key]


def map_consumption(obj: PDFObject, profile: LoaderProfile) -> str:
    if obj.object_type in {"text_span", "parser_text"}:
        return "yes" if profile.consume_text else "no"
    if obj.object_type == "metadata":
        return "yes" if profile.consume_metadata else "no"
    if obj.object_type == "annotation":
        return _map_annotation(profile.consume_annotations, obj)
    if obj.object_type == "form":
        return _map_form(profile.consume_forms, obj)
    if obj.object_type in {"ocg", "ocg_text"}:
        return profile.consume_ocg_hidden
    if obj.object_type == "embedded_file":
        return profile.consume_embedded_files
    if obj.object_type in {"signature", "font"}:
        return "uncertain"
    return "uncertain"


def _map_annotation(mode: str, obj: PDFObject) -> str:
    subtype = str(obj.attrs.get("subtype", "")).strip("/").lower()
    if mode == "yes":
        return "yes"
    if mode == "no":
        return "no"
    if mode == "freetext_only":
        return "yes" if subtype in {"freetext", "text"} else "uncertain"
    return "uncertain"


def _map_form(mode: str, obj: PDFObject) -> str:
    if mode == "yes":
        return "yes"
    if mode == "no":
        return "no"
    if mode == "values_only":
        return "yes" if obj.attrs.get("field_key") in {"/V", "/DV"} else "no"
    return "uncertain"
