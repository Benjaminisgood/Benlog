document.addEventListener("DOMContentLoaded", () => {
  const toggleBtn = document.getElementById('theme-toggle');
  const html = document.documentElement;
  const canvas = document.getElementById('universe');

  // 获取当前已设定的主题
  const currentTheme = html.getAttribute('data-theme') || 'light';
  toggleBtn.textContent = currentTheme === 'dark' ? '☀️' : '🌙';
  canvas.style.backgroundColor = getComputedStyle(html).getPropertyValue('--canvas-bg');

  toggleBtn.addEventListener('click', () => {
    const currentTheme = html.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    toggleBtn.textContent = newTheme === 'dark' ? '☀️' : '🌙';
    canvas.style.backgroundColor = getComputedStyle(html).getPropertyValue('--canvas-bg');
  });
  
});
