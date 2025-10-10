(() => {
  const STYLE_ID = 'code-copy-style';
  const BUTTON_CLASS = 'code-copy-btn';

  const ensureStyleSheet = () => {
    if (document.getElementById(STYLE_ID)) {
      return;
    }
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .${BUTTON_CLASS} {
        position: absolute;
        top: 12px;
        right: 12px;
        border: none;
        border-radius: 999px;
        padding: 6px 14px;
        background: rgba(15, 23, 42, 0.85);
        color: #fff;
        font-size: 0.75rem;
        font-weight: 600;
        cursor: pointer;
        transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
        display: inline-flex;
        align-items: center;
        gap: 6px;
      }

      .${BUTTON_CLASS}::before {
        content: '📋';
        font-size: 0.9rem;
      }

      .${BUTTON_CLASS}:hover {
        transform: translateY(-1px);
        box-shadow: 0 10px 18px rgba(15, 23, 42, 0.18);
      }

      .${BUTTON_CLASS}.is-success {
        background: linear-gradient(135deg, #22c55e, #16a34a);
      }

      .markdown-body pre {
        position: relative;
      }

      .${BUTTON_CLASS}:focus-visible {
        outline: 2px solid #22d3ee;
        outline-offset: 2px;
      }
    `;
    document.head.appendChild(style);
  };

  const copyToClipboard = async (text) => {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }

    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    textarea.style.pointerEvents = 'none';
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    try {
      const successful = document.execCommand('copy');
      return successful;
    } catch (error) {
      return false;
    } finally {
      textarea.remove();
    }
  };

  document.addEventListener('DOMContentLoaded', () => {
    const blocks = document.querySelectorAll('.markdown-body pre');
    if (!blocks.length) {
      return;
    }

    ensureStyleSheet();

    blocks.forEach((pre, index) => {
      if (pre.dataset.copyBound === '1') {
        return;
      }

      const code = pre.querySelector('code');
      if (!code) {
        return;
      }

      const button = document.createElement('button');
      button.type = 'button';
      button.className = BUTTON_CLASS;
      button.setAttribute('aria-label', '复制代码');
      button.textContent = '复制';
      button.dataset.copyState = 'idle';

      let resetTimer = null;

      const resetLabel = () => {
        button.classList.remove('is-success');
        button.textContent = '复制';
        button.dataset.copyState = 'idle';
      };

      button.addEventListener('click', async () => {
        if (button.dataset.copyState === 'success') {
          return;
        }
        const text = code.innerText;
        try {
          const ok = await copyToClipboard(text);
          if (!ok) {
            throw new Error('copy failed');
          }
          button.classList.add('is-success');
          button.textContent = '已复制';
          button.dataset.copyState = 'success';
        } catch (error) {
          button.textContent = '复制失败';
          button.dataset.copyState = 'error';
        }

        if (resetTimer) {
          window.clearTimeout(resetTimer);
        }
        resetTimer = window.setTimeout(resetLabel, 2000);
      });

      pre.appendChild(button);
      pre.dataset.copyBound = '1';

      if (!pre.id) {
        pre.id = `code-block-${index + 1}`;
      }
    });
  });
})();

