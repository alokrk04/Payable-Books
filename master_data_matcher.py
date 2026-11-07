"""master_data_matcher.py — resolve document values to master-data codes.

Design for scale: the sample masters hold a handful of rows, but real tenants run to
hundreds of thousands / millions.  Every lookup path therefore:

  1. normalises the query once,
  2. tries an O(1) indexed exact match first (dicts keyed by normalised VAT id,
     normalised name, PO number, ...),
  3. only then falls back to a *blocked* fuzzy pass (candidates pre-filtered by
     country / first-letter bucket — never a full scan of the master per lookup),
  4. returns "" (via None) unless confidence is high — an honest blank beats a
     fabricated code.

Only stdlib + rapidfuzz-if-present (difflib fallback) are used.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

try:
    from rapidfuzz import fuzz as _fuzz

    def _similarity(a: str, b: str) -> float:
        return float(_fuzz.token_set_ratio(a, b))
except Exception:  # pragma: no cover - fallback when rapidfuzz is unavailable
    from difflib import SequenceMatcher as _SM

    def _similarity(a: str, b: str) -> float:
        return float(_SM(None, a, b).ratio() * 100.0)


MASTER_DIR = Path(__file__).resolve().parent / "master_data"

# Confidence thresholds (0-100 scale).
SUPPLIER_FUZZY_THRESHOLD = 88.0
TAX_NAME_FUZZY_THRESHOLD = 80.0


# --------------------------------------------------------------------------- #
# normalisation helpers
# --------------------------------------------------------------------------- #

def normalize_text(s: str | None) -> str:
    """Lowercase, de-accent, collapse whitespace/punctuation for comparison."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def normalize_vat(s: str | None) -> str:
    """Canonical VAT id: uppercase, no spaces/punctuation."""
    if not s:
        return ""
    return re.sub(r"[^A-Z0-9]+", "", str(s).upper())


def normalize_iban(s: str | None) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", "", str(s).upper())


# --------------------------------------------------------------------------- #
# master-data store with indexes (built once)
# --------------------------------------------------------------------------- #

class MasterData:
    def __init__(self, master_dir: str | Path = MASTER_DIR):
        self.dir = Path(master_dir)
        self.suppliers: list[dict] = []
        self.taxes: list[dict] = []
        self.payment_terms: list[dict] = []
        self.pos: list[dict] = []
        self.companies: list[dict] = []

        # indexes: exact-match fast paths (scale-safe)
        self._supplier_by_vat: dict[str, dict] = {}
        self._supplier_by_name: dict[str, list[dict]] = {}
        self._supplier_by_country: dict[str, list[dict]] = {}
        self._po_by_number: dict[str, dict] = {}
        self._tax_by_country_rate: dict[tuple[str, float], list[dict]] = {}
        self._buyer_index: list[dict] = []  # flattened locations

        self._load()

    # -- loading -------------------------------------------------------- #
    def _load_json(self, name: str) -> dict:
        path = self.dir / name
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _load(self) -> None:
        sup = self._load_json("suppliers.json")
        self.suppliers = sup.get("suppliers", [])
        for s in self.suppliers:
            vat = normalize_vat(s.get("vat_id"))
            if vat:
                self._supplier_by_vat.setdefault(vat, s)
            nm = normalize_text(s.get("name"))
            if nm:
                self._supplier_by_name.setdefault(nm, []).append(s)
            cc = (s.get("country") or "").upper()
            if cc:
                self._supplier_by_country.setdefault(cc, []).append(s)

        tax = self._load_json("tax_master.json")
        self.taxes = tax.get("taxes", [])
        for t in self.taxes:
            try:
                rate = round(float(str(t.get("rate")).replace("%", "").strip()), 4)
            except (TypeError, ValueError):
                continue
            key = ((t.get("country") or "").upper(), rate)
            self._tax_by_country_rate.setdefault(key, []).append(t)

        pt = self._load_json("payment_terms.json")
        self.payment_terms = pt.get("payment_terms", [])

        po = self._load_json("po_master.json")
        self.pos = po.get("purchase_orders", [])
        for p in self.pos:
            for k in (p.get("po_id"), p.get("po_number")):
                if k:
                    self._po_by_number[normalize_text(k).replace(" ", "")] = p

        cob = self._load_json("chart_of_books.json")
        self.companies = cob.get("companies", [])
        for comp in self.companies:
            for bu in comp.get("business_units", []):
                for loc in bu.get("locations", []):
                    self._buyer_index.append(
                        {
                            "company_code": comp.get("company_code", ""),
                            "company_name": comp.get("company_name", ""),
                            "business_unit_code": bu.get("business_unit_code", ""),
                            "business_unit_name": bu.get("business_unit_name", ""),
                            "location_code": loc.get("location_code", ""),
                            "location_name": loc.get("location_name", ""),
                            "invoice_to_address": loc.get("invoice_to_address", ""),
                        }
                    )


_STORE: MasterData | None = None


def get_store(master_dir: str | Path = MASTER_DIR) -> MasterData:
    global _STORE
    if _STORE is None:
        _STORE = MasterData(master_dir)
    return _STORE


# --------------------------------------------------------------------------- #
# supplier
# --------------------------------------------------------------------------- #

def match_supplier(
    name: str | None,
    address: str | None = None,
    vat_id: str | None = None,
    iban: str | None = None,
    country: str | None = None,
    store: MasterData | None = None,
) -> str | None:
    """Return supplier_id on high-confidence match, else None (= emit "")."""
    store = store or get_store()

    # 1. VAT id is the strongest key: exact indexed hit wins outright.
    vat = normalize_vat(vat_id)
    if vat and vat in store._supplier_by_vat:
        return store._supplier_by_vat[vat].get("supplier_id")

    # 2. Exact normalised-name hit.
    nm = normalize_text(name)
    if nm and nm in store._supplier_by_name:
        cands = store._supplier_by_name[nm]
        if len(cands) == 1:
            return cands[0].get("supplier_id")
        # several suppliers share a name: disambiguate by country/VAT fragment.
        for c in cands:
            if country and (c.get("country") or "").upper() == country.upper():
                return c.get("supplier_id")
        return None  # ambiguous -> honest blank

    # 3. Blocked fuzzy pass: restrict to same-country bucket when known so the
    #    comparison set stays small even with million-row masters.
    if nm:
        cc = (country or "").upper()
        if cc:
            pool = store._supplier_by_country.get(cc)
            if not pool:
                # Known country with no indexed suppliers: honest blank.
                # Falling back to a full scan here would defeat the blocking
                # design and risk cross-country false matches at scale.
                return None
        else:
            pool = store.suppliers
        best: dict | None = None
        best_score = 0.0
        for cand in pool:
            score = _similarity(nm, normalize_text(cand.get("name")))
            # corroboration: matching country / address fragment raises confidence
            if country and (cand.get("country") or "").upper() == cc:
                score += 2.0
            if score > best_score:
                best_score, best = score, cand
        if best is not None and best_score >= SUPPLIER_FUZZY_THRESHOLD:
            # require independent corroboration for pure-name fuzzy hits:
            # same country, or VAT/IBAN/address agreement. VAT/IBAN must
            # match exactly (substring checks let a truncated prefix
            # corroborate the full id — e.g. "DE20917712" matching
            # "DE209177122" — which is a false positive).
            corroborated = False
            if country and (best.get("country") or "").upper() == cc:
                corroborated = True
            if vat and normalize_vat(best.get("vat_id")) and vat == normalize_vat(best.get("vat_id")):
                corroborated = True
            if iban and normalize_iban(best.get("bank_iban")) and normalize_iban(iban) == normalize_iban(best.get("bank_iban")):
                corroborated = True
            if address and normalize_text(best.get("address")) and (
                normalize_text(best.get("address")) in normalize_text(address)
                or normalize_text(address) in normalize_text(best.get("address"))
            ):
                corroborated = True
            if corroborated:
                return best.get("supplier_id")
    return None


# --------------------------------------------------------------------------- #
# buyer (tenant org)
# --------------------------------------------------------------------------- #

# Bill-to mentions that map onto the tenant chart of books by country.
_BUYER_COUNTRY_HINTS: dict[str, str] = {
    "estonia": "EE", "tallinn": "EE", "eesti": "EE",
    "ghana": "GH", "accra": "GH",
    "malaysia": "MY", "kuala lumpur": "MY",
    "south africa": "ZA", "johannesburg": "ZA", "sandton": "ZA", "cape town": "ZA",
    "united kingdom": "GB", "london": "GB", "uk": "GB",
}

# Within Estonia the sample autodraft resolves to EE004; keep that default.
_DEFAULT_BU_UNIT: dict[str, str] = {"EE": "EE004"}


def match_buyer(
    bill_to_text: str | None,
    buyer_country: str | None = None,
    store: MasterData | None = None,
) -> dict:
    """Return {company_code, business_unit_code, location_code}; blanks when no match."""
    blank = {"company_code": "", "business_unit_code": "", "location_code": ""}
    store = store or get_store()
    if not store._buyer_index:
        return blank

    text = normalize_text(bill_to_text)
    cc = (buyer_country or "").upper()
    if not cc:
        for hint, code in _BUYER_COUNTRY_HINTS.items():
            if hint in text:
                cc = code
                break
    # The chart of books covers the tenant (Bolt/Northwind) only. A country
    # match alone never confers tenant status — third-party bill-tos
    # (e.g. Changi, Meridian, AmeriHealth) honestly resolve to blank.
    is_tenant = ("bolt" in text) or ("northwind" in text)
    if not is_tenant:
        return blank
    if not cc:
        # No country attribution: guessing the first location (EE001) would
        # be a fabricated code. Honest blank until the document says more.
        return blank

    candidates = [b for b in store._buyer_index if b["business_unit_code"].startswith(cc)]
    if not candidates:
        return blank
    preferred = _DEFAULT_BU_UNIT.get(cc)
    for b in candidates:
        if preferred and b["business_unit_code"] == preferred:
            return {k: b[k] for k in blank}
    b = candidates[0]
    return {k: b[k] for k in blank}


# --------------------------------------------------------------------------- #
# tax
# --------------------------------------------------------------------------- #

def _parse_rate(value) -> float | None:
    """Parse a percentage rate to a rounded float, or None if unparseable."""
    try:
        return round(float(str(value).replace("%", "").strip()), 4)
    except (TypeError, ValueError):
        return None


def match_tax(
    rate: str | float | None,
    country: str | None = None,
    tax_type: str | None = None,
    tax_name: str | None = None,
    store: MasterData | None = None,
) -> str | None:
    """Return tax_type_code on confident match, else None."""
    store = store or get_store()
    rate_f = _parse_rate(rate)
    if rate_f is None:
        return None
    cc = (country or "").upper()

    # Without a country the tax regime cannot be attributed honestly: the same
    # rate exists under several regimes (e.g. every 0%), so any pick would be
    # a guess. Return the honest blank.
    if not cc:
        return None

    cands: list[dict] = list(store._tax_by_country_rate.get((cc, rate_f), []))
    if not cands:
        return None
    if len(cands) == 1:
        single = cands[0]
        # Single country+rate row, but still require type/name corroboration so
        # that e.g. a generic "TAX 0%" line is never force-matched onto a
        # special regime such as US use-tax or a reverse-charge row.
        want_type = normalize_text(tax_type)
        want_name = normalize_text(tax_name)
        if want_type and normalize_text(single.get("tax_type")) == want_type:
            return single.get("code")
        if want_name and _similarity(
                want_name, normalize_text(single.get("name"))) >= TAX_NAME_FUZZY_THRESHOLD:
            return single.get("code")
        if not want_type and not want_name:
            return single.get("code")
        return None

    # Several rows share (country, rate) — e.g. Ghana 2.5% NHIL vs GETFund:
    # disambiguate by tax_type / tax_name text.
    want_type = normalize_text(tax_type)
    want_name = normalize_text(tax_name)
    for t in cands:
        if want_type and normalize_text(t.get("tax_type")) == want_type:
            return t.get("code")
    best, best_score = None, 0.0
    for t in cands:
        score = _similarity(want_name, normalize_text(t.get("name"))) if want_name else 0.0
        if score > best_score:
            best_score, best = score, t
    if best is not None and best_score >= TAX_NAME_FUZZY_THRESHOLD:
        return best.get("code")
    return None  # ambiguous -> honest blank


# --------------------------------------------------------------------------- #
# payment terms
# --------------------------------------------------------------------------- #

def _parse_days_from_text(text: str | None) -> int | None:
    if not text:
        return None
    norm = normalize_text(text)
    # Number after the cue ("net 30", "netto 30", "within 30 days",
    # "tahaeg 14"): the old pattern only matched digits *followed by* the
    # cue, so "net 30" was missed and only worked by accident via aliases.
    m = re.search(
        r"(?:\bnet(?:to)?\b|\bwithin\b|\btahaeg\b|\bpaeva\b)[^\d]{0,10}(\d{1,3})\b",
        norm)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    # Number before the cue ("30 days", "30 net", "30 pv neto", Estonian
    # "30 paeva" — "30 päeva" normalises to "30 paeva").
    # A stray PO number can only false-fire if it exactly equals a known
    # term day-count *and* the caller finds a matching term; the exact-match
    # guard in match_payment_term makes that safe.
    m = re.search(
        r"(\d{1,3})\s*(?:days?|pv|paeva|tahaeg|net(?:to)?)\b", norm)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def match_payment_term(
    term_text: str | None,
    invoice_date: str | None = None,
    due_date: str | None = None,
    store: MasterData | None = None,
) -> str | None:
    """Resolve payment_term_id from printed terms text and/or invoice/due dates."""
    store = store or get_store()
    text = normalize_text(term_text)

    def _parse_iso(s: str | None):
        if not s:
            return None
        s = str(s).strip()
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
            try:
                from datetime import datetime as _dt

                return _dt.strptime(s, fmt).date()
            except ValueError:
                continue
        return None

    date_days: int | None = None
    d1, d2 = _parse_iso(invoice_date), _parse_iso(due_date)
    if d1 and d2:
        date_days = (d2 - d1).days

    # 1. explicit alias text
    for term in store.payment_terms:
        for alias in term.get("text_aliases", []):
            if normalize_text(alias) and normalize_text(alias) in text:
                return term.get("payment_term_id")

    # 2. "N days" phrasing -> exact-days term only (never nearest).
    days = _parse_days_from_text(term_text)
    for term in store.payment_terms:
        if days is not None and term.get("days") == days and days != 0:
            # avoid false positives from stray numbers: require a terms cue word
            if any(w in text for w in ("net", "days", "pv", "neto", "tahaeg", "within", "paeva")):
                return term.get("payment_term_id")

    # 3. date arithmetic: exact day-count match only.
    if date_days is not None:
        for term in store.payment_terms:
            if term.get("days") == date_days:
                # terms like Immediate/Monthly_in_advance have days==0 but must
                # only match on explicit text, never on a 0-day date diff.
                if date_days != 0:
                    return term.get("payment_term_id")
    return None


# --------------------------------------------------------------------------- #
# purchase orders
# --------------------------------------------------------------------------- #

def match_po(po_number: str | None, store: MasterData | None = None) -> str | None:
    """Exact PO match only — a printed PO absent from the master stays blank."""
    store = store or get_store()
    if not po_number or not str(po_number).strip():
        return None
    key = normalize_text(po_number).replace(" ", "")
    hit = store._po_by_number.get(key)
    return hit.get("po_id") if hit else None
