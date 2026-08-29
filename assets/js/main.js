// AddisERP Solution PLC — site behaviours (vanilla JS, no build step)
document.addEventListener('DOMContentLoaded', function () {

  // Mobile nav toggle
  var toggle = document.querySelector('.nav-toggle');
  var links = document.querySelector('.nav-links');
  if (toggle && links) {
    toggle.addEventListener('click', function () {
      links.classList.toggle('open');
      var open = links.classList.contains('open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    links.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', function () { links.classList.remove('open'); });
    });
  }

  // Mark active nav link based on current file name
  var current = window.location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.nav-links a[href]').forEach(function (a) {
    var href = a.getAttribute('href');
    if (href === current || (current === '' && href === 'index.html')) {
      a.classList.add('active');
    }
  });

  // Gentle scroll-reveal (progressive enhancement only)
  var revealEls = document.querySelectorAll('[data-reveal]');
  if ('IntersectionObserver' in window && revealEls.length) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.style.opacity = 1;
          entry.target.style.transform = 'none';
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });
    revealEls.forEach(function (el) {
      el.style.opacity = 0;
      el.style.transform = 'translateY(16px)';
      el.style.transition = 'opacity .5s ease, transform .5s ease';
      io.observe(el);
    });
  }

  // Contact form: client-side handling with graceful fallback message
  var form = document.getElementById('contact-form');
  if (form) {
    form.addEventListener('submit', function (e) {
      var status = document.getElementById('form-status');
      // Let it POST normally to contact-handler.php.
      // If JS is present we just show an interim message; the PHP script
      // performs the real validation and redirect / response.
      if (status) {
        status.textContent = 'Sending your message…';
        status.style.color = '#5B6675';
      }
    });
  }
});
