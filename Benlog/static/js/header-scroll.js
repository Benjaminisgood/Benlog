(() => {
  const header = document.querySelector('.global-header');
  if (!header) return;

  let lastScrollY = window.scrollY;
  let ticking = false;

  const update = () => {
    const current = window.scrollY;
    const threshold = 12;
    const shouldHide = current > lastScrollY + threshold && current > 120;
    const shouldShow = current < lastScrollY - threshold || current <= 120;

    if (shouldHide) {
      header.classList.add('nav-hidden');
    } else if (shouldShow) {
      header.classList.remove('nav-hidden');
    }

    lastScrollY = current;
    ticking = false;
  };

  window.addEventListener('scroll', () => {
    if (!ticking) {
      window.requestAnimationFrame(update);
      ticking = true;
    }
  }, { passive: true });
})();
