document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.post-content img').forEach(img => {
      img.style.cursor = 'zoom-in'; // 鼠标指针样式提示可点击
      img.addEventListener('click', () => {
        const overlay = document.createElement('div');
        overlay.classList.add('fullscreen-overlay');
  
        const fullImg = document.createElement('img');
        fullImg.src = img.src;
  
        overlay.appendChild(fullImg);
        document.body.appendChild(overlay);
  
        overlay.addEventListener('click', () => {
          document.body.removeChild(overlay);
        });
      });
    });
  });