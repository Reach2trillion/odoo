# ABJ Shop — website

A bilingual (English / ខ្មែរ) storefront for ABJ, modelled on the structure of
Cambodian beauty shops like `pichpisey.shop`: category landing, product grid,
product detail pages with a slug URL, cart, and ordering through Telegram.

No build step, no framework, no external JavaScript — plain HTML, one CSS file
and three small scripts. Fonts come from Google Fonts; everything else
(including all product artwork, which is generated SVG) ships in the repo.

## Pages

| File | Purpose |
|---|---|
| `index.html` | Home: hero, categories, best sellers, brand values, story, reviews, newsletter |
| `shop.html` | Catalogue with category filter, search and sorting (`shop.html?cat=skincare`) |
| `product.html` | Product detail (`product.html?slug=vitamin-c-serum`) — gallery, sizes/shades, quantity, tabs, related products |
| `cart.html` | Cart with quantity editing, delivery threshold and Telegram checkout |
| `about.html` | Brand story and promises |
| `contact.html` | Contact details plus a message form that opens Telegram |

## Run it

```bash
# from the repo root
docker compose up -d website     # → http://localhost:8080

# or with no Docker at all
cd website && python3 -m http.server 8080
```

## Editing content

Everything customer-facing lives in two files:

- **`assets/js/data.js`** — products, categories, prices, sizes, reviews, shop
  contact details. Each product carries `en` and `km` text for its name,
  summary, description, how-to and ingredients.
- **`assets/js/i18n.js`** — all interface copy in both languages, keyed by
  `data-i18n` attributes in the HTML.

Adding a product means appending one object to `SHOP.products` and dropping
`assets/img/p-<slug>.svg` (and optionally `p-<slug>-b.svg` for the second
gallery image) next to the others. Nothing else needs to change — the home
page, catalogue, related products and cart all read from that array.

## Language

The language is chosen from `?lang=km`, then `localStorage`, then the browser
setting, defaulting to English. The EN/ខ្មែរ switch in the header re-renders the
page in place and remembers the choice. In Khmer mode the display font swaps to
Kantumruy Pro and letter-spacing is reset, so Khmer script stays legible.

## Ordering

There is no payment gateway. "Order on Telegram" and "Send order" build a
pre-written message listing the items, sizes, quantities and totals, and open
`SHOP.contact.telegram` with it — the same flow most Cambodian shops use, and it
pairs with the Messenger auto-reply bot in this repo. Change the handle, phone,
address and opening hours in `SHOP.contact` in `assets/js/data.js`.

Delivery is free over $25 and $1.50 below that (`FREE_DELIVERY_OVER` and
`DELIVERY_FEE` in `cart.html`).

## Notes

- Product photography is placeholder SVG artwork, generated so the layout is
  complete without binary assets. Swap in real photos by replacing the files in
  `assets/img/` — the markup expects square images.
- The brand name, phone number, Telegram handle and address are placeholders.
- Cart state is `localStorage` only; nothing is sent anywhere until the customer
  opens Telegram.
