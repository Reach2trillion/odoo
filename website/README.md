# ABJ Skincare — Odoo Website Source

Source templates and styles for the ABJ / AIBAOJI online store, deployed to the
Odoo instance at https://odoo2.yifu.io (website_sale / eCommerce).

## Files

| File | Odoo target |
|------|-------------|
| `homepage.xml` | Home page QWeb view (`website.homepage`, view id 2854) |
| `about.xml`    | `/about-us` page view (bilingual EN/ខ្មែរ) |
| `faq.xml`      | `/faq` page view (bilingual EN/ខ្មែរ) |
| `policy.xml`   | `/policy` page view — shipping, returns, privacy, terms (bilingual EN/ខ្មែរ) |
| `abj_brand.css`| Brand styles injected via **Website → Settings → Custom `<head>` code** |

## Notes

- Product and category records, images, menus, SEO meta, favicon and social
  image are configured directly on the Odoo instance via the MCP admin API.
- eCommerce (`website_sale`) is installed; Wire Transfer payment is enabled.
- This is a **work-in-progress snapshot**. The catalog is being migrated from
  placeholder products to the real ABJ / AIBAOJI product line (blue "Skin Care
  Series" + "Wash Care Series"); these templates will be updated to match.
