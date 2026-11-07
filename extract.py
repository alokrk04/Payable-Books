"""extract.py — document parsing & preliminary extraction.

Two paths to the same preliminary-JSON contract:

  1. **LLM vision path** (`ollama_extract`): sends the PDF page images plus
      the Autodraft schema to a local Ollama vision model (default
      ``gemma3:4b``, honouring ``OLLAMA_MODEL`` / ``OLLAMA_BASE_URL`` from the
      environment). The prompt instructs the model to *classify and transcribe
      only* — line items, header taxes/charges, printed totals — without doing
      any arithmetic of its own. The oracle (`erp.py`) owns all math.

  2. **Local fallback path** (`local_extract_text`): renders pages with pypdfium2
      and runs Tesseract OCR (or pypdf text extraction when the page has a text
      layer). Used when Ollama is not reachable and in CI. Its output is the same
      preliminary JSON, possibly with lower fidelity — downstream validation in
      ``main.py`` decides what books.

Both paths return a dict of the form::

    {
      "doc_kind": "INVOICE" | "CREDIT_MEMO" | "NOT_PAYABLE",
      "doc_type_detail": "e.g. ESTIMATE / REMINDER / DELIVERY_NOTE / ...",
      "reason": "...",                       # only for NOT_PAYABLE
      "currency": "EUR",
      "invoice_number": "...",
      "invoice_date": "YYYY-MM-DD",
      "due_date": "YYYY-MM-DD",
      "payment_terms_text": "...",
      "supplier": {"name": ..., "address": ..., "vat_id": ..., "iban": ...,
                   "country": ...},
      "buyer_text": "...",                   # raw bill-to block
      "buyer_country": "EE",
      "po_number": "...",                    # raw printed PO, "" if none
      "gross_total": "123.45",               # exactly as printed (dot-decimal)
      "subtotal": "...",
      "total_tax_amount": "...",
      "discount_amount": "...",
      "freight_charges": "...", "insurance_charges": "...",
      "extra_charges": "...", "excise_duties": "...",
      "taxes": [ {"tax_type":..., "tax_name":..., "tax_rate":...,
                  "tax_amount":...} ],       # header-level, as placed on doc
      "line_items": [ {"description":..., "item_type":..., "uom":...,
                       "quantity":..., "unit_price":..., "total":...,
                       "discount":..., "discount_percentage":...,
                       "tax_rate":..., "tax_amount":..., "taxes":[...] } ],
      "flags": {"compound_tax": false,       # e.g. VAT computed on levies
                "tax_inclusive_prices": false,
                "credit_applied": ""}        # informational only
    }

Strict rules enforced on every path: every number must literally appear on the
document; taxes stay where the document puts them; credit memos use positive
magnitudes under the same keys.
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import subprocess
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent / "documents"

# --------------------------------------------------------------------------- #
# LLM backend selection (Ollama local only — no cloud API).
#
#   LLM_BACKEND=ollama  -> local Ollama server (default model gemma3:4b,
#                          override with OLLAMA_MODEL, host with OLLAMA_BASE_URL)
#   LLM_BACKEND=off     -> no LLM; caller falls back to reviewed drafts
#   LLM_BACKEND=auto    -> ollama when the server answers, else off.
#   (default)
# --------------------------------------------------------------------------- #

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:4b")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "300"))


_REACHABLE_CACHE: dict[str, bool] = {}


def ollama_reachable(base_url: str | None = None, timeout: int = 5) -> bool:
    import urllib.request

    # Probe once per base URL per process: main.py calls active_backend()
    # per file, and without this cache 42 files × timeout would hang the
    # run when no server is listening.
    base_url = base_url or os.environ.get("OLLAMA_BASE_URL", OLLAMA_BASE_URL)
    if base_url in _REACHABLE_CACHE:
        return _REACHABLE_CACHE[base_url]
    try:
        with urllib.request.urlopen(base_url + "/api/tags",
                                    timeout=timeout) as resp:
            _REACHABLE_CACHE[base_url] = resp.status == 200
    except Exception:
        _REACHABLE_CACHE[base_url] = False
    return _REACHABLE_CACHE[base_url]


def active_backend() -> str:
    choice = os.environ.get("LLM_BACKEND", "auto").strip().lower()
    if choice == "ollama":
        return "ollama"
    if choice == "off":
        return "off"
    # auto (default): ollama when the server answers, else off.
    if ollama_reachable():
        return "ollama"
    return "off"


# --------------------------------------------------------------------------- #
# rendering + local OCR
# --------------------------------------------------------------------------- #

def render_pdf_pages(pdf_path: str | Path, scale: float = 2.0):
    """Render a PDF to a list of PIL images (one per page)."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    images = []
    for i in range(len(pdf)):
        images.append(pdf[i].render(scale=scale).to_pil())
    return images


def _ocr_with_tesseract(image) -> str:
    # Tesseract under this sandbox can only read files inside the workspace,
    # so spill the PNG next to the repo (cleaned up afterwards).
    tmp = Path(__file__).resolve().parent / f"_tmp_ocr_{os.getpid()}.png"
    try:
        image.save(str(tmp))
        proc = subprocess.run(
            ["tesseract", str(tmp), "stdout"],
            capture_output=True, text=True, timeout=120,
        )
        return proc.stdout
    except (FileNotFoundError, subprocess.SubprocessError):
        return ""
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


def _text_layer(pdf_path: str | Path) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        return "\n".join((pg.extract_text() or "") for pg in reader.pages)
    except Exception:
        return ""


def local_extract_text(pdf_path: str | Path) -> str:
    """Best-effort local text: OCR each rendered page; fall back to text layer."""
    images = render_pdf_pages(pdf_path)
    chunks = []
    for i, img in enumerate(images):
        ocr = _ocr_with_tesseract(img).strip()
        if len(ocr) < 50:  # blank/schematic page -> try embedded text
            ocr = ""
        chunks.append(f"===== page {i + 1} =====\n{ocr}")
    combined = "\n".join(chunks)
    if len(combined.strip()) < 100:
        combined = _text_layer(pdf_path)
    return combined


# --------------------------------------------------------------------------- #
# LLM vision path
# --------------------------------------------------------------------------- #

EXTRACTION_SYSTEM_PROMPT = """\
You are a precise document transcription engine for accounts-payable autodrafts.
Read the attached invoice/credit-memo page image(s) and transcribe what is PRINTED.

Rules (absolute):
1. NEVER invent numbers. Every amount, rate, quantity you emit must literally
   appear on the page. If a value is absent, emit "" — never compute it.
2. Do NOT do arithmetic. Do not sum lines, do not derive tax, do not "fix" totals.
3. Structural faithfulness: a tax shown per line goes in that line's taxes[] (or
   the line's tax_rate/tax_amount); a tax stated once for the whole document goes
   in header taxes[]. Never move a tax to make totals reconcile.
4. If the document is NOT a payable (estimate, proforma, reminder/dunning letter,
   delivery note, customs declaration, internal form, receipt without amounts
   owed, duplicate copy of another invoice in the same file), set
   doc_kind to NOT_PAYABLE with doc_type_detail + reason.
5. CREDIT_MEMO uses the identical keys as an invoice with POSITIVE magnitudes.
6. Numbers out are dot-decimal strings ("1234.56"): convert continental formats
   ("1.234,56" -> "1234.56"). Keep the printed precision.
7. unit_price is the NET unit price as printed (exclude any indication that the
    price includes tax — if the document labels prices tax-inclusive, set
    flags.tax_inclusive_prices=true and still transcribe the printed figures).
8. If one tax is computed on top of another (e.g. VAT on a levy-inclusive base),
   set flags.compound_tax=true and transcribe each printed rate AND amount.
9. Transcribe the bill-to block verbatim (buyer_text), the supplier block
   (name/address/vat_id/iban/country), payment-terms text, PO as printed,
   invoice/credit number, ISO dates, currency, and the printed gross_total.
"""

EXTRACTION_USER_TEMPLATE = """\
Transcribe the attached document page(s) into the preliminary JSON contract below.
Return ONLY valid JSON, no commentary.

Contract:
{{
  "doc_kind": "INVOICE | CREDIT_MEMO | NOT_PAYABLE",
  "doc_type_detail": "",
  "reason": "",
  "currency": "",
  "invoice_number": "",
  "invoice_date": "YYYY-MM-DD",
  "due_date": "YYYY-MM-DD",
  "payment_terms_text": "",
  "supplier": {{"name": "", "address": "", "vat_id": "", "iban": "", "country": ""}},
  "buyer_text": "",
  "buyer_country": "",
  "po_number": "",
  "gross_total": "",
  "subtotal": "",
  "total_tax_amount": "",
  "discount_amount": "",
  "freight_charges": "",
  "insurance_charges": "",
  "extra_charges": "",
  "excise_duties": "",
  "taxes": [{{"tax_type": "", "tax_name": "", "tax_rate": "", "tax_amount": ""}}],
  "line_items": [{{"description": "", "item_type": "GOODS|SERVICE|FREIGHT|TAX",
    "uom": "", "quantity": "", "unit_price": "", "total": "",
    "discount": "", "discount_percentage": "",
    "tax_rate": "", "tax_amount": "", "taxes": []}}],
  "flags": {{"compound_tax": false, "tax_inclusive_prices": false, "credit_applied": ""}}
}}

Local OCR (unreliable — the IMAGES are authoritative, use OCR only as a hint):
---
{ocr_hint}
---
"""


def extract_preliminary(pdf_path: str | Path) -> tuple[dict | None, str]:
    """Best available preliminary extraction.

    Returns (prelim_json_or_None, ocr_text). The backend follows
    ``LLM_BACKEND`` (see :func:`active_backend`); when Ollama is not active
    ``None`` is returned and the caller (main.py) falls back to the reviewed
    transcription store in ``transcriptions.py`` (``PRELIMS``).
    """
    ocr_text = local_extract_text(pdf_path)
    backend = active_backend()
    if backend == "ollama":
        return ollama_extract(pdf_path, ocr_hint=ocr_text), ocr_text
    return None, ocr_text


# --------------------------------------------------------------------------- #
# Ollama (local) vision path — stdlib HTTP, no extra dependencies
# --------------------------------------------------------------------------- #

def _pil_to_b64(image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _ollama_chat(messages: list[dict], model: str | None = None,
                 base_url: str | None = None,
                 timeout: int | None = None) -> str:
    """POST /api/chat with JSON-constrained decoding; return message content."""
    import urllib.request

    body = json.dumps({
        "model": model or OLLAMA_MODEL,
        "messages": messages,
        "format": "json",
        "stream": False,
        "options": {"temperature": 0, "num_ctx": 16384, "num_predict": 8192},
    }).encode()
    req = urllib.request.Request(
        (base_url or OLLAMA_BASE_URL) + "/api/chat", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout or OLLAMA_TIMEOUT) as resp:
        data = json.loads(resp.read())
    return data["message"]["content"]


def _parse_json_response(text: str) -> dict:
    """Tolerantly parse model JSON (code fences / prose around the object)."""
    text = text.strip()
    try:
        return json.loads(text)
    except ValueError:
        pass
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        try:
            return json.loads(text)
        except ValueError:
            pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start:end + 1])
    raise ValueError("no JSON object found in model response")


def ollama_extract(pdf_path: str | Path, ocr_hint: str = "",
                   model: str | None = None) -> dict:
    """Transcribe a PDF with a local Ollama vision model. Returns prelim JSON."""
    images = render_pdf_pages(pdf_path, scale=1.5)
    content: list[dict] = [
        {"type": "text",
         "text": EXTRACTION_USER_TEMPLATE.format(ocr_hint=ocr_hint[:6000])}
    ]
    # Ollama native message format carries images alongside the text.
    ollama_images = [_pil_to_b64(img) for img in images]
    messages = [
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": content[0]["text"],
         "images": ollama_images},
    ]
    return _parse_json_response(_ollama_chat(messages, model=model))


def ollama_correct(pdf_path: str | Path, previous_json: str,
                   booked, printed, currency: str,
                   model: str | None = None) -> dict:
    """One bounded re-examination round via the local model."""
    images = render_pdf_pages(pdf_path, scale=1.5)
    messages = [
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        {"role": "user",
         "content": CORRECTION_USER_TEMPLATE.format(
             booked=booked, currency=currency, printed=printed,
             previous_json=previous_json),
         "images": [_pil_to_b64(img) for img in images]},
    ]
    return _parse_json_response(_ollama_chat(messages, model=model))


# --------------------------------------------------------------------------- #
# correction prompt for the bounded validation loop
# --------------------------------------------------------------------------- #

CORRECTION_USER_TEMPLATE = """\
Your previous transcription of this payable does NOT reconcile: the ERP recompute
from your components gives will_book_gross={booked} {currency} but the document
prints gross_total={printed}.

Re-examine ONLY the component placement (which numbers are line vs header, which
tax sits where, whether a discount/charge was misread). Constraints:
- every number must still literally appear on the document;
- do not move a tax from where the document places it;
- do not invent a rate/amount to force the balance;
- if the document genuinely cannot reconcile (e.g. an unexplained credit applied
  with no supporting detail), say so with "irreconcilable": true and why.

Previous JSON:
{previous_json}

Return ONLY the corrected JSON in the same contract (plus optional
"irreconcilable" + "_note" keys).
"""
