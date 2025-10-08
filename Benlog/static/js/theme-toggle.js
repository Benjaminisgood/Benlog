document.addEventListener('DOMContentLoaded', () => {
  const toggleBtn = document.getElementById('theme-toggle');
  const html = document.documentElement;
  const canvas = document.getElementById('universe');

  if (!toggleBtn) return;

  const updateCanvasBackground = () => {
    if (!canvas) return;
    canvas.style.backgroundColor = getComputedStyle(html).getPropertyValue('--canvas-bg');
  };

  updateCanvasBackground();

  toggleBtn.addEventListener('click', () => {
    const currentTheme = html.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateCanvasBackground();
  });
});
