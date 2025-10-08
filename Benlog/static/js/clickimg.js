document.addEventListener('DOMContentLoaded', () => {
  const images = document.querySelectorAll('.markdown-body img');
  if (!images.length || document.getElementById('imageModal')) return;

  images.forEach((img) => {
    img.style.cursor = 'zoom-in';
    img.addEventListener('click', () => {
      const overlay = document.createElement('div');
      overlay.classList.add('fullscreen-overlay');

      const fullImg = document.createElement('img');
      fullImg.src = img.src;

      overlay.appendChild(fullImg);
      overlay.style.display = 'flex';
      document.body.appendChild(overlay);

      overlay.addEventListener('click', () => {
        document.body.removeChild(overlay);
      });
    });
  });
});
