# POS Khmer Bilingual Receipt (ABJ) — `pos_receipt_khmer`

Odoo 18.0 module (LGPL-3, author ABJ SkinCare) that turns the Point of Sale customer receipt and the
cash in/out slip into a Khmer / English document designed for an 80 mm thermal printer and for the
browser's print dialog.

## What it does

- **Letterhead**: the print logo beside the Khmer shop name, the Latin name and the Khmer and English
  address, then the phone (`031 266 3333`), web and e-mail, and the Tax ID with a bilingual label.
- **Title band**: `វិក្កយបត្រ / INVOICE` (default) or `បង្កាន់ដៃលក់ / SALES RECEIPT`, followed by the
  number, the date in Phnom Penh time (`dd/MM/yyyy HH:mm`, whatever the zone of the cashier's
  device), the cashier and the customer.
- **Items**: name and line price, then `2 × $6.00` and a bilingual discount line.
- **Totals**: one large USD total with the **exact KHR total** under it (1 riel precision, as
  Notification 4908 requires), the exchange-rate line, then the payments
  (`សាច់ប្រាក់ / Cash`, `ABA KHQR` + transaction ID, `គណនីអតិថិជន / Customer Account`), and the
  change in USD with `ឬ / or` the riel amount rounded to 100 riel for cash, plus a
  `ការបង្គត់ / Rounding` row when the rounding changes the amount.
- **Unpaid pre-receipts** (a draft order printed before payment, e.g. by `cst_pos_pre_receipt`):
  dashed `មិនទាន់បង់ប្រាក់ / NOT PAID — PRE-RECEIPT` frame, `Order No.`, `AMOUNT DUE`,
  "please pay at the counter" and a NOT PAID stamp. **A change row is never printed on an unpaid
  order or with a negative amount** (the `CHANGE $ -6.00` bug of older 18.0 builds).
- **Loyalty** points earned / spent / balance in a small bilingual box (paid receipts only; with more
  than one loyalty program each block is headed by the program's points name).
- **Cash in/out slip**: `ដាក់ប្រាក់ចូល CASH IN` / `ដកប្រាក់ចេញ CASH OUT` band, amount, reason,
  cashier and date.
- Ships the **Kantumruy Pro** Khmer font (subset, SIL Open Font License 1.1, see
  `static/fonts/OFL.txt`), so Khmer shapes correctly on every device and in the printed image, and
  waits for it before printing.

Only receipts change: the product-screen order list, the ticket screen and the customer display use
the shared `Orderline` component, which this module does not modify (all receipt markup goes into
`OrderReceipt`'s own `Orderline` slot and all CSS is scoped to `.pos-receipt.o_kh_receipt`).

## Settings

**Settings > Companies > (your company) > tab "POS Receipt (Khmer)"**

| Field | Default | Effect |
|---|---|---|
| Khmer trade name (receipt) | empty | Khmer shop name in the header (hidden when empty). ABJ placeholder: `អេប៊ីជេ ស្គីនឃែរ` until the owner confirms the registered Khmer name. |
| Receipt address (Khmer) | empty → city + province | e.g. `ក្រុងតាខ្មៅ ខេត្តកណ្ដាល` |
| Receipt address (English) | empty (hidden) | e.g. `Ta Khmau, Kandal` |
| Receipt title | `វិក្កយបត្រ / INVOICE` | or `បង្កាន់ដៃលក់ / SALES RECEIPT`. Also switches the number label (`Invoice No.` / `Receipt No.`). |
| Tax ID label | `លេខអត្តសញ្ញាណកម្ម / TIN` | `Do not print`, `TIN`, or `លេខអត្តសញ្ញាណកម្ម អតប / VATTIN` (only once the accountant confirms the VAT registration). The number printed is the company **Tax ID** (`vat`). |
| Receipt logo (thermal) | empty → company logo | See below. |

**Point of Sale > Configuration > Payment Methods > (method) > Receipt label**: the name printed on
the receipt, e.g. `ABA KHQR` for "ABA QR Pos". Empty: cash methods print `សាច់ប្រាក់ / Cash`,
customer-account methods `គណនីអតិថិជន / Customer Account`, others their own name. The label can be
changed while a POS session is open (the POS picks it up after a reload).

**Exchange rate**: there is no new setting. The receipt uses the company's accounting rate
`l10n_kh_exchange_rate` (module `l10n_kh_tax`) when it is installed and greater than 0 (ABJ: 4,100)
and the POS sells in the company currency; otherwise the current rate of the KHR currency
(Accounting > Currencies; KHR must be active), converted to the POS currency. With neither, or when
the POS itself sells in riel (KHR), the KHR total, rate line and riel change are not printed. The rate
line names the POS currency (`1 USD = 4,100 ៛`).

After changing settings, reload the POS (or close and reopen the session) so it loads the new values.

## How to upload the print logo

Thermal printers print 1-bit images (black or white dots). A colour or grey logo is dithered into
speckles and thin lines break up, so upload a dedicated print logo:

1. Make a **black-and-white PNG (1-bit), exactly 200 px wide**, any height (ABJ: 200 × 123). Lines
   must be at least 2 px thick; drop fine taglines. `static/img/abj_logo_print.png` in this module
   is the ABJ print logo and can be used as is.
2. Settings > Companies > your company > tab **POS Receipt (Khmer)** > **Receipt logo (thermal)** >
   upload the file > Save.
3. Reload the POS. The receipt prints it 1:1 (200 dots) beside the shop name.

Without a print logo the receipt uses the normal company logo at 44 % width with a hard
black/white threshold; a light or pastel logo (lighter than about 40 % grey) can disappear.

## Questions for the accountant (before go-live)

1. **VATTIN format.** The company Tax ID on file is `121200209`. A Cambodian VAT TIN usually looks
   like `K008-…` / `L001-…` (letter + 3 digits + 9 digits). Which number must be printed, and is the
   company VAT-registered? Until confirmed the receipt prints the neutral `លេខអត្តសញ្ញាណកម្ម / TIN`
   label; switch to `VATTIN` only after confirmation.
2. **Document title.** Must the POS document be called `វិក្កយបត្រ / INVOICE` (default) or
   `បង្កាន់ដៃលក់ / SALES RECEIPT`? Does the GDT require "tax invoice" (`វិក្កយបត្រអាករ`) wording,
   the customer's TIN, or a sequential invoice number different from the POS order reference?
3. **VAT registration and VAT lines.** ABJ products currently have no taxes, so no VAT line is
   printed. If the company is VAT-registered, taxes must be configured on the products; Odoo then
   prints its tax summary above the total (styled by this module).
4. **Exchange rate.** The receipt prints the `l10n_kh_exchange_rate` (4,100) rather than the NBC rate
   loaded in Odoo (4,055.06). Confirm that this is the rate to print and keep it up to date.
5. **Wording.** Strings marked "U" in the design spec (e.g. `គណនីអតិថិជន`, `លេខប្រតិបត្តិការ`,
   `ដាក់ប្រាក់ចូល`, `ដកប្រាក់ចេញ`, `មូលហេតុ`, the "not an invoice" line and the loyalty labels) and the
   placeholder Khmer shop name need a native-speaker review. Added after the spec, also to review:
   `ឥតគិតថ្លៃ / Free` (a 100 % discounted line), `លេខបញ្ជាទិញ / SO` (pos_sale sale-order reference),
   `ប្រាក់ត្រូវបង់ / To pay` (cash-rounded amount, same words as AMOUNT DUE) and
   `សម្គាល់ / Note` as the heading of the order's general note.

## Technical overview

| Part | File |
|---|---|
| Company settings, `_load_pos_data_fields` (+ `l10n_kh_exchange_rate` only if that field exists) | `models/res_company.py` |
| Load the KHR currency into the POS | `models/res_currency.py` |
| Payment-method receipt label (+ loaded into the POS, editable with an open session) | `models/pos_payment_method.py` |
| Views (company page "POS Receipt (Khmer)", payment-method field) | `views/*.xml` |
| Formatting helpers (riel, phone, web, dates in Asia/Phnom_Penh) | `static/src/js/kh_format.js` |
| Data patches: `PosStore.getReceiptHeaderData`, `PosOrder.export_for_printing`, `OrderReceipt` helpers, `CashMoveReceipt.khMove` | `static/src/js/receipt_kh.js` |
| Font readiness (`PosStore._loadFonts`, `PrinterService.print` await the Khmer font) | `static/src/js/font_ready.js` |
| Template extensions (`ReceiptHeader`, `OrderReceipt`, `CashMoveReceipt`; extension mode, attribute changes and insertions only) | `static/src/xml/receipt_kh.xml` |
| Receipt stylesheet (em-based: 512 px / 27 px raster and 266 px / 14 px web print) | `static/src/scss/receipt_kh.scss` |
| Font + licence, sample print logo | `static/fonts/`, `static/img/` |
| Tests: POS data loaders, logo flag, label editing, receipt tour | `tests/`, `static/tests/tours/` |

Run the tests with
`odoo-bin -d <db> -i pos_receipt_khmer --test-tags /pos_receipt_khmer --stop-after-init`.

## Implementation notes

The module follows the design spec (`design/final/SPEC.md`). Deviations, each because the spec did
not work as written on real Odoo 18.0:

1. **SCSS `max()`** — the spec's CSS is "valid SCSS", but Odoo compiles SCSS with libsass, which
   evaluates `max(2px, 0.115em)` itself and fails with "Incompatible units: 'px' and 'em'". One
   failing file breaks the whole POS stylesheet. The six `max(2px, …em)` values are written as Sass
   string interpolations (`#{'max(2px, 0.115em)'}`); the compiled CSS is identical to the spec's
   (checked rule by rule).
2. **`khLine()` identity lookup** — the spec's `props.data.orderlines.indexOf(line)` never matched:
   the slot's `line` reaches `OrderReceipt` through `OrderWidget`'s props, i.e. as a *different OWL
   reactive proxy* of the same object, so every line fell back to the core "1.00 x $ 6.00 / Units"
   row (spec risk 4). The lookup now compares raw objects (`toRaw`).
3. **`show_change` normalised by the module** — older 18.0 builds have no `show_change` /
   `order_change` in `export_for_printing` (Dec 2024) or show it on unpaid drafts (before Odoo commit
   ebfc6bf1, 2025-09-29: the live server's `CHANGE $ -6.00`). The patch computes `order_change`
   itself when missing (`get_change()`) and sets
   `show_change = (core value ?? true) && finalized && change > 0 && paymentlines.length`, in its own
   guarded step before the rest of the Khmer data. The template's `div.receipt-change` also gets
   `t-if="props.data.show_change"` (attribute change on the class anchor), because the Dec 2024
   template used `'order_change' in taxTotals` instead.
4. **Receipt number without "Order "** — this 18.0 build stores `pos_reference = "Order 00030-001-0002"`
   once the order is synced (the server copies the frontend `name`), the live build does not. The
   meta row prints `kh.number` (the reference without a leading `Order ` or its translation) instead
   of `props.data.name`; `props.data.name` itself is unchanged.
5. **Line discount condition from display data** — `kh.lines` is built from the exported orderlines
   (`d.discount`, same condition as the core discount `<li>`) instead of indexing
   `getSortedOrderlines()` in parallel, so it can never shift if another module filters the lines.
6. **Negative amounts in item lines** — core formats a refund line price as `$ -6.00`; the receipt-only
   orderline strings are normalised to `-$6.00` (spec §8 USD format), not just stripped of the NBSP.
7. **Payment-method label editable with an open session** — core forbids writing any payment-method
   field except `sequence` while a session is open; `kh_receipt_label` is whitelisted
   (`_is_write_forbidden`) because it is purely cosmetic (needed to configure "ABA QR Pos" on a
   running shop).
8. **Defensive data code** — the JS patches are wrapped so an unexpected error logs a console error
   and prints the core receipt instead of blocking printing; `_load_pos_data_fields` overrides do not
   turn an "all fields" (`[]`) answer into a restricted list; the payment-line label mapping is only
   applied when the core payment lines align with `payment_ids`; the font wait is capped at 4 s.
9. **Font readiness** — the spec's patch is applied as written (`PosStore._loadFonts` and
   `PrinterService.print` await `document.fonts.load()` for weights 500 and 700), with the
   4-second cap above.
10. **Tour assets** — the receipt tour lives in `static/tests/tours/` and is added to
    `web.assets_tests` (not to the POS bundle).
11. **18.0 build compatibility** — an xpath that matches nothing throws and no receipt renders at
    all, so every anchor was checked with Odoo's own `template_inheritance.js` against the 9
    distinct core `OrderReceipt` versions of 18.0 (2024-09-25 release to 2026-10), the 4
    `ReceiptHeader` versions, `CashMoveReceipt` and both `pos_loyalty` versions: all apply.
    - The total is anchored as the first `div.pos-receipt-amount` (every build) and gets the
      `receipt-total` class there, because core only added that class on 2024-11-29 (8fb7e5fd).
    - The total, rounding and to-pay amounts come from build-independent helpers (`khTotal()`,
      `khRounding()`): `taxTotals.order_sign` only exists since 2024-12-16 (186bb06b) and `taxTotals`
      since 2024-11-29; before that `amount_total` / `rounding_applied` are used. A non-numeric
      total prints no KHR line (never `NaN ៛`).
    - Anchors that exist only on some builds (`receipt-rounding`, `receipt-to-pay`, the tax-summary
      amount expressions) are written `<anchor> | //span[hasclass('kh-xp-sink')]`: the union resolves
      to the real node when it exists and otherwise to a never-rendered sink node the module appends
      inside `<t t-if="false">`.
    - **Fully supported from the 2024-11-29 builds on** (the live server: point_of_sale 18.0.1.0.2,
      2025-03 or later). On the first two months of 18.0 (2024-09-25 to 2024-11-29) the receipt still
      renders with all Khmer content, but core's TOTAL / CHANGE / Discounts / Rounding / To Pay labels
      are literal English text there, and the tax-summary and cash-rounding amounts keep core's
      `$ 6.00` format.
12. **One USD format on every amount** — the total, payments, change, discounts, cash rounding,
    "To pay" and tax-summary amounts all print as `$6.00` / `-$15.72` (spec §8), so a refund never
    mixes `-$15.72` with core's `$ -15.70`. "To Pay" gets a bilingual label; core's English text node
    cannot be selected, so the CSS grid places it in a 0-high, clipped row.
13. **Fallback without Khmer data** — if `_khExportForPrinting` throws, `res.kh` and
    `headerData.kh` are removed and the root gets no `o_kh_receipt` class (it is set with
    `t-att-class` from the data), so no receipt CSS applies and the plain core receipt prints with its
    number, date and loyalty rows.
14. **KHR change rounding** — the cash riel line is rounded to 100 from the exact riel amount
    (`halfUp(exact / 100) × 100`), so the `Rounding` row always adds up, also with a fractional rate
    (4,055.06 × $0.90 = 3,650 → 3,700, `+50`). A change that rounds to 0 riel (e.g. $0.01) prints no
    riel line and no rounding row.
15. **Loyalty box** — the spec's fixed labels (`Points earned / spent / balance`), points grouped
    like the KHR figures (`100,365`) and signed (`+120`, `-5`, a negative gain prints `-5`); the value
    never wraps. The box is not printed on an unpaid pre-receipt (points are only earned or spent
    when the order is paid, and the balance would not add up).
16. **Core blocks restyled** — the order's general note (OrderWidget) is styled like the line notes
    with a `សម្គាល់ / Note` heading (CSS on the receipt only; the shared component is not modified);
    a 100 % discounted line prints `ឥតគិតថ្លៃ / Free` instead of core's English `Free`; pos_sale's
    sale-order reference gets a `លេខបញ្ជាទិញ / SO` prefix and its down-payment table prints in body
    weight with `$1,800.00` amounts.
17. **Quantities** keep the locale they were formatted in: trailing zeros are trimmed after the
    locale's decimal point (`1,000.00` → `1,000`, `1.000,00` → `1.000`).
18. **Font subset** — the bundled woff2 contains every code point of Kantumruy Pro 1.002 (363:
    ASCII, all of Latin-1 Supplement, Œ œ ı, punctuation, ™, arrows, combining accents, Khmer),
    74 KB. The font has no Latin Extended-A/B (e.g. Vietnamese ă đ ư): such letters fall back to the
    device's sans-serif.

Known limits (from the spec's risk list, still true):

- **Core tours that assert core's amount format fail with the module installed** (expected, the spec's
  `-$15.72` format is deliberate): the 7 `point_of_sale` `TestPosCashRounding` tours
  (`test_cash_rounding_{down,halfup,up}_add_invoice_line_*`) and `TestUi.test_refund_backend_duplicate`
  look for `.receipt-total:contains("-15.72")` / `("-10.00")`, which `-$15.72` does not contain. Every
  other `point_of_sale`, `pos_hr`, `pos_loyalty`, `pos_sale` and `pos_discount` UI tour passes. The core
  `Served by` line stays in the DOM as a 1 px, ink-free strip so pos_hr's
  `.pos-receipt-contact .cashier:contains(Served by)` check still sees it.
- Core blocks the module does not translate keep Odoo's own words: the tax summary (`Untaxed
  Amount`, the tax group names, `on`; not used by ABJ, which has no taxes), pos_sale's `(tax incl.)`,
  pos_loyalty's coupon-code block and the terminal slips.
- Refunds keep the paid title and print negative amounts (spec risk 9); a `សងប្រាក់វិញ / REFUND`
  title with the original order's number is a possible v2.

- CSS hides every core `.pos-receipt-contact` child except the config header. If a module that
  injects inside `.pos-receipt-contact` is installed later (e.g. `l10n_es_pos`, `l10n_jo_edi_pos`),
  add an exception.
- The cash slip direction compares the popup's translated type with `_t("in")`.
- Other `ReceiptHeader` users that are not `OrderReceipt` or `CashMoveReceipt` (pos_restaurant tip
  receipt, pos_self_order — not installed) show the extra Khmer lines without the receipt styling.
- The cash in/out slip only prints on a real printer (ePOS / IoT): Odoo's cash-move popup calls the
  printer without web-print fallback.
