"""main.py — the bookable-payable pipeline. One command:  python main.py

Backend selection via LLM_BACKEND (see extract.active_backend):
  LLM_BACKEND=ollama  local Ollama vision model (OLLAMA_MODEL, default gemma3:4b)
  LLM_BACKEND=off     reviewed transcriptions only (fast, deterministic)
  LLM_BACKEND=auto    ollama if the server answers, else off (default)

For every ``documents/*.pdf``:
  1. extract a preliminary JSON (local Ollama vision model when reachable,
     otherwise the reviewed transcriptions in ``transcriptions.py``),
  2. resolve master-data codes (``master_data_matcher.py``),
  3. shape the Autodraft payable (``AUTODRAFT_SCHEMA.md``),
  4. run the oracle (``erp_book``) and compare ``will_book_gross`` to the
     printed ``gross_total`` to the exact cent,
  5. on mismatch, run a strictly bounded correction loop (max 2 Ollama
     re-examinations; without Ollama the mismatch is reported, never fudged),
  6. write ``output/<stem>.json`` as ``{"file","payables","declined"}``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from erp import erp_book
from extract import (extract_preliminary, active_backend, ollama_correct)
from master_data_matcher import (
    get_store, match_supplier, match_buyer, match_tax,
    match_payment_term, match_po,
)
from transcriptions import PRELIMS

ROOT = Path(__file__).resolve().parent
DOCS_DIR = ROOT / "documents"
OUTPUT_DIR = ROOT / "output"
MAX_CORRECTION_ROUNDS = 2


# --------------------------------------------------------------------------- #
# prelim -> payable
# --------------------------------------------------------------------------- #

def _clean_tax(t: dict, store) -> dict:
    # Do not mutate the caller's dict (PRELIMS entries are reused across runs):
    # read the internal matcher-only key instead of popping it.
    country = t.get("country", "")
    code = match_tax(t.get("tax_rate"), country=country or None,
                     tax_type=t.get("tax_type"), tax_name=t.get("tax_name"),
                     store=store)
    return {
        "tax_type": t.get("tax_type", ""),
        "tax_name": t.get("tax_name", ""),
        "tax_rate": t.get("tax_rate", ""),
        "tax_amount": t.get("tax_amount", ""),
        "tax_type_code": code or "",
    }


def build_payable(pre: dict, store) -> dict:
    sup = pre.get("supplier", {})
    supplier_id = match_supplier(sup.get("name"), address=sup.get("address"),
                                 vat_id=sup.get("vat_id"), iban=sup.get("iban"),
                                 country=sup.get("country"), store=store)
    buyer = match_buyer(pre.get("buyer_text"), buyer_country=pre.get("buyer_country"),
                        store=store)
    term_id = match_payment_term(pre.get("payment_terms_text"),
                                 invoice_date=pre.get("invoice_date"),
                                 due_date=pre.get("due_date"), store=store)
    po_number = (pre.get("po_number") or "").strip()
    po_id = match_po(po_number, store=store)

    line_items = []
    for li in pre.get("line_items", []):
        taxes = [_clean_tax(dict(t), store) for t in (li.get("taxes") or [])]
        line_items.append({
            "description": li.get("description", ""),
            "item_type": li.get("item_type", "SERVICE"),
            "uom": li.get("uom", ""),
            "quantity": li.get("quantity", ""),
            "unit_price": li.get("unit_price", ""),
            "total": li.get("total", ""),
            "discount": li.get("discount", ""),
            "discount_percentage": li.get("discount_percentage", ""),
            "tax_rate": li.get("tax_rate", ""),
            "tax_amount": li.get("tax_amount", ""),
            "taxes": taxes,
        })

    kind = pre.get("doc_kind", "INVOICE")
    return {
        "invoice_number": pre.get("invoice_number", ""),
        "invoice_date": pre.get("invoice_date", ""),
        "due_date": pre.get("due_date", ""),
        "invoice_type": "CREDIT_MEMO" if kind == "CREDIT_MEMO" else "INVOICE",
        "currency": pre.get("currency", ""),
        "supplier": {
            "name": sup.get("name", ""),
            "supplier_id": supplier_id or "",
            "address": sup.get("address", ""),
            "vat_id": sup.get("vat_id", ""),
        },
        "buyer": buyer,
        "payment_term_id": term_id or "",
        "po_number": po_number,
        "po_id": po_id or "",
        "gross_total": pre.get("gross_total", ""),
        "subtotal": pre.get("subtotal", ""),
        "total_tax_amount": pre.get("total_tax_amount", ""),
        "discount_amount": pre.get("discount_amount", ""),
        "freight_charges": pre.get("freight_charges", ""),
        "insurance_charges": pre.get("insurance_charges", ""),
        "extra_charges": pre.get("extra_charges", ""),
        "excise_duties": pre.get("excise_duties", ""),
        "taxes": [_clean_tax(dict(t), store) for t in (pre.get("taxes") or [])],
        "line_items": line_items,
    }


def _parse_gross(s: str) -> float | None:
    try:
        return round(float(str(s).strip()), 2)
    except (TypeError, ValueError):
        return None


def check_booking(payable: dict) -> tuple[bool, float | None, float | None]:
    """(books_exactly, will_book_gross, printed_gross)."""
    printed = _parse_gross(payable.get("gross_total"))
    if printed is None:
        return False, None, None
    try:
        booked = erp_book(payable)["will_book_gross"]
    except Exception:
        return False, None, printed
    return abs(booked - printed) < 0.0001, booked, printed


# --------------------------------------------------------------------------- #
# correction loop (bounded; LLM only — never invents numbers locally)
# --------------------------------------------------------------------------- #

def correct_with_llm(pdf_path: Path, pre: dict, payable: dict,
                     booked, printed) -> dict | None:
    """Bounded re-examination via the local Ollama model.

    Never invents numbers locally: each round re-reads the page images and is
    only accepted when the rebuilt payable foots exactly on printed figures.
    """
    backend = active_backend()
    if backend != "ollama":
        return None
    store = get_store()
    current_pre, current = pre, payable
    for _ in range(MAX_CORRECTION_ROUNDS):
        ok, booked_now, _ = check_booking(current)
        if ok:
            return current
        try:
            new_pre = ollama_correct(
                pdf_path, json.dumps(current_pre, ensure_ascii=False),
                booked_now, current.get("gross_total"),
                current.get("currency"))
        except Exception as exc:
            print(f"  [warn] ollama correction failed: {exc}",
                  file=sys.stderr)
            return None
        if new_pre.get("irreconcilable"):
            return None
        new_payable = build_payable(new_pre, store)
        ok, _, _ = check_booking(new_payable)
        if ok:
            return new_payable
        current_pre, current = new_pre, new_payable
    return None


# --------------------------------------------------------------------------- #
# per-file driver
# --------------------------------------------------------------------------- #

def process_file(pdf_path: Path, store) -> dict:
    stem = pdf_path.stem
    backend = active_backend()
    use_llm = backend == "ollama"
    if use_llm:
        print(f"  [llm:ollama] extracting {stem} ...")
        try:
            pre, _ = extract_preliminary(pdf_path)
        except Exception as exc:
            print(f"  [warn] LLM extraction failed for {stem}: {exc}", file=sys.stderr)
            pre = None
        if pre is None:
            pre = PRELIMS.get(stem)
    else:
        pre = PRELIMS.get(stem)

    if pre is None:
        return {"file": pdf_path.name, "payables": [],
                "declined": [{"doc_type": "UNKNOWN",
                              "reason": "no extraction available for this file"}]}

    if pre.get("doc_kind") == "NOT_PAYABLE":
        return {"file": pdf_path.name, "payables": [],
                "declined": [{"doc_type": pre.get("doc_type_detail", "UNKNOWN"),
                              "reason": pre.get("reason", "")}]}

    payable = build_payable(pre, store)
    ok, booked, printed = check_booking(payable)
    if not ok and use_llm:
        fixed = correct_with_llm(pdf_path, pre, payable, booked, printed)
        if fixed is not None:
            payable = fixed
            ok, booked, printed = check_booking(payable)

    status = "BOOKS " if ok else "MISMATCH"
    print(f"  [{status}] {stem}: booked={booked} printed={printed} "
          f"{payable.get('currency')}")
    if not ok:
        print(f"    -> emitted honestly; document flagged in DESIGN.md "
              f"(booked {booked} vs printed {printed})")
    return {"file": pdf_path.name, "payables": [payable], "declined": []}


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(DOCS_DIR.glob("*.pdf"))
    if not pdfs:
        print("no PDFs found in documents/", file=sys.stderr)
        return 1
    store = get_store()
    n_ok = n_bad = 0
    for pdf in pdfs:
        result = process_file(pdf, store)
        (OUTPUT_DIR / f"{pdf.stem}.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        for payable in result["payables"]:
            ok, _, _ = check_booking(payable)
            n_ok += ok
            n_bad += (not ok)
    print(f"\nwrote {len(pdfs)} files to output/ — books: {n_ok}, "
          f"mismatch: {n_bad}, declined-only: {len(pdfs) - n_ok - n_bad}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
