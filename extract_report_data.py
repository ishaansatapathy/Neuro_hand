"""
Extract text from report images (and optional PDFs) under report/

Usage:  py -3 extract_report_data.py
        py -3 extract_report_data.py --en-only   # faster (English OCR only)

Outputs (under data/processed/reports/):
  manifest.jsonl   — one JSON object per file: path, text, ocr_engine, num_boxes
  summary.json     — counts, total chars

Requires: pip install easyocr
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPORT_DIR = BASE / "report"
OUT_DIR = BASE / "data" / "processed" / "reports"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}

# EasyOCR can hang on large/noisy photos on CPU — cap wait per image (seconds).
OCR_TIMEOUT_SEC = 240


def _run_readtext(reader: object, path_str: str):
    return reader.readtext(
        path_str,
        paragraph=False,
        width_ths=0.9,
        height_ths=0.9,
    )


def readtext_with_timeout(reader, fp: Path, timeout_sec: int = OCR_TIMEOUT_SEC):
    """Run EasyOCR in a worker thread so we can timeout (avoids infinite hangs)."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(_run_readtext, reader, str(fp))
        try:
            return fut.result(timeout=timeout_sec)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(f"OCR exceeded {timeout_sec}s for {fp.name}") from None


def _extract_pdf_text(pdf_path: Path) -> str:
    try:
        import fitz  # pymupdf

        doc = fitz.open(pdf_path)
        parts: list[str] = []
        for page in doc:
            parts.append(page.get_text())
        doc.close()
        return "\n".join(parts).strip()
    except Exception:
        pass
    try:
        from pypdf import PdfReader

        r = PdfReader(str(pdf_path))
        return "\n".join((p.extract_text() or "") for p in r.pages).strip()
    except Exception as e:
        return f"[pdf_extract_failed: {e}]"


def main() -> None:
    ap = argparse.ArgumentParser(description="OCR for files in report/")
    ap.add_argument(
        "--en-only",
        action="store_true",
        help="English-only OCR (faster than en+hi).",
    )
    args = ap.parse_args()

    langs = ["en"] if args.en_only else ["en", "hi"]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT_DIR / "manifest.jsonl"

    if not REPORT_DIR.is_dir():
        print(f"[ERROR] Missing folder: {REPORT_DIR}", flush=True)
        sys.exit(1)

    files: list[Path] = []
    for p in REPORT_DIR.rglob("*"):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext in IMAGE_EXTS or ext == ".pdf":
            if p.name.startswith("."):
                continue
            files.append(p)

    if not files:
        print(f"[WARN] No images/PDFs under {REPORT_DIR}", flush=True)
        sys.exit(0)

    print(
        f"Found {len(files)} file(s). OCR langs={langs} (first run may download models)…",
        flush=True,
    )

    try:
        import easyocr

        reader = easyocr.Reader(langs, gpu=False, verbose=False)
    except ImportError:
        print("[ERROR] easyocr not installed. Run:  pip install easyocr", flush=True)
        sys.exit(1)

    n_written = 0
    with manifest_path.open("w", encoding="utf-8") as out:
        for fp in sorted(files, key=lambda x: str(x).lower()):
            rel = str(fp.relative_to(BASE))
            ext = fp.suffix.lower()
            record: dict = {"path": rel, "file": fp.name, "ext": ext}

            if ext == ".pdf":
                text = _extract_pdf_text(fp)
                record["text"] = text
                record["ocr_engine"] = "pdf_text"
                record["num_boxes"] = 0
            else:
                try:
                    raw = readtext_with_timeout(reader, fp)
                    pieces = [t[1] for t in raw if len(t) >= 2]
                    text = " ".join(pieces).strip()
                    confs = [float(t[2]) for t in raw if len(t) >= 3]
                    record["text"] = text
                    record["ocr_engine"] = "easyocr_" + "_".join(langs)
                    record["num_boxes"] = len(pieces)
                    record["ocr_conf_mean"] = (sum(confs) / len(confs)) if confs else None
                except Exception as e:
                    record["text"] = ""
                    record["error"] = str(e)
                    record["ocr_engine"] = "easyocr"

            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()
            n_written += 1
            print(f"  ok  {fp.name}  ({len(record.get('text') or '')} chars)", flush=True)

    summary = {
        "n_files": n_written,
        "manifest": str(manifest_path.relative_to(BASE)),
        "note": "Sensitive — do not commit if policy requires.",
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nDone. Wrote {n_written} rows -> {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
