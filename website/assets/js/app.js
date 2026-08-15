/* ==========================================================================
   ABJ Shop — shared behaviour: chrome, cart, product cards, page wiring
   ========================================================================== */

/* ------------------------------------------------------------------ icons */
const ICON = {
  cart: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="20" r="1.4"/><circle cx="18" cy="20" r="1.4"/><path d="M2 3h3l2.6 12.3a1.6 1.6 0 0 0 1.6 1.2h8.2a1.6 1.6 0 0 0 1.6-1.3L21 7H6"/></svg>',
  menu: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16"/></svg>',
  truck: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 16V5h11v11M14 9h4l3 3.5V16"/><circle cx="7.5" cy="18" r="1.8"/><circle cx="17.5" cy="18" r="1.8"/></svg>',
  sun: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4"/></svg>',
  leaf: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20c0-8 5-13 16-14 0 10-5 15-13 15H4z"/><path d="M4 20c3-5 6-7 10-8.5"/></svg>',
  tag: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M20 12.5 12.5 20a2 2 0 0 1-2.8 0L3 13.3V4h9.3l7.7 7.7a2 2 0 0 1 0 .8z"/><circle cx="8" cy="8" r="1.4"/></svg>',
  chat: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a8 8 0 0 1-11.5 7.2L4 21l1.8-5.4A8 8 0 1 1 21 12z"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>',
  phone: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16.9v2.6a1.6 1.6 0 0 1-1.8 1.6A18 18 0 0 1 3 5.8 1.6 1.6 0 0 1 4.6 4h2.6a1.6 1.6 0 0 1 1.6 1.4c.1 1 .3 1.9.6 2.8a1.6 1.6 0 0 1-.4 1.7l-1 1a14 14 0 0 0 5.7 5.7l1-1a1.6 1.6 0 0 1 1.7-.4c.9.3 1.8.5 2.8.6A1.6 1.6 0 0 1 21 16.9z"/></svg>',
  pin: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0z"/><circle cx="12" cy="10" r="2.8"/></svg>',
  clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5.2l3.2 2"/></svg>',
  mail: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="m3.5 7 8.5 6 8.5-6"/></svg>',
  facebook: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M13.5 21v-8h2.7l.4-3.1h-3.1V7.9c0-.9.25-1.5 1.55-1.5H16.7V3.6c-.3 0-1.3-.1-2.5-.1-2.45 0-4.15 1.5-4.15 4.25V9.9H7.3V13h2.75v8z"/></svg>',
  instagram: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3.5" y="3.5" width="17" height="17" rx="5"/><circle cx="12" cy="12" r="3.8"/><circle cx="17" cy="7" r="1" fill="currentColor" stroke="none"/></svg>',
  tiktok: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M16.5 3c.4 2.1 1.7 3.4 3.8 3.6v2.6c-1.4.1-2.7-.3-3.9-1.1v5.6c0 4.4-4.3 6.9-7.8 4.6-3.1-2-3.2-6.7.2-8.5 1-.5 2-.7 3.1-.6v2.7c-1.6-.3-2.7.6-2.8 1.9-.1 1.3 1 2.4 2.4 2.3 1.3-.1 2.1-1.1 2.1-2.5V3z"/></svg>',
  telegram: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M21.5 4.3 3.2 11.2c-1 .4-1 1.1-.2 1.4l4.6 1.4 1.8 5.4c.2.6.4.7 1 .3l2.6-1.9 4.6 3.4c.8.5 1.4.2 1.6-.8l3-13.9c.3-1.2-.4-1.8-1.7-1.2zM8.9 13.9l9.3-5.8c.4-.3.8-.1.5.2l-7.9 7.2-.3 3z"/></svg>'
};

/* ------------------------------------------------------------------- cart */
const Cart = {
  key: 'abj_cart',
  read() {
    try { return JSON.parse(localStorage.getItem(this.key)) || []; }
    catch (e) { return []; }
  },
  write(items) {
    localStorage.setItem(this.key, JSON.stringify(items));
    document.dispatchEvent(new CustomEvent('cartchange'));
  },
  add(slug, size, qty = 1) {
    const items = this.read();
    const hit = items.find((i) => i.slug === slug && i.size === size);
    if (hit) hit.qty += qty; else items.push({ slug, size, qty });
    this.write(items);
  },
  setQty(index, qty) {
    const items = this.read();
    if (!items[index]) return;
    if (qty <= 0) items.splice(index, 1); else items[index].qty = qty;
    this.write(items);
  },
  remove(index) {
    const items = this.read();
    items.splice(index, 1);
    this.write(items);
  },
  count() { return this.read().reduce((n, i) => n + i.qty, 0); },
  subtotal() {
    return this.read().reduce((sum, i) => {
      const p = findProduct(i.slug);
      return p ? sum + p.price * i.qty : sum;
    }, 0);
  }
};

/* ------------------------------------------------------------------ toast */
let toastTimer;
function toast(message) {
  let el = document.querySelector('.toast');
  if (!el) {
    el = document.createElement('div');
    el.className = 'toast';
    el.setAttribute('role', 'status');
    document.body.appendChild(el);
  }
  el.textContent = message;
  requestAnimationFrame(() => el.classList.add('is-visible'));
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('is-visible'), 2400);
}

/* ----------------------------------------------------------------- chrome */
function renderHeader(active) {
  const nav = [
    ['index.html', 'nav.home', 'home'],
    ['shop.html', 'nav.shop', 'shop'],
    ['shop.html?cat=skincare', 'nav.skincare', 'skincare'],
    ['shop.html?cat=cosmetic', 'nav.cosmetic', 'cosmetic'],
    ['about.html', 'nav.about', 'about'],
    ['contact.html', 'nav.contact', 'contact']
  ];
  return `
  <div class="topbar"><span data-i18n="topbar.promo"></span></div>
  <header class="site-header">
    <div class="container header-inner">
      <a class="logo" href="index.html">
        <span class="logo__mark">ABJ</span>
        <span class="logo__text">
          <span class="logo__name">ABJ Shop</span>
          <span class="logo__tag" data-i18n="meta.tagline"></span>
        </span>
      </a>
      <nav class="nav" id="nav">
        ${nav.map(([href, key, id]) =>
          `<a href="${href}" class="${id === active ? 'is-active' : ''}" data-i18n="${key}"></a>`).join('')}
      </nav>
      <div class="header-actions">
        <div class="lang-switch" role="group" aria-label="Language">
          <button type="button" data-lang="en">EN</button>
          <button type="button" data-lang="km">ខ្មែរ</button>
        </div>
        <a class="icon-btn" href="cart.html" id="cartBtn" data-i18n-attr="aria-label:aria.cart">
          ${ICON.cart}<span class="cart-count" id="cartCount" hidden>0</span>
        </a>
        <button class="icon-btn burger" id="burger" type="button" data-i18n-attr="aria-label:aria.menu">
          ${ICON.menu}
        </button>
      </div>
    </div>
  </header>`;
}

function renderFooter() {
  const c = SHOP.contact;
  return `
  <footer class="site-footer">
    <div class="container">
      <div class="footer-grid">
        <div>
          <a class="logo" href="index.html">
            <span class="logo__mark">ABJ</span>
            <span class="logo__text">
              <span class="logo__name">ABJ Shop</span>
              <span class="logo__tag" data-i18n="meta.tagline"></span>
            </span>
          </a>
          <p style="margin-top:1rem" data-i18n="footer.about"></p>
          <div class="socials">
            <a href="${c.facebook}" aria-label="Facebook">${ICON.facebook}</a>
            <a href="${c.instagram}" aria-label="Instagram">${ICON.instagram}</a>
            <a href="${c.tiktok}" aria-label="TikTok">${ICON.tiktok}</a>
            <a href="${c.telegram}" aria-label="Telegram">${ICON.telegram}</a>
          </div>
        </div>
        <div>
          <h4 data-i18n="footer.shop"></h4>
          <ul>
            ${SHOP.categories.map((cat) =>
              `<li><a href="shop.html?cat=${cat.slug}">${tv(cat.name)}</a></li>`).join('')}
            <li><a href="shop.html" data-i18n="btn.viewAll"></a></li>
          </ul>
        </div>
        <div>
          <h4 data-i18n="footer.help"></h4>
          <ul>
            <li><a href="contact.html" data-i18n="footer.faq"></a></li>
            <li><a href="contact.html" data-i18n="footer.returns"></a></li>
            <li><a href="contact.html" data-i18n="footer.track"></a></li>
            <li><a href="about.html" data-i18n="nav.about"></a></li>
          </ul>
        </div>
        <div>
          <h4 data-i18n="footer.contact"></h4>
          <ul>
            <li><a href="tel:${c.phone.replace(/\s/g, '')}">${c.phone}</a></li>
            <li><a href="mailto:${c.email}">${c.email}</a></li>
            <li><span class="footer-address"></span></li>
            <li><span class="footer-hours"></span></li>
          </ul>
        </div>
      </div>
      <div class="footer-bottom">
        <span data-i18n="footer.rights"></span>
        <span class="pay-methods">
          <span data-i18n="footer.pay" style="background:none;padding-left:0"></span>
          <span>ABA</span><span>Wing</span><span>ACLEDA</span><span>COD</span>
        </span>
      </div>
    </div>
  </footer>`;
}

/* ---------------------------------------------------------- product cards */
function badgeHtml(p) {
  if (!p.badge) return '';
  const label = { best: { en: 'Best seller', km: 'លក់ដាច់' },
                  sale: { en: 'Sale', km: 'បញ្ចុះតម្លៃ' },
                  new: { en: 'New', km: 'ថ្មី' } }[p.badge];
  return `<span class="badge badge--${p.badge}">${tv(label)}</span>`;
}

function productCard(p) {
  const cat = SHOP.categories.find((c) => c.slug === p.category);
  return `
  <article class="product-card">
    <a class="product-card__media" href="product.html?slug=${p.slug}">
      ${badgeHtml(p)}
      <img src="${productImage(p)}" alt="${tv(p.name)}" loading="lazy" width="600" height="636">
    </a>
    <div class="product-card__body">
      <span class="product-card__cat">${cat ? tv(cat.name) : ''}</span>
      <h3><a href="product.html?slug=${p.slug}">${tv(p.name)}</a></h3>
      <p class="product-card__desc">${tv(p.short)}</p>
      <div class="stars">${'★'.repeat(Math.round(p.rating))}<small>${p.rating.toFixed(1)} (${p.reviews})</small></div>
      <div class="price-row">
        <span class="price">${money(p.price)}</span>
        ${p.oldPrice ? `<span class="price--old">${money(p.oldPrice)}</span>` : ''}
        <span class="price-riel">${riel(p.price)}</span>
      </div>
      <button class="btn btn--primary btn--sm btn--block js-add" data-slug="${p.slug}" data-i18n="btn.addToCart"></button>
    </div>
  </article>`;
}

/* --------------------------------------------------------------- wiring */
function syncCartCount() {
  const el = document.getElementById('cartCount');
  if (!el) return;
  const n = Cart.count();
  el.textContent = n;
  el.hidden = n === 0;
}

function bindAddButtons(root = document) {
  root.querySelectorAll('.js-add').forEach((btn) => {
    if (btn.dataset.bound) return;
    btn.dataset.bound = '1';
    btn.addEventListener('click', () => {
      const p = findProduct(btn.dataset.slug);
      if (!p) return;
      Cart.add(p.slug, p.sizes[0], 1);
      toast(`${t('cart.added')} · ${tv(p.name)}`);
    });
  });
}

function initReveal() {
  const items = document.querySelectorAll('.reveal');
  if (!items.length) return;
  if (!('IntersectionObserver' in window)) {
    items.forEach((el) => el.classList.add('is-in'));
    return;
  }
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) { e.target.classList.add('is-in'); io.unobserve(e.target); }
    });
  }, { threshold: 0.12 });
  items.forEach((el) => io.observe(el));
}

/* Fill contact strings that live in the data file rather than i18n.js. */
function applyContactStrings() {
  document.querySelectorAll('.footer-address').forEach((el) => { el.textContent = tv(SHOP.contact.address); });
  document.querySelectorAll('.footer-hours').forEach((el) => { el.textContent = tv(SHOP.contact.hours); });
}

function boot(page, pageInit) {
  const head = document.getElementById('site-header');
  const foot = document.getElementById('site-footer');
  if (head) head.innerHTML = renderHeader(page);
  if (foot) foot.innerHTML = renderFooter();

  document.querySelectorAll('.lang-switch button').forEach((b) => {
    b.addEventListener('click', () => setLang(b.dataset.lang));
  });
  const burger = document.getElementById('burger');
  const nav = document.getElementById('nav');
  if (burger && nav) burger.addEventListener('click', () => nav.classList.toggle('is-open'));

  const render = () => {
    if (pageInit) pageInit();
    applyI18n();
    applyContactStrings();
    bindAddButtons();
    syncCartCount();
  };

  render();
  initReveal();

  document.addEventListener('langchange', () => {
    const h = document.getElementById('site-header');
    const f = document.getElementById('site-footer');
    if (h) h.innerHTML = renderHeader(page);
    if (f) f.innerHTML = renderFooter();
    document.querySelectorAll('.lang-switch button').forEach((b) => {
      b.addEventListener('click', () => setLang(b.dataset.lang));
    });
    const bg = document.getElementById('burger');
    const nv = document.getElementById('nav');
    if (bg && nv) bg.addEventListener('click', () => nv.classList.toggle('is-open'));
    render();
    document.querySelectorAll('.reveal').forEach((el) => el.classList.add('is-in'));
  });

  document.addEventListener('cartchange', syncCartCount);
}
