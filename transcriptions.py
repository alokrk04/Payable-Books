"""transcriptions.py — reviewed preliminary extractions (the local fallback store).

Each entry follows the preliminary-JSON contract defined in ``extract.py``.
These are the human-reviewed transcriptions that stand in for the Ollama
vision-LLM output when the local Ollama server is not reachable (see
``main.py``): every number below was read off the corresponding PDF page.
``main.py`` still runs every entry through master-data resolution and the
``erp.py`` oracle.

Conventions used throughout (see DESIGN.md for why):
* ``qty``/``unit`` are the printed quantity and NET unit price. Two systematic
  exceptions, both deterministic functions of printed figures, never fudges:
  - tax-inclusive unit prices (INV-25: ``P.VENDA C/IVA``) are stored NET as
    ``incl / (1 + rate)`` so the printed per-line rate can stay on the line;
  - ``PU 100`` price units (DU-05) are stored per-1 as ``listed / 100``.
* Single-charge lines with no printed quantity use ``"1"`` (amount == price).
* ``taxes`` entries carry an internal ``country`` key used only for matching;
  it is stripped before output.
* Credit memos use positive magnitudes under identical keys.
"""

from __future__ import annotations


def L(desc, item_type="SERVICE", uom="", qty="", unit="", total="",
      disc="", disc_pct="", rate="", amt="", taxes=None):
    return {
        "description": desc, "item_type": item_type, "uom": uom,
        "quantity": qty, "unit_price": unit, "total": total,
        "discount": disc, "discount_percentage": disc_pct,
        "tax_rate": rate, "tax_amount": amt, "taxes": taxes or [],
    }


def T(ttype, tname, rate, amt, country="", ):
    return {"tax_type": ttype, "tax_name": tname, "tax_rate": rate,
            "tax_amount": amt, "country": country}


def S(name, address="", vat="", country="", iban=""):
    return {"name": name, "address": address, "vat_id": vat,
            "iban": iban, "country": country}


def P(doc_kind="INVOICE", **kw):
    d = {"doc_kind": doc_kind, "doc_type_detail": "", "reason": "",
         "currency": "", "invoice_number": "", "invoice_date": "",
         "due_date": "", "payment_terms_text": "", "supplier": S(""),
         "buyer_text": "", "buyer_country": "", "po_number": "",
         "gross_total": "", "subtotal": "", "total_tax_amount": "",
         "discount_amount": "", "freight_charges": "",
         "insurance_charges": "", "extra_charges": "", "excise_duties": "",
         "taxes": [], "line_items": [],
         "flags": {"compound_tax": False, "tax_inclusive_prices": False,
                   "credit_applied": ""}}
    d.update(kw)
    return d


PRELIMS: dict[str, dict] = {

# ---------------------------------------------------------------- INV series
"INV-01": P(
    currency="EUR", invoice_number="852566", invoice_date="2026-02-02",
    due_date="2026-02-12", payment_terms_text="",
    supplier=S("", "", "", ""),
    buyer_text="Northwind Operations OÜ, Herrn Alex Kask, Lindenstrasse 15, 10134 Estonia",
    buyer_country="EE", gross_total="438.00", subtotal="438.00",
    total_tax_amount="0.00",
    taxes=[T("VAT", "MwSt", "0", "0.00", "")],
    line_items=[
        L("Projektmanagement Nachberechnung aus November", "SERVICE", "Std.", "4", "73.00", "292.00"),
        L("Projektmanagement Nachberechnung aus Dezember", "SERVICE", "Std.", "2", "73.00", "146.00"),
    ]),

"INV-02": P(
    currency="EUR", invoice_number="9972-907", invoice_date="2026-03-18",
    due_date="2026-04-01", payment_terms_text="",
    supplier=S("Meridian Logistics OÜ", "Avenida Central 22, 50106 Tartu linn, Estonia",
               "", "EE", "EE682389839721862212"),
    buyer_text="Northwind Technology OÜ, Market Road 15, Harjumaa, 10134 Tallinn, Estonia",
    buyer_country="EE", po_number="#2287",
    gross_total="608.23", subtotal="538.60", total_tax_amount="117.72",
    discount_amount="48.09",
    taxes=[T("VAT", "Käibemaks 24%", "24", "117.72", "EE")],
    line_items=[
        L("Led Bar FOS Luminus BAR", "SERVICE", "24 tundi", "9", "6.00", "54.00"),
        L("Meremiin ADJ Starburst", "SERVICE", "24 tundi", "1", "10.00", "10.00"),
        L("Pioneer CDJ-3000", "SERVICE", "24 tundi", "2", "45.00", "90.00"),
        L("Pioneer DJM-900 NXS2 mixer", "SERVICE", "24 tundi", "1", "45.00", "45.00"),
        L("DJ laud 2m x 0,5m h=1m (Kaasas must seelik)", "SERVICE", "1 päev", "1", "18.00", "18.00"),
        L("Aktiivkõlar Veritas 8000 komplekt", "SERVICE", "24 tundi", "1", "103.60", "103.60"),
        L("Linnasisene transport", "SERVICE", "Fikseeritud", "1", "50.00", "50.00"),
        L("Tehnik", "SERVICE", "3 tundi", "2", "84.00", "168.00"),
    ]),

"INV-03": P(
    currency="ZAR", invoice_number="INV-75162461", invoice_date="2025-05-25",
    due_date="2025-06-08", payment_terms_text="",
    supplier=S("Cloverdale Print Ltd", "Bahnhofstrasse 9", "3590736231", "ZA"),
    buyer_text="Northwind Services ZA (Pty) Ltd, 9446639440 - Maria Kask",
    buyer_country="ZA", po_number="PO-ZA218-81-057014",
    gross_total="8550.00", subtotal="7434.78", total_tax_amount="1115.22",
    line_items=[
        L("Contract Office cleaning - Contract", "SERVICE", "", "1.00", "7434.78", "7434.78",
          taxes=[T("VAT", "VAT", "15", "", "ZA")]),
    ]),

"INV-04": P(
    currency="ZAR", invoice_number="INV7097292303", invoice_date="2025-04-30",
    due_date="2025-05-31", payment_terms_text="",
    supplier=S("Larkspur Distribution Meridian Print",
               "Gartenweg 173, F04, Kiepersol House, Bahnhofstrasse 300, Darrenwood, Gauteng, 2195, South Africa",
               "", "ZA"),
    buyer_text="Northwind Services ZA (Pty) Ltd, Rua do Ouro 5, Unit 7, Block B, Gartenweg 60, Maitland, WESTERN CAPE CAPE TOWN 7405, SOUTH AFRICA",
    buyer_country="ZA",
    gross_total="6620.55", subtotal="17157.00", total_tax_amount="2573.55",
    discount_amount="13110.00",
    flags={"compound_tax": False, "tax_inclusive_prices": False,
           "credit_applied": "Less Amount Credited 13,110.00"},
    line_items=[
        L("Standard Criminal Verification", "SERVICE", "", "133.00", "129.00", "17157.00",
          taxes=[T("VAT", "VAT", "15", "", "ZA")]),
    ]),

"INV-06": P(
    currency="ZAR", invoice_number="8527907727", invoice_date="2025-04-07",
    due_date="", payment_terms_text="",
    supplier=S("Meridian Mobility Ltd", "Jalan Ampang 23087", "5471258869", "ZA"),
    buyer_text="Northwind Services ZA (Pty) Ltd",
    buyer_country="ZA",
    gross_total="1683.98", subtotal="1633.98", total_tax_amount="169.83",
    freight_charges="50.00",
    flags={"compound_tax": False, "tax_inclusive_prices": True, "credit_applied": ""},
    line_items=[
        L("Pnp Bananas Box 1.2kg", "GOODS", "EA", "1", "44.99", "44.99"),
        L("Pnp Banana Loaf 300g", "GOODS", "EA", "1", "24.99", "24.99"),
        L("Liqui-fruit Breakfast Punch Fruit Juice", "GOODS", "EA", "1", "25.00", "25.00"),
        L("Liqui-fruit Berry Blaze Juice 1l", "GOODS", "EA", "1", "25.00", "25.00"),
        L("Liqui-fruit Cranberry Cooler Juice 1l", "GOODS", "EA", "1", "25.00", "25.00"),
        L("Liqui-fruit Orange Fruit Juice 1l", "GOODS", "EA", "1", "25.00", "25.00"),
        L("Pnp Ripe & Ready Cling Peaches", "GOODS", "EA", "1", "56.99", "56.99"),
        L("Pnp Red Grapes 500g", "GOODS", "EA", "1", "39.99", "39.99"),
        L("Pnp White Grapes 500g", "GOODS", "EA", "1", "39.99", "39.99"),
        L("Nature Valley Crunchy Oats & Honey", "GOODS", "EA", "1", "69.99", "69.99"),
        L("Kellogg's Cocoa & Nutmix Granola", "GOODS", "EA", "1", "72.99", "72.99"),
        L("Kellogg's Cranberry & Linseed Granola", "GOODS", "EA", "1", "72.99", "72.99"),
        L("Pringles Salt & Vinegar Potato Chips", "GOODS", "EA", "1", "69.99", "69.99"),
        L("Pringles Sour Cream & Onion Potato Chips", "GOODS", "EA", "1", "69.99", "69.99"),
        L("Pnp Sliced Beef Biltong 300g", "GOODS", "EA", "1", "113.99", "113.99"),
        L("Pnp Roasted & Salted Economy Mixed Nuts", "GOODS", "EA", "1", "125.99", "125.99"),
        L("Pnp Bakehouse Blueberry Muffins 4 Pack", "GOODS", "EA", "1", "39.99", "39.99"),
        L("Pnp Full Cream Smooth Plain Yoghurt 1kg", "GOODS", "EA", "2", "38.99", "77.98"),
        L("Pnp Granola 750g", "GOODS", "EA", "1", "57.99", "57.99"),
        L("Pnp Berry Muesli Cereal 750g", "GOODS", "EA", "1", "74.99", "74.99"),
        L("Kellogg's Corn Flakes 750g", "GOODS", "EA", "1", "74.99", "74.99"),
        L("Clover Uht Full Cream Long Life", "GOODS", "EA", "2", "99.99", "199.98"),
        L("Little Bee Honey Squeeze Bottle 1kg", "GOODS", "EA", "1", "159.99", "159.99"),
        L("Pnp Bakehouse Blueberry Muffins 4 Pack (substitute)", "GOODS", "EA", "1", "39.99", "39.99"),
        L("Online Shopping Bag", "GOODS", "EA", "4", "1.30", "5.20"),
    ]),

"INV-07": P(
    currency="ZAR", invoice_number="INV7097292303", invoice_date="2025-04-30",
    due_date="2025-05-31", payment_terms_text="",
    supplier=S("Larkspur Distribution Meridian Print",
               "Gartenweg 173, F04, Kiepersol House, Bahnhofstrasse 300, Darrenwood, Gauteng, 2195, South Africa",
               "", "ZA"),
    buyer_text="Northwind Services ZA (Pty) Ltd, Rua do Ouro 5, Unit 7, Block B, Gartenweg 60, Maitland, WESTERN CAPE CAPE TOWN 7405, SOUTH AFRICA",
    buyer_country="ZA",
    gross_total="6620.55", subtotal="17157.00", total_tax_amount="2573.55",
    discount_amount="13110.00",
    flags={"compound_tax": False, "tax_inclusive_prices": False,
           "credit_applied": "Less Amount Credited 13,110.00"},
    line_items=[
        L("Standard Criminal Verification", "SERVICE", "", "133.00", "129.00", "17157.00",
          taxes=[T("VAT", "VAT", "15", "", "ZA")]),
    ]),

"INV-09": P(
    currency="EUR", invoice_number="11768395", invoice_date="2025-06-06",
    due_date="2025-06-27", payment_terms_text="",
    supplier=S("Cloverdale Trading", "10112, Gartenweg 13, Harju county, ESTONIA",
               "EE418070965", "EE"),
    buyer_text="Northwind Operations OÜ, Lindenstrasse 15, EE-10134 TALLINN",
    buyer_country="EE",
    gross_total="37767.32", subtotal="37767.32", total_tax_amount="0.00",
    line_items=[
        L("Import duties", "SERVICE", "", "1", "31889.09", "31889.09", rate="0"),
        L("Customs VAT", "SERVICE", "", "1", "5878.23", "5878.23", rate="0"),
    ]),

"INV-10": P(
    currency="EUR", invoice_number="18533", invoice_date="2026-03-25",
    due_date="2026-04-24", payment_terms_text="30 pv neto",
    supplier=S("Larkspur Print OÜ", "Jalan Ampang 60, Tallinn, Harju maakond, 10412",
               "EE755780626", "EE"),
    buyer_text="Northwind Operations OÜ, Rua do Ouro 15, Tallinn, Harju maakond, 10134",
    buyer_country="EE",
    gross_total="594.30", subtotal="479.27", total_tax_amount="115.03",
    taxes=[T("VAT", "Käibemaks 24%", "24", "115.03", "EE")],
    line_items=[
        L("17/03 Toitlustus", "SERVICE", "kord", "1", "479.28", "479.28"),
        L("Ümardus", "SERVICE", "", "1", "-0.01", "-0.01"),
    ]),

"INV-11": P(
    currency="EUR", invoice_number="18109293", invoice_date="2026-04-07",
    due_date="2026-04-28", payment_terms_text="",
    supplier=S("Meridian Media", "Gartenweg 12", "EE063536009", "EE"),
    buyer_text="Northwind OPERATIONS OÜ, Lindenstrasse 15, 10134 TALLINN, EESTI",
    buyer_country="EE",
    gross_total="83.21", subtotal="67.10", total_tax_amount="16.11",
    line_items=[
        L("408 AGREED PICKUP FEE", "SERVICE", "", "1", "5.00", "5.00",
          taxes=[T("VAT", "KM 24%", "24", "", "EE")]),
        L("551 TARNEKULUD", "SERVICE", "", "1", "53.40", "53.40",
          taxes=[T("VAT", "KM 24%", "24", "", "EE")]),
        L("805 AGREED DELIVERY FEE", "SERVICE", "", "1", "5.00", "5.00",
          taxes=[T("VAT", "KM 24%", "24", "", "EE")]),
        L("920 BAF 6,93% (16.03-29.03)", "SERVICE", "", "1", "3.70", "3.70",
          taxes=[T("VAT", "KM 24%", "24", "", "EE")]),
    ]),

"INV-13": P(
    currency="EUR", invoice_number="1410", invoice_date="2026-04-30",
    due_date="2026-05-30", payment_terms_text="30 päeva",
    supplier=S("Coverdale Supply OÜ", "High Street 64, Eesti", "EE085819779", "EE"),
    buyer_text="Northwind Services EE OÜ, Rua do Ouro 15, 10134 Kesklinna linnaosa, Tallinn, Harju maakond",
    buyer_country="EE",
    gross_total="152587.46", subtotal="127564.34", total_tax_amount="25023.12",
    taxes=[T("VAT", "KM 24%", "24", "25023.12", "EE"),
           T("VAT", "KM 0%", "0", "0.00", "EE")],
    line_items=[
        L("Parking fee EUROPARK", "SERVICE", "", "1", "63479.69", "63479.69"),
        L("Parking fee EUROPARK discount 20%", "SERVICE", "", "-1", "12695.94", "-12695.94"),
        L("Parking fee EUROPARK success fee", "SERVICE", "", "1", "3173.98", "3173.98"),
        L("Parking fee EUROPARK Ülemiste City H Garage, zone 335", "SERVICE", "", "1", "234.86", "234.86"),
        L("Parking fee EUROPARK KESKLINN", "SERVICE", "", "1", "13528.54", "13528.54"),
        L("Parking fee EUROPARK SÜDALINN", "SERVICE", "", "1", "8897.68", "8897.68"),
        L("Parking start fee EUROPARK", "SERVICE", "", "1", "6976.80", "6976.80"),
        L("Parking fee ÜHISTEENUSED OPEN AREA", "SERVICE", "", "1", "21380.06", "21380.06"),
        L("Parking fee ÜHISTEENUSED OPEN AREA discount 20%", "SERVICE", "", "-1", "4276.01", "-4276.01"),
        L("Parking fee ÜHISTEENUSED OPEN AREA success fee", "SERVICE", "", "1", "1069.00", "1069.00"),
        L("Parking fee ÜHISTEENUSED TARTU", "SERVICE", "", "1", "875.10", "875.10"),
        L("Parking start fee ÜHISTEENUSED", "SERVICE", "", "1", "1939.80", "1939.80"),
        L("Parking fee AVALIKUD TEENUSED", "SERVICE", "", "1", "1075.86", "1075.86"),
        L("Parking fee AVALIKUD TEENUSED discount 20%", "SERVICE", "", "-1", "215.17", "-215.17"),
        L("Parking fee AVALIKUD TEENUSED success fee", "SERVICE", "", "1", "53.79", "53.79"),
        L("Parking start fee AVALIKUD TEENUSED", "SERVICE", "", "1", "119.00", "119.00"),
        L("Parking fee Snabb", "SERVICE", "", "1", "20711.63", "20711.63"),
        L("Parking fee Snabb discount", "SERVICE", "", "-1", "2946.89", "-2946.89"),
        L("Parking fee Snabb success fee", "SERVICE", "", "1", "736.70", "736.70"),
        L("Parking fee Snabb with special price", "SERVICE", "", "1", "1952.18", "1952.18"),
        L("Parking fee Snabb special price discount", "SERVICE", "", "-1", "1108.87", "-1108.87"),
        L("Parking fee Snabb special price success fee", "SERVICE", "", "1", "160.85", "160.85"),
        L("Parking start fee Snabb", "SERVICE", "", "1", "2379.20", "2379.20"),
        L("Parking fee Mahtra 5 / Mahtra 27", "SERVICE", "", "1", "50.00", "50.00"),
        L("Parking fee Mahtra 5 / Mahtra 27 success fee", "SERVICE", "", "1", "12.50", "12.50"),
    ]),

"INV-14": P(
    currency="GBP", invoice_number="INV-1587", invoice_date="2026-05-01",
    due_date="2026-05-31", payment_terms_text="",
    supplier=S("Silverbrook Media Limited",
               "2nd Floor, Parnu mnt 117, Parnu mnt 26, London, Middlesex, N1 9RY, UNITED KINGDOM",
               "474927490", "GB"),
    buyer_text="Northwind Services UK Ltd, Rua do Ouro 175, Taper Studio, London, SE1 4GT",
    buyer_country="GB",
    gross_total="29253.72", subtotal="26042.68", total_tax_amount="3211.04",
    line_items=[
        L("Management Fee for June 2026", "SERVICE", "", "1.00", "14620.18", "14620.18",
          taxes=[T("VAT", "VAT 20%", "20", "", "GB")]),
        L("Business Rates for June 2026", "SERVICE", "", "1.00", "9987.50", "9987.50"),
        L("Utilities for June 2026", "SERVICE", "", "1.00", "1435.00", "1435.00",
          taxes=[T("VAT", "VAT 20%", "20", "", "GB")]),
    ]),

"INV-15": P(
    currency="GBP", invoice_number="INV-8935", invoice_date="2026-04-01",
    due_date="2026-04-30", payment_terms_text="",
    supplier=S("Silverbrook Media Limited",
               "2nd Floor, Parnu mnt 117, Parnu mnt 26, London, Middlesex, N1 9RY, UNITED KINGDOM",
               "474927490", "GB"),
    buyer_text="Northwind Services UK Ltd, Rua do Ouro 175, Taper Studio, London, SE1 4GT",
    buyer_country="GB",
    gross_total="29253.72", subtotal="26042.68", total_tax_amount="3211.04",
    line_items=[
        L("Management Fee for May 2026", "SERVICE", "", "1.00", "14620.18", "14620.18",
          taxes=[T("VAT", "VAT 20%", "20", "", "GB")]),
        L("Business Rates for May 2026", "SERVICE", "", "1.00", "9987.50", "9987.50"),
        L("Utilities for May 2026", "SERVICE", "", "1.00", "1435.00", "1435.00",
          taxes=[T("VAT", "VAT 20%", "20", "", "GB")]),
    ]),

"INV-16": P(
    currency="EUR", invoice_number="TLLIR72836045", invoice_date="2025-06-09",
    due_date="2025-07-07", payment_terms_text="",
    supplier=S("Speedwell Express Estonia AS", "Bahnhofstrasse 32, 11415 Tallinn, ESTONIA",
               "EE445462205", "EE"),
    buyer_text="Northwind Operations OÜ, VANA-LÕUNA TN 15, 10134 TALLINN, ESTONIA",
    buyer_country="EE",
    gross_total="26.47", subtotal="21.70", total_tax_amount="4.77",
    extra_charges="2.83",
    taxes=[T("VAT", "KM 22%", "22", "4.77", "EE")],
    line_items=[
        L("ECONOMY SELECT", "SERVICE", "", "1", "18.87", "26.47"),
    ]),

"INV-19": P(
    currency="GHS", invoice_number="", invoice_date="", due_date="",
    payment_terms_text="",
    supplier=S("Redwater Technologies", "Lindenstrasse 111 (Stadtbank)", "C9765403675", "GH"),
    buyer_text="Northwind HOLDINGS OÜ, High Street 10",
    buyer_country="EE",
    gross_total="8045.40", subtotal="6600.00", total_tax_amount="",
    flags={"compound_tax": True, "tax_inclusive_prices": False, "credit_applied": ""},
    taxes=[T("NHIL", "NHIL (2.5%)", "2.5", "165.00", "GH"),
           T("GETFund", "GETFund Levy (2.5%)", "2.5", "165.00", "GH"),
           T("COVID", "COVID-19 Levy (1%)", "1", "66.00", "GH"),
           T("VAT", "VAT (15%)", "15", "1049.40", "GH")],
    line_items=[
        L("Meal per head", "SERVICE", "", "60", "90.00", "5400.00"),
        L("Transportation and Set up", "SERVICE", "", "1", "1200.00", "1200.00"),
    ]),

"INV-20": P(
    currency="CHF", invoice_number="20423591", invoice_date="2026-02-16",
    due_date="2026-03-08", payment_terms_text="20 Days net",
    supplier=S("Elektra", "Avenida Central 60, 8005 Zürich", "", "CH"),
    buyer_text="Northwind CH sarl, Nina Costa, Market Road 26, 8008, Switzerland",
    buyer_country="CH",
    gross_total="12.10", subtotal="11.19", total_tax_amount="0.91",
    line_items=[
        L("King Tony Cap 1/2 Torx tip with T45x60mm hole (24 Months Warranty 2/16/2026 - 2/16/2028)",
          "GOODS", "", "1", "11.19", "11.19",
          taxes=[T("VAT", "VAT 8.10%", "8.10", "", "CH")]),
    ]),

"INV-21": P(
    currency="EUR", invoice_number="9894313366", invoice_date="2026-04-06",
    due_date="2026-05-06", payment_terms_text="",
    supplier=S("Oakhaven Partners LDA", "High Street 8, 2799-554 LINDA-A-VELHA",
               "PT059909082", "PT"),
    buyer_text="Northwind SUPPORT SERVICES PT, UNIPESSOAL LDA, Avenida Central 224, 1250-148 Lisboa",
    buyer_country="PT",
    gross_total="535.79", subtotal="868.51", total_tax_amount="100.19",
    line_items=[
        L("SICAL SUPER BAR Cafe Grao 6x1kg N1PT", "GOODS", "", "24.000", "34.69", "407.95",
          disc_pct="51.00", taxes=[T("IVA", "IVA 23%", "23", "", "PT")]),
        L("Desconto em Valor BEVERAGES SOLUTIONS", "GOODS", "", "1", "-8.30", "-8.30",
          taxes=[T("IVA", "IVA 23%", "23", "", "PT")]),
        L("Vireo Chocolate Quente 12(25x20g) N1", "GOODS", "", "1.000", "10.01", "10.01",
          taxes=[T("IVA", "IVA 23%", "23", "", "PT")]),
        L("NESCAFE Acucar Std 1x2.8kg PT", "GOODS", "", "1.000", "8.30", "8.30",
          taxes=[T("IVA", "IVA 23%", "23", "", "PT")]),
        L("AHMAD Inf Menta/HortLim 6(20x1,5g) N1PT", "GOODS", "", "3.000", "2.94", "8.82",
          taxes=[T("IVA", "IVA 23%", "23", "", "PT")]),
        L("AHMAD Inf Camomila 6(20x1.5g) N1PT", "GOODS", "", "3.000", "2.94", "8.82",
          taxes=[T("IVA", "IVA 23%", "23", "", "PT")]),
    ]),

"INV-25": P(
    currency="EUR", invoice_number="A98/712", invoice_date="2026-04-13",
    due_date="2026-05-13", payment_terms_text="Pagamento Credito",
    supplier=S("Fairmont Services LDA", "High Street 34, 1000-137 LISBOA",
               "029461956", "PT"),
    buyer_text="Support Services PT Unipessoal, Lda, ro 224, Lisboa",
    buyer_country="PT",
    gross_total="176.00", subtotal="176.00", total_tax_amount="32.91",
    flags={"compound_tax": False, "tax_inclusive_prices": True, "credit_applied": ""},
    line_items=[
        L("FOT./IMPRESSAO A4 CORES 1 ESTUD.", "GOODS", "UNI", "400.00", "0.32520", "160.00",
          taxes=[T("IVA", "IVA 23%", "23", "", "PT")]),
        L("FOLHA 80g BRANCO A4", "GOODS", "UNI", "400.00", "0.000", "0.00",
          taxes=[T("IVA", "IVA 23%", "23", "", "PT")]),
        L("FOLHA 120g BRANCO A4", "GOODS", "UNI", "200.00", "0.06504", "16.00",
          taxes=[T("IVA", "IVA 23%", "23", "", "PT")]),
    ]),

"INV-26": P(
    currency="MYR", invoice_number="", invoice_date="2025-02-08",
    due_date="", payment_terms_text="Instant Transfer",
    supplier=S("Cloverdale Partners Sdn Bhd",
               "Bahnhofstrasse 1, Lindenstrasse 1, 47810 JAYA, Malaysia", "", "MY"),
    buyer_text="Northwind MY SDN BHD (867063633189), Lindenstrasse 21, Mid Valley City, Lingkaran Syed Putra, 59200 Kuala Lumpur, Malaysia",
    buyer_country="MY",
    gross_total="873.53", subtotal="873.53", total_tax_amount="0.00",
    taxes=[T("SST", "SST 0%", "0", "0.00", "MY")],
    line_items=[
        L("WIPES", "GOODS", "", "2", "14.20", "28.40"),
        L("5X90S", "GOODS", "", "2", "10.95", "21.90"),
        L("PEEL FRESH MANGO 1L", "GOODS", "", "2", "6.90", "13.80"),
        L("NOI MIXED ROOT CHIPS 65G", "GOODS", "", "2", "3.60", "7.20"),
        L("POP SWEET N SALTY 120G", "GOODS", "", "4", "15.90", "63.60"),
        L("(+/-1KG)", "GOODS", "", "1", "7.20", "7.20"),
        L("CHINA SHINE GRAPE 500G", "GOODS", "", "2", "11.80", "23.60"),
        L("CHIPS SALT N 142G", "GOODS", "", "2", "15.50", "31.00"),
        L("TONG NUT MIX HONEY 140GM", "GOODS", "", "2", "17.00", "34.00"),
        L("150G", "GOODS", "", "2", "12.20", "24.40"),
        L("VIREO 2F SHARE BAG 10X17G", "GOODS", "", "2", "12.10", "24.20"),
        L("BAR 138G", "GOODS", "", "2", "15.20", "30.40"),
        L("CREAM 300G", "GOODS", "", "1", "5.95", "5.95"),
        L("CEO WHITE 500G", "GOODS", "", "1", "4.90", "4.90"),
        L("DAIRY THICK & 150G", "GOODS", "", "6", "9.50", "57.00"),
        L("CAFE OAT MILK 300G", "GOODS", "", "2", "28.50", "57.00"),
        L("GREEK FIT 160G", "GOODS", "", "2", "12.60", "25.20"),
        L("THINS CHIPS SOUR CREAM & 175G", "GOODS", "", "2", "15.90", "31.80"),
        L("", "GOODS", "", "2", "9.00", "18.00"),
        L("GLICO PRETZ SWEET CORN 31G", "GOODS", "", "4", "2.00", "8.00"),
        L("CAMPBELL'S INST WILD SOUP 3X16.8G", "GOODS", "", "6", "5.45", "32.70"),
        L("PREGO MAC 71G", "GOODS", "", "5", "4.85", "24.25"),
        L("LAY'S CHIPS 170G", "GOODS", "", "2", "14.60", "29.20"),
        L("120G", "GOODS", "", "1", "10.50", "10.50"),
        L("WHITE", "GOODS", "", "3", "21.90", "65.70"),
        L("HONEY TEA 1150G", "GOODS", "", "1", "44.85", "44.85"),
        L("ORG CHIA SEEDS 200G", "GOODS", "", "1", "19.90", "19.90"),
        L("3IN1 GREEN TEA", "GOODS", "", "2", "12.60", "25.20"),
        L("DRIED & 130G", "GOODS", "", "2", "6.60", "13.20"),
        L("(BUY 2 @RM68.80) L 15S", "GOODS", "", "1", "33.88", "33.88"),
        L("GREEK FIT PASSIONFRUIT 160G", "GOODS", "", "1", "12.60", "12.60"),
        L("GREEK FIT 160G", "GOODS", "", "1", "12.60", "12.60"),
        L("BAG", "GOODS", "", "10", "0.20", "2.00"),
        L("BAG", "GOODS", "", "4", "0.50", "2.00"),
    ]),

"INV-27": P(
    currency="KES", invoice_number="32917ALS55", invoice_date="2025-06-03",
    due_date="2025-07-03", payment_terms_text="",
    supplier=S("Oakhaven Supply Ltd", "Lindenstrasse 8, P.O Box 14108, Nairobi, Kenya, 00400 KEN",
               "P088353697W", "KE"),
    buyer_text="Northwind Support Kenya Ltd, Rua do Ouro 117, AZURE TOWERS, 10TH FLOOR, RIVERSIDE SQUARE RIVERSIDE DRIVE, 00600 Nairobi, Kenya",
    buyer_country="KE",
    gross_total="70654.30", subtotal="60908.88", total_tax_amount="9745.42",
    taxes=[T("VAT", "VAT @ 16%", "16", "9745.42", "KE")],
    line_items=[
        L("Handling Out (per CBM) - Handling Out of POS DEVICES (SUNMI V2PRO) on 19th May, 0.00686CBM * 40 units",
          "SERVICE", "", "0.2744", "500.00", "137.20"),
        L("Transport - Transport of POS devices (SUNMI V2PRO) on 4th April",
          "SERVICE", "", "1", "3000.00", "3000.00"),
        L("Transport - Transport of POS DEVICES (SUNMI V2PRO) on 19th May",
          "SERVICE", "", "1", "1500.00", "1500.00"),
        L("Storage charges - Storage charges for POS devices (SUNMI V2PRO) from 1st to 19th May, 0.00686 CBM * 311 units * 19days",
          "SERVICE", "", "40.53574", "30.00", "1216.07"),
        L("Storage charges - Storage charges for POS devices (SUNMI V2PRO) from 20th to 31st May, 0.00686 CBM * 271 units * 12days",
          "SERVICE", "", "22.30872", "30.00", "669.26"),
        L("Storage charges - Storage charges for Food delivery bag (insulated bag) from 1st to 31st May, 0.0297 CBM * 1788 units * 31 days",
          "SERVICE", "", "1646.2116", "30.00", "49386.35"),
        L("Stock Management fee - Monthly stock Management fee",
          "SERVICE", "", "1", "5000.00", "5000.00"),
    ]),

"INV-28": P(
    currency="DKK", invoice_number="3025139", invoice_date="2026-02-28",
    due_date="2026-03-30", payment_terms_text="",
    supplier=S("Silverbrook Print", "Rua do Ouro 40, 2605 Brondby", "DK74347584", "DK"),
    buyer_text="Northwind Services Dk Aps, Att.: Sofia Roth, Lindenstrasse 3, 2610 Rodovre, Danmark",
    buyer_country="DK",
    gross_total="4478.20", subtotal="3582.56", total_tax_amount="895.64",
    taxes=[T("VAT", "Moms 25%", "25", "895.64", "DK")],
    line_items=[
        L("Bølgepap", "SERVICE", "KG", "10", "0.521", "5.21"),
        L("Lithium-ion bat. Lowgrade", "SERVICE", "KG", "35", "32.427", "1134.95"),
        L("Træ, Klasse A2", "SERVICE", "KG", "100", "2.632", "263.20"),
        L("Liftbil, Farligt affald", "SERVICE", "STK", "1", "0.000", "0.00"),
        L("Transport 1. enhed liftbil", "SERVICE", "STK", "1", "513.00", "513.00"),
        L("Tømning 660L minicontainer", "SERVICE", "STK", "1", "172.00", "172.00"),
        L("Oparbejdning papir / pap", "SERVICE", "KG", "10", "0.69", "6.90"),
        L("Vermiculite, 100 L, salg", "SERVICE", "STK", "1", "355.186", "355.19"),
        L("Vejbenyttelsesafgift", "SERVICE", "STK", "1", "65.25", "65.25"),
        L("Miljøindberetning", "SERVICE", "STK", "1", "119.00", "119.00"),
        L("Fakturaadministration", "SERVICE", "STK", "1", "200.00", "200.00"),
        L("Leje minicont. 660 ltr. m/lås", "SERVICE", "STK", "1", "120.00", "120.00"),
        L("Leje minicont. 240 ltr.", "SERVICE", "STK", "3", "60.00", "180.00"),
        L("Leje - Plastfad, 120 ltr.", "SERVICE", "STK", "1", "156.86", "156.86"),
        L("Leje minicont. 660 ltr.", "SERVICE", "STK", "2", "112.00", "224.00"),
        L("Leje Plast stativer", "SERVICE", "STK", "1", "67.00", "67.00"),
    ]),

"INV-31": P(
    currency="USD", invoice_number="39015", invoice_date="2018-06-01",
    due_date="2018-06-01", payment_terms_text="",
    supplier=S("100 Airport KPG III, LLC.", "125 E Elm Street, Suite 400, Conshohocken, PA 19428",
               "", "US"),
    buyer_text="AmeriHealth Caritas, 200 Stevens Drive, Suite 100, Lester, PA 19113",
    buyer_country="US", po_number="16299",
    gross_total="17657.53", subtotal="17657.53", total_tax_amount="",
    line_items=[
        L("Electric 04/27/18-05/16/18", "SERVICE", "", "1", "17657.53", "17657.53"),
    ]),

"INV-32": P(
    currency="USD", invoice_number="72", invoice_date="2018-06-05",
    due_date="2018-06-19", payment_terms_text="NET 14",
    supplier=S("215B.E.A.R.S.", "4613 Conshohocken Avenue, Philadelphia, PA 19131", "", "US"),
    buyer_text="Amerihealthcaritas Transportation",
    buyer_country="US", po_number="30193",
    gross_total="750.00", subtotal="750.00", total_tax_amount="0.00",
    taxes=[T("TAX", "TAX 0%", "0", "0.00", "US")],
    line_items=[
        L("5/31/18 1-15 15 passenger van from Philly going to DC pick back up in DC coming back to Philly. 8:30am to 5:30pm 9hr",
          "SERVICE", "", "1", "750.00", "750.00"),
    ]),

"INV-33": P(
    currency="SGD", invoice_number="ADIPLINV/070/17", invoice_date="2017-06-08",
    due_date="", payment_terms_text="C.O.D",
    supplier=S("AD NOTIONS INT'L PTE. LTD.",
               "20 Sin Ming Lane, Midview City #08-61, Singapore 573968", "53057406", "SG"),
    buyer_text="Changi Airport Group (S) Pte Ltd, PO Box 168, Singapore Changi Airport, Singapore 918146",
    buyer_country="SG",
    gross_total="250.00", subtotal="250.00", total_tax_amount="",
    line_items=[
        L("PROJECT: Pillar Signage Panel For Shuttle Service At T2 Coach Bay (Lot No. 8) - Supply of 2mm thick clear poly-carbonate sheet with reverse black color base & install onto existing pillar with A3 size digital print Matt lamination onto panel surface (Day Work)",
          "SERVICE", "pc", "1", "250.00", "250.00"),
    ]),

"INV-34": P(
    currency="AUD", invoice_number="I220-127612", invoice_date="2015-06-20",
    due_date="2015-06-27", payment_terms_text="",
    supplier=S("Asian Pacific Serviced Offices Pty Ltd",
               "Level 3, 480 Collins Street, Melbourne VIC 3000", "11 068 012 653", "AU"),
    buyer_text="Mario Kalogiannis, Zycus Infotech Private Limited, Level 9, 440 Collins Street, Melbourne VIC 3000",
    buyer_country="AU",
    gross_total="572.00", subtotal="520.00", total_tax_amount="52.00",
    taxes=[T("GST", "GST", "10", "52.00", "AU")],
    line_items=[
        L("Licence Fees - Suite 313b 20/06/2015 - 19/07/2015 (Workstation)", "SERVICE", "", "1.00", "520.00", "520.00"),
    ]),

"INV-35": P(
    currency="USD", invoice_number="0248727220", invoice_date="2018-06-27",
    due_date="", payment_terms_text="within 30 days of the receipt of this invoice",
    supplier=S("Ciox Health", "P.O. Box 409875, Atlanta, GA 30384-9875", "58-2659941", "US"),
    buyer_text="QUALITY MANAGEMENT DEPT, AMERIHEALTH CARITAS LA, PO BOX 83580, BATON ROUGE, LA 70884-3580",
    buyer_country="US", po_number="1000020040",
    gross_total="30.25", subtotal="27.50", total_tax_amount="2.75",
    taxes=[T("Sales Tax", "Sales Tax", "", "2.75", "US")],
    line_items=[
        L("Basic Fee", "SERVICE", "", "1", "25.50", "25.50"),
        L("Retrieval Fee", "SERVICE", "", "1", "0.00", "0.00"),
        L("Per Page Copy (Paper) 1", "SERVICE", "", "13", "0.00", "0.00"),
        L("Electronic Data Archive Fee", "SERVICE", "", "1", "2.00", "2.00"),
    ]),

"INV-36": P(
    currency="USD", invoice_number="44273107", invoice_date="2018-06-18",
    due_date="2018-07-18", payment_terms_text="30 NET",
    supplier=S("Oracle America, Inc.", "500 Oracle Parkway, Redwood Shores, CA 94065",
               "94-2805249", "US"),
    buyer_text="AmeriHealth Caritas Services, Attention: Accounts Payable, 200 Stevens Drive, Philadelphia, PA 19113, United States",
    buyer_country="US", po_number="1000021496",
    gross_total="91580.50", subtotal="91580.50", total_tax_amount="",
    line_items=[
        L("Managed Cloud Services - Computer and Administration Services - Managed Cloud Services - Additional Services 18-JUL-2018 : 17-OCT-2018",
          "SERVICE", "", "1", "91580.50", "91580.50"),
    ]),

"INV-37": P(
    currency="USD", invoice_number="5568", invoice_date="2018-06-12",
    due_date="", payment_terms_text="",
    supplier=S("1120 VERMONT AVENUE ASSOCIATES, LLP", "", "", "US"),
    buyer_text="AmeriHealth, 200 Stevens Drive, Philadelphia, PA 19113",
    buyer_country="US", po_number="17816",
    gross_total="2487.73", subtotal="", total_tax_amount="",
    line_items=[
        L("Electric energy charges (Non-Residential-GT, Total KWH Billed 16,031)", "SERVICE", "", "1", "1570.37", "1570.37",
          taxes=[T("Tax", "Sales tax 0.0575 on utility bills", "5.75", "", "US")]),
        L("Electric demand charges (Maximum Demand 23.200)", "SERVICE", "", "1", "266.10", "266.10",
          taxes=[T("Tax", "Sales tax 0.0575 on utility bills", "5.75", "", "US")]),
        L("Emergency generator fuel usage (0 gallons)", "SERVICE", "", "1", "0.00", "0.00"),
        L("Cooling system condenser water usage (Standby 3.500 Ton)", "SERVICE", "", "1", "61.73", "61.73"),
        L("Cooling system condenser water usage (24 Hour 2.000 Ton)", "SERVICE", "", "1", "35.27", "35.27"),
        L("Cooling system condenser water usage (24 Hour 5.000 Ton)", "SERVICE", "", "1", "319.65", "319.65"),
        L("Building service fees", "SERVICE", "", "1", "122.00", "122.00",
          taxes=[T("Tax", "Sales tax 0.0575 on building services", "5.75", "", "US")]),
    ]),

# ------------------------------------------------------------------ DU/HLD
"DU-03": P(
    currency="USD", invoice_number="74", invoice_date="", due_date="2026-01-16",
    payment_terms_text="60 Days Net",
    supplier=S("Blueharbor Logistics & Services Singapore Pte. Ltd.", "Singapore", "M2-0029161-1", "SG"),
    buyer_text="Cadence PTE. LTD., Rua do Ouro 18, 539775, Singapore",
    buyer_country="SG",
    gross_total="1040.06", subtotal="1040.06", total_tax_amount="0.00",
    taxes=[T("GST", "0% GST on sales", "0", "0.00", "SG")],
    line_items=[
        L("International Freight", "FREIGHT", "KG", "567.000", "1.28", "725.76"),
        L("Origin Terminal Handling", "SERVICE", "KG", "567.000", "0.10", "56.70"),
        L("Documentation Fee", "SERVICE", "EA", "1.000", "45.00", "45.00"),
        L("Delivery", "SERVICE", "KG", "567.000", "0.04", "22.68"),
        L("Pick-up", "SERVICE", "KG", "567.000", "0.18", "102.06"),
        L("Customs - Export", "SERVICE", "EA", "1.000", "7.50", "7.50"),
        L("Origin Documentation", "SERVICE", "EA", "1.000", "15.00", "15.00"),
        L("Customs - Import", "SERVICE", "EA", "1.000", "15.00", "15.00"),
        L("Carrier Manifest Filing", "SERVICE", "EA", "1.000", "5.00", "5.00"),
        L("Terminal Handling", "SERVICE", "KG", "567.000", "0.08", "45.36"),
    ]),

"DU-05": P(
    currency="SGD", invoice_number="7363916", invoice_date="2026-06-30",
    due_date="2026-09-28", payment_terms_text="90 days net",
    supplier=S("Vantek Asia Pte Ltd.", "High Street 7, #03-66/67/68/69, Singapore 737664",
               "207490313H", "SG"),
    buyer_text="Cadence Pte. Ltd - Standard, Jalan Ampang 08, Singapore 539775",
    buyer_country="SG",
    gross_total="771.66", subtotal="771.66", total_tax_amount="",
    line_items=[
        L("4108044 F:WSA_89424080_HSS (N) H2940 DKC (Cust. mat-no: 89424080, Indonesia, 3926.9000, Delivery note: 8358769)",
          "GOODS", "PC", "100", "7.7166", "771.66"),
    ]),

"DU-06": P(
    currency="EUR", invoice_number="FN 05/80906935", invoice_date="2026-06-15",
    due_date="2026-07-16", payment_terms_text="",
    supplier=S("Blackpine Supply S.A", "Qta da Mendanha, OTAPARK, Fração AN, 2580-490 Carregado",
               "785255159", "PT"),
    buyer_text="Northwind SUPPORT SERVICES PT, UNIPESSOAL, Bahnhofstrasse 224, 1250-148 LISBOA",
    buyer_country="PT",
    gross_total="153.58", subtotal="138.20", total_tax_amount="",
    taxes=[T("IVA", "IVA 23%", "23", "9.59", "PT"),
           T("IVA", "IVA 6%", "6", "5.79", "PT")],
    line_items=[
        L("Empanadilha Atum Cozida (50u)", "GOODS", "", "1", "41.68", "41.68"),
        L("Pao Burger Brioch LeBrio14px4u", "GOODS", "", "1", "28.43", "28.43"),
        L("Chapata Cristallino 28px2u", "GOODS", "", "1", "25.94", "25.94"),
        L("Pao Maestra Classica 7u", "GOODS", "", "2", "13.43", "26.86"),
        L("Pao Maestra Cereais 7u", "GOODS", "", "1", "15.29", "15.29"),
    ]),

"DU-10": P(
    doc_kind="CREDIT_MEMO", currency="GBP", invoice_number="5900366703",
    invoice_date="2026-04-15", due_date="", payment_terms_text="Within 30 days of invoice date",
    supplier=S("Blackpine Consulting Limited",
               "Parnu mnt 50, Bahnhofstrasse 65, Chippenham, SN14 0GF", "GB447324473", "GB"),
    buyer_text="Northwind Services UK Limited, Jalan Ampang 157, Jalan Ampang 175, London SE1 4GT, UNITED KINGDOM",
    buyer_country="GB",
    gross_total="5076.17", subtotal="4230.14", total_tax_amount="846.03",
    line_items=[
        L("4582314 Logitech Tap Scheduler Touch Controller (952-000091)", "GOODS", "", "6", "457.24", "2743.44",
          taxes=[T("VAT", "VAT 20%", "20", "", "GB")]),
        L("4541892 Logitech Tap Touch Controller Cat5e Kit (939-001950)", "GOODS", "", "2", "743.35", "1486.70",
          taxes=[T("VAT", "VAT 20%", "20", "", "GB")]),
    ]),

"DU-11": P(
    doc_kind="CREDIT_MEMO", currency="EUR", invoice_number="6265-K",
    invoice_date="2025-03-16", due_date="2025-03-16", payment_terms_text="",
    supplier=S("Tavolo OÜ", "", "", "EE"),
    buyer_text="Northwind Operations OÜ, Rua do Ouro 15, 10134 Kesklinna, Tallinn, Harju maakond, Eesti",
    buyer_country="EE",
    gross_total="400.00", subtotal="327.87", total_tax_amount="72.13",
    line_items=[
        L("Toitlustamine Tavolo 11.03.25", "SERVICE", "tk", "1", "327.868852", "327.87",
          taxes=[T("VAT", "KM 22%", "22", "", "EE")]),
    ]),

"HLD-01": P(
    currency="THB", invoice_number="SI6675/02/467", invoice_date="2026-05-05",
    due_date="", payment_terms_text="",
    supplier=S("บริษัท ซิงค์ ครีเอชั่น จำกัด", "Bangkok", "0105556100879", "TH"),
    buyer_text="Northwind SUPPORT SERVICES (THAILAND) LIMITED",
    buyer_country="TH",
    gross_total="8161.92", subtotal="7200.00", total_tax_amount="549.36",
    extra_charges="648.00",
    taxes=[T("VAT", "Vat 7%", "7", "549.36", "TH"),
           T("WHT", "Withholding tax 3%", "3", "-235.44", "TH")],
    line_items=[
        L("Staff 2 Units X 6 Days (Staff Impact May 2026)", "SERVICE", "", "12", "600.00", "7200.00"),
    ]),

"HLD-03": P(
    currency="EUR", invoice_number="", invoice_date="2025-12-02",
    due_date="2026-01-01", payment_terms_text="",
    supplier=S("", "", "", "PT"),
    buyer_text="Blackpine Unipessoal Lda, Kadaka tee 224, 1250-148 Lisboa",
    buyer_country="PT",
    gross_total="67.25", subtotal="123.36", total_tax_amount="7.74",
    taxes=[T("IVA", "IVA 13%", "13", "7.74", "PT")],
    line_items=[
        L("TRINCA ALE T22 6X1500 CXE NTT (EAN: 5601012004984)", "GOODS", "CX", "1", "123.36", "123.36",
          disc_pct="51.76"),
    ]),

"HLD-05": P(
    currency="EUR", invoice_number="7769922058", invoice_date="2026-06-12",
    due_date="", payment_terms_text="",
    supplier=S("", "", "PT668715865", "PT"),
    buyer_text="Northwind Support Services PT Unipessoal, Lda, Parnu mnt 224, Portugal",
    buyer_country="PT",
    gross_total="1037.94", subtotal="1796.54", total_tax_amount="176.87",
    discount_amount="1049.60", excise_duties="88.33",
    taxes=[T("IVA", "IVA 23%", "23", "157.05", "PT"),
           T("IVA", "IVA 13%", "13", "19.82", "PT")],
    line_items=[
        L("SAGRES Branca Gfa Tab 6x1L PT", "GOODS", "TAB", "40", "14.76", "590.40"),
        L("HEINEKEN Barril OW 5L PT", "GOODS", "BAR", "6", "24.53", "147.18"),
        L("SAGRES Branca Gfa Tab 4(6x25cl) PT201a", "GOODS", "TAB", "1", "24.96", "24.96"),
        L("SAGRES Branca Gfa Cxa 20x25cl PT 201a", "GOODS", "CRT", "9", "20.80", "187.20"),
        L("CASTELLO Original Gfa SW 4(6x25cl) 404a", "GOODS", "PAK", "7", "20.40", "142.80"),
        L("LUSO PET SW 6x1,5L SDR", "GOODS", "PAK", "27", "6.72", "181.44"),
        L("Depósito SDR", "GOODS", "UND", "162", "0.10", "16.20"),
        L("LUSO PET SW 4(6x50cl) SDR", "GOODS", "PAK", "4", "14.64", "58.56"),
        L("Depósito SDR", "GOODS", "UND", "96", "0.10", "9.60"),
        L("DECVAKUGZK Gfa Cxa 4(6x33cl) ES", "GOODS", "CRT", "1", "48.00", "48.00"),
        L("HEINEKEN Gfa Cxa 18x25cl PT", "GOODS", "CRT", "4", "18.72", "74.88"),
        L("HEINEKEN Gfa Tab 4(6x25cl) PT", "GOODS", "TAB", "7", "24.96", "174.72"),
        L("SAGRES Branca Gfa SW 2(10x25cl) PT201a", "GOODS", "PAK", "8", "20.80", "166.40"),
    ]),

"HLD-08": P(
    currency="ZAR", invoice_number="162547", invoice_date="2026-05-19",
    due_date="", payment_terms_text="",
    supplier=S("Cloverdale Partners CC", "PO Box 2505, Market Road 73, Rua do Ouro 138, 4300",
               "2731114415", "ZA"),
    buyer_text="Meridian Technologies, A Division of Meridian Print LTD, P.O.Box 13385, Jacobs 4026",
    buyer_country="ZA",
    gross_total="148941.47", subtotal="129514.32", total_tax_amount="19427.15",
    line_items=[
        L("Hall's Smooth Fruit Punch 1lt M 337521 (WT037912, CG)", "GOODS", "", "468", "276.74", "129514.32",
          taxes=[T("VAT", "VAT 15%", "15", "", "ZA")]),
    ]),

"HLD-10": P(
    currency="EUR", invoice_number="", invoice_date="2026-05-07",
    due_date="2026-06-04", payment_terms_text="",
    supplier=S("Speedwell Express Estonia AS", "High Street 36, 75310 Harju maakond, Eesti", "", "EE"),
    buyer_text="Northwind Operations OÜ",
    buyer_country="EE",
    gross_total="254.52", subtotal="223.98", total_tax_amount="30.54",
    extra_charges="66.36",
    taxes=[T("VAT", "KM 24%", "24", "30.54", "EE"),
           T("VAT", "KM 0%", "0", "0.00", "EE")],
    line_items=[
        L("Courier transport - 1 shipment WAW-OSL (4.00 kg)", "SERVICE", "", "1", "65.26", "96.73"),
        L("Courier transport - 3 shipments, nondoc (38.00 kg)", "SERVICE", "", "1", "92.36", "157.78"),
    ]),

# ------------------------------------------------------------- not payables
"DU-02": P(doc_kind="NOT_PAYABLE", doc_type_detail="CUSTOMS_DOCUMENT",
           reason="Customs consolidated/detailed valuation invoices (Novatek BE to TR); "
                  "no payment obligation, terms, or single amount owed is stated — not a bookable payable."),
"DU-05s": P(doc_kind="NOT_PAYABLE", doc_type_detail="DELIVERY_NOTES",
            reason="Vantek delivery notes, DHL shipping labels and a shipment receipt; "
                   "no commercial invoice or amount owed."),
"DU-08": P(doc_kind="NOT_PAYABLE", doc_type_detail="REMINDER",
           reason="Mahnung (dunning letter) for invoice VRB700A6126940; it references a canceled "
                  "invoice (44.84 credit) and an invoice not present in the file. A reminder is not itself a payable."),
"DU-09": P(doc_kind="NOT_PAYABLE", doc_type_detail="INTERNAL_FORM",
           reason="Internal donation/sponsorship approval form plus forwarding email; "
                  "no supplier invoice or amount owed."),
"INV-23": P(doc_kind="NOT_PAYABLE", doc_type_detail="ESTIMATE",
            reason="Estimate EST-259684 (proforma) requiring a GHC 13,000 deposit to proceed; "
                   "estimates are not bookable payables. The ICUMS pages are supporting customs calculations."),
}
