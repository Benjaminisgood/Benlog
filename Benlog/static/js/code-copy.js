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
        border-radius: 999px;
        padding: 6px 12px;
        border: 1px solid rgba(148, 163, 184, 0.35);
        background: rgba(248, 250, 252, 0.78);
        color: rgba(15, 23, 42, 0.75);
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        box-shadow: 0 14px 26px rgba(15, 23, 42, 0.08);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease, color 0.18s ease, box-shadow 0.18s ease;
      }

      .${BUTTON_CLASS}:hover {
        transform: translateY(-1px);
        border-color: rgba(59, 130, 246, 0.45);
        background: rgba(236, 244, 255, 0.92);
        color: rgb(37, 99, 235);
        box-shadow: 0 18px 32px rgba(37, 99, 235, 0.18);
      }

      .${BUTTON_CLASS}:focus-visible {
        outline: none;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.28);
      }

      [data-theme="dark"] .${BUTTON_CLASS} {
        background: rgba(15, 23, 42, 0.72);
        border-color: rgba(148, 163, 184, 0.24);
        color: rgba(226, 232, 240, 0.88);
        box-shadow: 0 18px 34px rgba(2, 6, 23, 0.62);
      }

      [data-theme="dark"] .${BUTTON_CLASS}:hover {
        background: rgba(59, 130, 246, 0.2);
        border-color: rgba(96, 165, 250, 0.4);
        color: rgb(147, 197, 253);
        box-shadow: 0 22px 38px rgba(30, 64, 175, 0.32);
      }

      .${BUTTON_CLASS}.is-success {
        background: rgba(220, 252, 231, 0.94);
        border-color: rgba(34, 197, 94, 0.55);
        color: rgb(22, 163, 74);
      }

      [data-theme="dark"] .${BUTTON_CLASS}.is-success {
        background: rgba(34, 197, 94, 0.22);
        border-color: rgba(34, 197, 94, 0.45);
        color: rgb(16, 185, 129);
      }

      .${BUTTON_CLASS}.is-error {
        background: rgba(254, 242, 242, 0.95);
        border-color: rgba(248, 113, 113, 0.55);
        color: rgb(220, 38, 38);
      }

      [data-theme="dark"] .${BUTTON_CLASS}.is-error {
        background: rgba(220, 38, 38, 0.16);
        border-color: rgba(248, 113, 113, 0.35);
        color: rgb(252, 165, 165);
      }

      .${BUTTON_CLASS} .copy-icon {
        position: relative;
        width: 16px;
        height: 16px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
      }

      .${BUTTON_CLASS} .copy-icon svg {
        width: 16px;
        height: 16px;
        fill: currentColor;
        position: absolute;
        inset: 0;
        transition: opacity 0.18s ease, transform 0.18s ease;
      }

      .${BUTTON_CLASS} .icon-check {
        opacity: 0;
        transform: scale(0.65);
      }

      .${BUTTON_CLASS}.is-success .icon-copy {
        opacity: 0;
        transform: scale(0.65);
      }

      .${BUTTON_CLASS}.is-success .icon-check {
        opacity: 1;
        transform: scale(1);
      }

      .${BUTTON_CLASS} .copy-label {
        display: inline-block;
        line-height: 1;
        font-size: 0.72rem;
        letter-spacing: 0.03em;
      }

      @media (max-width: 640px) {
        .${BUTTON_CLASS} {
          padding: 6px;
          gap: 0;
          min-width: 34px;
        }

        .${BUTTON_CLASS} .copy-label {
          display: none;
        }
      }

      .markdown-body pre {
        position: relative;
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
      button.dataset.copyState = 'idle';

      const iconWrapper = document.createElement('span');
      iconWrapper.className = 'copy-icon';
      iconWrapper.setAttribute('aria-hidden', 'true');
      iconWrapper.innerHTML = `
        <svg class="icon-copy" viewBox="0 0 24 24" focusable="false">
          <path d="M15 3H6a2 2 0 00-2 2v11h2V5h9V3zm3 4H9a2 2 0 00-2 2v12h11a2 2 0 002-2V7zm-2 12H9V9h7v10z"></path>
        </svg>
        <svg class="icon-check" viewBox="0 0 24 24" focusable="false">
          <path d="M9.55 17.1l-3.2-3.2a1 1 0 011.4-1.42l1.8 1.82 6.2-6.22a1 1 0 011.42 1.42l-7.6 7.6a1 1 0 01-1.42 0z"></path>
        </svg>
      `;

      const label = document.createElement('span');
      label.className = 'copy-label';
      label.textContent = '复制';

      button.append(iconWrapper, label);

      let resetTimer = null;

      const resetLabel = () => {
        button.classList.remove('is-success', 'is-error');
        label.textContent = '复制';
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
          button.classList.remove('is-error');
          button.classList.add('is-success');
          label.textContent = '已复制';
          button.dataset.copyState = 'success';
        } catch (error) {
          button.classList.remove('is-success');
          button.classList.add('is-error');
          label.textContent = '复制失败';
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
