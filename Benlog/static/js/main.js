document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.content-card__media[data-card-gradient]').forEach((media) => {
    const gradient = media.dataset.cardGradient;
    const cover = media.dataset.cardCover;
    const layers = [];

    if (gradient) {
      layers.push(gradient);
    }

    if (cover) {
      layers.push(`url("${cover}")`);
    }

    if (layers.length) {
      media.style.backgroundImage = layers.join(', ');
    }
  });

  const isInteractiveTarget = (target) => {
    return target && target.closest('a, button, input, textarea, select');
  };

  document.querySelectorAll('.content-card[data-url]').forEach((card) => {
    const url = card.dataset.url;
    if (!url) return;

    card.addEventListener('click', (event) => {
      if (isInteractiveTarget(event.target)) return;
      window.location.href = url;
    });

    card.addEventListener('keydown', (event) => {
      if (isInteractiveTarget(event.target)) return;
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        window.location.href = url;
      }
    });
  });
});
