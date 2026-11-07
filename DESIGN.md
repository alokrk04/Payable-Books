# DESIGN.md — The Bookable Payable

## 1. What we understood late (the shift)

On day one each document looked like a bag of fields to copy into the schema:
quantity here, rate there, total at the bottom. That approach books roughly a
third of the set and then stalls on failures with nothing visibly in common —
a 15% discount that isn't 15% of anything, a VAT that won't derive, a total
off by one cent, lines that add up to less than the subtotal.

The failures become one thing once you stop asking *"what are the fields?"*
and start asking ***"on what base is each tax computed?"*** The ERP
(`erp.py`) always applies a rate to the *plain net* (lines minus header
discount). Real documents rarely do. Every hard document in this set is a
different answer to the base question:

* **Ghana (INV-19):** VAT 15% is computed on the *levy-inclusive* value
  (6,996, not 6,600). The amount (1,049.40) is printed, the base is not the
  plain net. The schema anticipates exactly this: *"give an explicit
  `tax_amount` when … the base isn't the plain net — e.g. a compound levy."*
* **Thailand (HLD-01):** VAT 7% on the agency-fee-inclusive total, and a 3%
  withholding that *subtracts* (negative `tax_amount`).
* **Portugal (HLD-05):** the IVA base *includes* the IEC excise
  (1,796.54 − 1,049.60 + 88.33 = 835.27). Per-line excise cannot be
  represented in the ERP at all, which forces the header collapse described
  below — the one place where we knowingly drop per-line detail, because the
  machine has no slot for it.
* **Tax-inclusive retail (INV-25, INV-06, INV-20's incl column):** the printed
  "unit price" already contains the tax, so the ERP's net-price assumption
  double-counts. Where every line carries its rate (INV-25, 23%), the net is
  `incl / (1 + rate)` — a deterministic function of two printed numbers, not
  an invention. Where rates are unknowable per item (INV-06, mixed
  standard/zero-rated groceries with no per-line rates), the honest encoding
  is inclusive lines with *no* tax and the printed VAT kept informationally in
  `total_tax_amount`.
* **Per-line rounding vs aggregate (INV-13, INV-28, DU-06):** each line shows
  a rate, but deriving per line overshoots the printed tax by exactly one
  cent (25,023.13 vs 25,023.12). The document itself computes tax on the
  aggregated base, so the header summary — which prints rate *and* amount —
  governs. Our rule: a numeric rate per line wins *only if* per-line
  derivation foots to the cent; otherwise the header's printed amounts win.
  Same gross, wrong structure still fails, but a structure that cannot foot
  fails first.
* **Discounts with unprinted scope (INV-02):** "Allahindlus 15% −48.09" is a
  single summary line; 15% of the whole (538.60) would be 80.79. It is 15% of
  lines 1–6 only (320.60). The schema has no header percentage field, so it
  is stored as the printed header `discount_amount` — placement preserved,
  amount grounded, scope left to the document's own arithmetic.
* **Pre-rounded inputs (INV-10, HLD-10, DU-11):** VAT on the pre-rounding
  base (115.03 on 479.28, not 479.27), a 0.01 rounding line already absorbed
  in the explicit header VAT (excluded to avoid double-count), a six-decimal
  unit price kept verbatim. Explicit amounts wherever the base is not the
  plain net; derivation only where it is exact.

The general form: **transcribe the printed arithmetic, identify each tax's
true base, and use explicit amounts exactly where the base isn't the plain
net.** That is what the `tax_amount` field is for, what negative amounts are
for, and what `total_tax_amount` (informational) vs `taxes[]` (computational)
is for.

## 2. What the system does with a document unlike any it has seen

It does the same four things, in order, with no per-document branches anywhere
in the code — there is not one `if filename == …` in the pipeline:

1. **Transcribe, don't compute.** The extractor (vision LLM, or the reviewed
   fallback store) copies printed numbers and their placement only. It is
   forbidden from doing arithmetic; the oracle owns all math. Supporting
   detail without its own extended total (kit breakdowns, shipment specs,
   duplicate copies, customs backup pages) stays out of `line_items` because
   the document's own totals exclude it — including it would contradict the
   printed arithmetic, not complete it.
2. **Resolve codes by index, blank by default.** Suppliers by VAT id then
   blocked fuzzy-with-corroboration; taxes by (country, rate) with
   type/name disambiguation (Ghana 2.5% NHIL vs GETFund); terms by alias or
   *exact* day-count; POs by exact number only. Country-less tax guesses and
   third-party buyers resolve to `""`. A blank is a legitimate answer; every
   code in `output/` can point at its master row.
3. **Ask the oracle.** `erp_book` recomputes from our components; we compare
   to the printed gross to the cent.
4. **Correct only with grounding.** The retry loop (bounded, Ollama-only) may
   move a tax between line and header *iff* the alternative uses solely
   printed numbers, respects where the document places the tax, and foots
   exactly. A "fix" that would corrupt an already-correct record can never
   fire, because a correct record never enters the loop. And when nothing
   grounded foots, the system emits the faithful record anyway and says so —
   it never invents a rate, moves a tax for convenience, or renames a credit
   a discount… with one disclosed exception below.

This generalises because the decisions are about *arithmetic grounding*, not
document identity: derive where derivation is exact, state explicitly where
printed, omit where absent, refuse where inconsistent.

## 3. The documents that could not be solved the way the others were

**INV-26 (Malaysia, 873.53 MYR).** Thirty-four printed lines sum to 846.13;
the subtotal, SST specification, amount-in-words, and grand total all say
873.53. The 27.40 gap corresponds to no printed line (numbering jumps 29 →
31 over a cost-center note). No schema field can absorb +27.40 without
inventing a charge, and restating the gross as 846.13 would contradict four
printed totals. We emit the lines and the printed gross as-is (oracle:
846.13) and record the document's own inconsistency here rather than fake a
reconciliation.

**INV-37 (US utilities, $2,487.73).** Every section is exact, but the final
sum is one cent high (1,942.07 + 416.65 + 122.00 + 7.02 = 2,487.74). Same
treatment: faithful components, printed gross, one-cent oracle gap disclosed.

**INV-04 / INV-07 (South Africa).** The borderline case we *did* solve:
"Less Amount Credited 13,110.00" with no supporting credit memo in the file.
`discount_amount` is the schema's only header-level reduction mechanism, and
the figure is printed, so the payable books at the genuine amount due
(6,620.55) with the VAT kept on its line. We flag the judgment call: had the
credit been unexplained *and* unquantified we would have declined to book,
per the brief's third question — refusing to fake it outranks fitting it.
