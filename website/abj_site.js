/* ABJ / AIBAOJI — front-end motion (injected via Website Settings > Custom end-of-body code) */
(function () {
  'use strict';
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function init() {
    if (!reduced) document.documentElement.classList.add('abj-js');

    /* --- fade-in on view --- */
    if (!reduced && 'IntersectionObserver' in window) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting) { e.target.classList.add('is-in'); io.unobserve(e.target); }
        });
      }, { rootMargin: '50px', threshold: 0 });
      document.querySelectorAll('[data-fade]').forEach(function (el) { io.observe(el); });
    }

    /* --- character split for scroll-reveal paragraphs --- */
    var charEls = Array.prototype.slice.call(document.querySelectorAll('[data-chars]'));
    charEls.forEach(function (el) {
      var text = el.textContent;
      el.textContent = '';
      for (var i = 0; i < text.length; i++) {
        var s = document.createElement('span');
        s.textContent = text[i];
        s.style.opacity = reduced ? 1 : 0.2;
        el.appendChild(s);
      }
    });
    function revealChars() {
      charEls.forEach(function (el) {
        var r = el.getBoundingClientRect();
        var vh = window.innerHeight;
        var start = vh * 0.8, end = vh * 0.2;
        var p = (start - r.top) / (r.height + (start - end));
        p = Math.max(0, Math.min(1, p));
        var spans = el.children, n = spans.length;
        for (var i = 0; i < n; i++) {
          var o = 0.2 + 0.8 * Math.max(0, Math.min(1, p * n - i));
          spans[i].style.opacity = o;
        }
      });
    }

    /* --- scroll marquee (rows tripled for coverage, opposite directions) --- */
    var rows = Array.prototype.slice.call(document.querySelectorAll('[data-mq]'));
    rows.forEach(function (row) {
      var set = row.innerHTML;
      row.innerHTML = set + set + set;
    });
    function measureRows() {
      rows.forEach(function (row) { row.dataset.setw = row.scrollWidth / 3; });
    }
    function moveRows() {
      rows.forEach(function (row) {
        var sec = row.closest('section') || row.parentElement;
        var top = sec.getBoundingClientRect().top + window.scrollY;
        var off = (window.scrollY - top + window.innerHeight) * 0.3;
        var dir = row.getAttribute('data-mq') === 'left' ? -1 : 1;
        var base = parseFloat(row.dataset.setw || 0);
        row.style.transform = 'translateX(' + (dir * (off - 200) - base) + 'px)';
      });
    }

    /* --- sticky stacking cards: scale down as the stack scrolls --- */
    var stack = document.querySelector('[data-stack]');
    var cards = stack ? Array.prototype.slice.call(stack.querySelectorAll('[data-stack-card]')) : [];
    function scaleCards() {
      if (!cards.length) return;
      var r = stack.getBoundingClientRect();
      var total = r.height - window.innerHeight;
      var p = total > 0 ? Math.max(0, Math.min(1, -r.top / total)) : 0;
      cards.forEach(function (c, i) {
        var target = 1 - (cards.length - 1 - i) * 0.03;
        c.style.transform = 'scale(' + (1 - (1 - target) * p) + ')';
      });
    }

    /* --- magnetic hero figure --- */
    var magnet = document.querySelector('.abj-magnet');
    if (magnet && !reduced && window.matchMedia('(pointer: fine)').matches) {
      var PAD = 150, STR = 3;
      window.addEventListener('mousemove', function (ev) {
        var r = magnet.getBoundingClientRect();
        var cx = r.left + r.width / 2, cy = r.top + r.height / 2;
        var inside = ev.clientX > r.left - PAD && ev.clientX < r.right + PAD &&
                     ev.clientY > r.top - PAD && ev.clientY < r.bottom + PAD;
        if (inside) {
          magnet.style.transition = 'transform 0.3s ease-out';
          magnet.style.transform = 'translate3d(' + ((ev.clientX - cx) / STR) + 'px,' + ((ev.clientY - cy) / STR) + 'px,0)';
        } else {
          magnet.style.transition = 'transform 0.6s ease-in-out';
          magnet.style.transform = 'translate3d(0,0,0)';
        }
      }, { passive: true });
    }

    if (!reduced) {
      var ticking = false;
      function onScroll() {
        if (ticking) return;
        ticking = true;
        window.requestAnimationFrame(function () {
          revealChars(); moveRows(); scaleCards();
          ticking = false;
        });
      }
      window.addEventListener('scroll', onScroll, { passive: true });
      window.addEventListener('resize', function () { measureRows(); onScroll(); }, { passive: true });
      measureRows(); revealChars(); moveRows(); scaleCards();
      window.addEventListener('load', function () { measureRows(); moveRows(); });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
