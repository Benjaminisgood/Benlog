(() => {
  const IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg'];
  const VIDEO_EXTENSIONS = ['mp4', 'webm', 'mov'];
  const AUDIO_EXTENSIONS = ['mp3', 'wav', 'flac', 'aac', 'ogg'];
  const DOCUMENT_EXTENSIONS = ['pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx'];

  const DEFAULT_FLASH_DURATIONS = {
    success: 5000,
    info: 5000,
    warning: 7000,
    error: 8000,
  };

  const TONE_CLASS_MAP = {
    success: 'flash-success',
    info: 'flash-info',
    warning: 'flash-warning',
    error: 'flash-error',
  };

  const TONE_ICON_SVG = {
    success: '<svg viewBox="0 0 24 24" focusable="false"><path d="M9.5 16.2l-3.7-3.7a1 1 0 0 1 1.4-1.4l2.3 2.32 6.4-6.42a1 1 0 1 1 1.4 1.42l-7.8 7.78a1 1 0 0 1-1.4 0z"></path></svg>',
    info: '<svg viewBox="0 0 24 24" focusable="false"><path d="M12 4a8 8 0 1 1 0 16 8 8 0 0 1 0-16zm0 3.5a1 1 0 1 0 0 2 1 1 0 0 0 0-2zm1 4h-2a1 1 0 0 0-1 1v4a1 1 0 1 0 2 0v-3h1a1 1 0 1 0 0-2z"></path></svg>',
    warning: '<svg viewBox="0 0 24 24" focusable="false"><path d="M12 4a1 1 0 0 1 .87.5l7.5 13a1 1 0 0 1-.87 1.5H4.5a1 1 0 0 1-.87-1.5l7.5-13A1 1 0 0 1 12 4zm0 10a1 1 0 0 0-1-1V11a1 1 0 1 0 2 0v2a1 1 0 0 0-1 1zm0 4a1.25 1.25 0 1 0 0 2.5 1.25 1.25 0 0 0 0-2.5z"></path></svg>',
    error: '<svg viewBox="0 0 24 24" focusable="false"><path d="M12 5a1 1 0 0 1 .9.55l6.5 12.5A1 1 0 0 1 18.5 20h-13a1 1 0 0 1-.9-1.45L11 5.55A1 1 0 0 1 12 5zm0 5a1 1 0 0 0-1 1v3a1 1 0 1 0 2 0v-3a1 1 0 0 0-1-1zm0 7.25a1.25 1.25 0 1 0 0 2.5 1.25 1.25 0 0 0 0-2.5z"></path></svg>',
  };

  const COVER_TARGET = {
    width: 1280,
    height: 720,
    quality: 0.82,
  };

  const KIND_LABEL = {
    image: '图片',
    video: '视频',
    audio: '音频',
    document: '文档',
    file: '文件',
  };

  const PHOTOPEA_ORIGIN = 'https://www.photopea.com/#';

  const toArray = (listLike) => Array.prototype.slice.call(listLike || []);

  const escapeHtml = (value) => {
    if (value === null || value === undefined) {
      return '';
    }
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  };

  const detectKind = (name, fallback) => {
    if (!name && fallback) {
      return fallback;
    }
    if (!name) {
      return 'file';
    }

    const lowered = name.split('?')[0].split('#')[0].toLowerCase();
    const ext = lowered.includes('.') ? lowered.split('.').pop() || '' : '';

    if (IMAGE_EXTENSIONS.includes(ext)) return 'image';
    if (VIDEO_EXTENSIONS.includes(ext)) return 'video';
    if (AUDIO_EXTENSIONS.includes(ext)) return 'audio';
    if (DOCUMENT_EXTENSIONS.includes(ext)) return 'document';
    return fallback || 'file';
  };

  const createFlashStack = () => {
    let stack = document.getElementById('flash-stack');
    if (stack) {
      return stack;
    }
    stack = document.createElement('section');
    stack.id = 'flash-stack';
    stack.className = 'flash-stack';
    stack.setAttribute('role', 'status');
    stack.setAttribute('aria-live', 'polite');
    document.body.prepend(stack);
    return stack;
  };

  const pushFlash = (message, tone = 'info') => {
    if (!message) {
      return;
    }
    const normalized = ['success', 'warning', 'error', 'info'].includes(tone) ? tone : 'info';
    const stack = createFlashStack();
    const card = document.createElement('article');
    card.className = `flash-card ${TONE_CLASS_MAP[normalized] || 'flash-info'}`;
    card.dataset.duration = DEFAULT_FLASH_DURATIONS[normalized] || DEFAULT_FLASH_DURATIONS.info;
    card.innerHTML = `
      <span class="flash-icon" aria-hidden="true">${TONE_ICON_SVG[normalized] || TONE_ICON_SVG.info}</span>
      <p class="flash-message-text">${message}</p>
      <button class="flash-close" type="button" aria-label="关闭通知">
        <svg viewBox="0 0 24 24" focusable="false">
          <path d="M7.05 7.05a1 1 0 0 1 1.4 0L12 10.6l3.55-3.55a1 1 0 0 1 1.4 1.4L13.4 12l3.55 3.55a1 1 0 1 1-1.4 1.4L12 13.4l-3.55 3.55a1 1 0 0 1-1.4-1.4L10.6 12 7.05 8.45a1 1 0 0 1 0-1.4z"></path>
        </svg>
      </button>
    `;
    stack.appendChild(card);

    const removeCard = () => {
      if (!card || card.dataset.removed === '1') return;
      card.dataset.removed = '1';
      card.classList.add('flash-leave');
      card.addEventListener(
        'animationend',
        () => {
          card.remove();
          if (!stack.childElementCount) {
            stack.remove();
          }
        },
        { once: true },
      );
    };

    const duration = Number.parseInt(card.dataset.duration || '5000', 10);
    let timerId = window.setTimeout(removeCard, duration);

    const closeBtn = card.querySelector('.flash-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', removeCard);
      closeBtn.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          removeCard();
        }
      });
    }

    card.addEventListener('mouseenter', () => {
      if (timerId) {
        window.clearTimeout(timerId);
        timerId = null;
      }
    });
    card.addEventListener('mouseleave', () => {
      if (timerId) return;
      timerId = window.setTimeout(removeCard, Math.max(2200, duration / 2));
    });
  };

  const buildPhotopeaUrl = (url) => {
    try {
      const payload = encodeURIComponent(JSON.stringify({ files: [url] }));
      return `${PHOTOPEA_ORIGIN}${payload}`;
    } catch (error) {
      return PHOTOPEA_ORIGIN;
    }
  };

  const uniqueId = () => {
    if (window.crypto && window.crypto.randomUUID) {
      return window.crypto.randomUUID();
    }
    return `media-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
  };

  class NeibrMediaManager {
    constructor(form) {
      this.form = form;
      this.mode = form.dataset.mode || 'create';
      this.postId = Number.parseInt(form.dataset.postId || '0', 10) || 0;
      this.coverUri = form.dataset.coverUri || '';
      this.coverPlaceholder = form.dataset.coverPlaceholder || this.coverUri || '';
      this.api = {
        set: form.dataset.apiCover || '',
        auto: form.dataset.apiCoverAuto || '',
        reset: form.dataset.apiCoverReset || '',
      };

      this.elements = {
        uploadBtn: form.querySelector('[data-neibr-upload-btn]'),
        fileInput: form.querySelector('[data-neibr-file-input]'),
        remotePanel: form.querySelector('[data-neibr-remote-panel]'),
        remoteInput: form.querySelector('[data-neibr-remote-input]'),
        remoteSubmit: form.querySelector('[data-neibr-remote-submit]'),
        gallery: form.querySelector('[data-neibr-gallery]'),
        remoteTextarea: form.querySelector('[data-neibr-remote-textarea]'),
        coverImage: form.querySelector('[data-neibr-cover-image]'),
        coverCard: form.querySelector('[data-neibr-cover-card]'),
        coverAuto: form.querySelector('[data-neibr-cover-auto]'),
        coverReset: form.querySelector('[data-neibr-cover-reset]'),
        coverDataInput: form.querySelector('[data-neibr-cover-data]'),
        coverRemoteInput: form.querySelector('[data-neibr-cover-remote]'),
        deleteBucket: form.querySelector('[data-neibr-delete-bucket]'),
      };
      this.heroImage = document.querySelector('[data-neibr-cover-hero]');

      this.initialMedia = this.parseInitialMedia();
      this.items = new Map();
      this.uploadMap = new Map();
      this.remoteEntries = [];
      this.activeBubble = null;
      this.currentCoverKey = null;

      this.bindEvents();
      this.loadInitialMedia();
      this.refreshRemoteTextarea();
      this.setCoverPreview(this.coverUri || this.coverPlaceholder);
    }

    parseInitialMedia() {
      const raw = this.form.dataset.initialMedia;
      if (!raw) {
        return { local: [], remote: [] };
      }
      try {
        const parsed = JSON.parse(raw);
        return {
          local: Array.isArray(parsed.local) ? parsed.local : [],
          remote: Array.isArray(parsed.remote) ? parsed.remote : [],
        };
      } catch (error) {
        return { local: [], remote: [] };
      }
    }

    bindEvents() {
      const { uploadBtn, fileInput, remoteSubmit, coverAuto, coverReset } = this.elements;

      if (uploadBtn && fileInput) {
        uploadBtn.addEventListener('click', () => fileInput.click());
      }

      if (fileInput) {
        fileInput.addEventListener('change', (event) => {
          const files = event.target.files ? toArray(event.target.files) : [];
          if (files.length) {
            this.handleFileSelection(files);
          }
        });
      }

      if (remoteSubmit) {
        remoteSubmit.addEventListener('click', () => this.addRemoteFromInput());
      }


      if (coverAuto) {
        coverAuto.addEventListener('click', () => this.handleAutoCover());
      }
      if (coverReset) {
        coverReset.addEventListener('click', () => this.handleResetCover());
      }

      document.addEventListener('click', (event) => {
        if (this.activeBubble && !this.activeBubble.contains(event.target)) {
          if (!event.target.closest('[data-neibr-card]')) {
            this.closeBubble();
          }
        }
      });

      window.addEventListener('scroll', () => this.closeBubble(), { passive: true });
      window.addEventListener('resize', () => this.closeBubble(), { passive: true });
    }

    loadInitialMedia() {
      this.initialMedia.local.forEach((item) => this.addExistingLocal(item));
      this.initialMedia.remote.forEach((item) => this.addRemoteEntry(item, true));
    }

    addExistingLocal(media) {
      if (!media || !media.filename) {
        return;
      }
      const key = `local-existing::${media.filename}`;
      const kind = media.kind || detectKind(media.filename, 'file');
      const item = {
        key,
        source: 'local-existing',
        existing: true,
        kind,
        name: media.filename,
        url: media.url,
        thumb: media.kind === 'image' ? media.url : null,
        previewUrl: media.url,
      };
      this.items.set(key, item);
      this.renderCard(item);
    }

    addRemoteEntry(entry, isExisting = false) {
      if (!entry || !entry.url) {
        return;
      }
      const kind = entry.type || detectKind(entry.url, 'file');
      const keyBase = encodeURIComponent(entry.url);
      const key = `${isExisting ? 'remote-existing' : 'remote-upload'}::${keyBase}`;
      if (this.items.has(key)) {
        return;
      }
      const item = {
        key,
        source: isExisting ? 'remote-existing' : 'remote-upload',
        existing: Boolean(isExisting),
        kind,
        name: entry.url,
        url: entry.url,
        previewUrl: entry.url,
      };
      this.items.set(key, item);
      this.remoteEntries.push({
        key,
        url: entry.url,
        existing: Boolean(isExisting),
        kind,
      });
      this.renderCard(item);
    }

    handleFileSelection(files) {
      files.forEach((file) => {
        const fingerprint = `${file.name}-${file.size}-${file.lastModified}`;
        if (this.uploadMap.has(fingerprint)) {
          return;
        }
        const previewUrl = URL.createObjectURL(file);
        const key = `local-upload::${uniqueId()}`;
        const kind = detectKind(file.name, 'file');
        const item = {
          key,
          source: 'local-upload',
          existing: false,
          kind,
          name: file.name,
          file,
          previewUrl,
        };
        this.uploadMap.set(fingerprint, { file, key, previewUrl });
        this.items.set(key, item);
        this.renderCard(item);
      });
      this.syncFileInput();
    }

    renderCard(item) {
      if (!this.elements.gallery || !item) {
        return;
      }
      let card = this.elements.gallery.querySelector(`[data-neibr-card="${item.key}"]`);
      if (card) {
        card.remove();
      }
      card = document.createElement('article');
      card.className = 'media-card-tile';
      card.dataset.neibrCard = item.key;
      card.dataset.kind = item.kind;
      card.dataset.source = item.source;
      card.dataset.existing = item.existing ? '1' : '0';

      const label = KIND_LABEL[item.kind] || KIND_LABEL.file;
      const chip = `<span class="media-type-chip">${escapeHtml(label)}</span>`;

      let preview = '';
      const safePreviewUrl = escapeHtml(item.previewUrl);
      const previewAlt = escapeHtml(item.name || label);
      if (item.kind === 'image') {
        preview = `<img src="${safePreviewUrl}" alt="${previewAlt}" loading="lazy" decoding="async">`;
      } else if (item.kind === 'video') {
        preview = `<video src="${safePreviewUrl}" muted preload="metadata"></video>`;
      } else if (item.kind === 'audio') {
        preview = `
          <div class="media-audio">
            <span>${escapeHtml(item.name || label)}</span>
          </div>
        `;
      } else {
        preview = `
          <div class="media-doc">
            <span>${escapeHtml(item.name || label)}</span>
          </div>
        `;
      }

      const rawName = item.name || label;
      const trimmedName = rawName.length > 48 ? `${rawName.slice(0, 45)}…` : rawName;
      const displayName = escapeHtml(trimmedName);
      const titleAttr = escapeHtml(rawName);

      card.innerHTML = `
        <div class="media-thumb">${preview}</div>
        ${chip}
        <footer class="media-meta">
          <strong title="${titleAttr}">${displayName}</strong>
          <span class="media-src">${item.existing ? '已保存' : '待上传'}</span>
        </footer>
      `;

      card.addEventListener('click', (event) => {
        event.preventDefault();
        this.openBubble(item, card);
      });

      this.elements.gallery.appendChild(card);
    }

    openBubble(item, card) {
      this.closeBubble();
      const bubble = document.createElement('div');
      bubble.className = 'media-bubble';
      const sourceLabel = item.source.startsWith('remote') ? '外链' : item.source.includes('existing') ? '本地已上传' : '本地待上传';
      const isImage = item.kind === 'image';
      const safeSourceLabel = escapeHtml(sourceLabel);
      const safeName = escapeHtml(item.name || '');
      const canEdit = Boolean(item.url);

      bubble.innerHTML = `
        <header class="media-bubble-header">
          <span>${safeSourceLabel}</span>
          <small>${safeName}</small>
        </header>
        <div class="media-bubble-actions">
          <button type="button" data-action="cover"${isImage ? '' : ' disabled'}>设为新封面</button>
          <button type="button" data-action="delete">删除</button>
          <button type="button" data-action="edit"${canEdit ? '' : ' disabled'}>编辑</button>
        </div>
      `;

      bubble.querySelectorAll('button[data-action]').forEach((btn) => {
        btn.addEventListener('click', (event) => {
          event.stopPropagation();
          const action = btn.dataset.action;
          this.handleBubbleAction(item, action);
          this.closeBubble();
        });
      });

      document.body.appendChild(bubble);
      const rect = card.getBoundingClientRect();
      const bubbleRect = bubble.getBoundingClientRect();
      const top = window.scrollY + rect.top - bubbleRect.height - 12;
      const left = window.scrollX + rect.left + rect.width / 2 - bubbleRect.width / 2;
      bubble.style.top = `${Math.max(12, top)}px`;
      bubble.style.left = `${Math.max(12, left)}px`;
      requestAnimationFrame(() => bubble.classList.add('show'));
      this.activeBubble = bubble;
    }

    closeBubble() {
      if (this.activeBubble) {
        this.activeBubble.remove();
        this.activeBubble = null;
      }
    }

    handleBubbleAction(item, action) {
      if (!item || !action) return;
      switch (action) {
        case 'cover':
          if (item.kind !== 'image') {
            pushFlash('只能选择图片作为封面。', 'warning');
            return;
          }
          this.handleSetCover(item);
          break;
        case 'delete':
          this.handleDelete(item);
          break;
        case 'edit':
          this.handleEdit(item);
          break;
        default:
          break;
      }
    }

    handleSetCover(item) {
      if (!item) return;
      const isExisting = item.existing && this.postId;
      if (isExisting && (item.source === 'local-existing' || item.source === 'remote-existing')) {
        if (!this.api.set) {
          pushFlash('当前无法更新封面，请稍后重试。', 'error');
          return;
        }
        const payload = {
          source: item.source.startsWith('remote') ? 'remote' : 'local',
        };
        if (payload.source === 'local') {
          payload.filename = item.name;
        } else {
          payload.url = item.url;
        }
        this.callApi(this.api.set, 'POST', payload)
          .then((response) => {
            if (response.status === 'ok') {
              this.setCoverPreview(response.cover);
              this.highlightCover(item.key);
              pushFlash(response.message || '封面更新成功。', 'success');
              this.elements.coverDataInput.value = '';
              this.elements.coverRemoteInput.value = '';
            } else {
              pushFlash(response.message || '封面更新失败。', 'error');
            }
          })
          .catch(() => pushFlash('网络异常，封面未更新。', 'error'));
        return;
      }

      if (item.source.startsWith('remote')) {
        if (this.elements.coverRemoteInput) {
          this.elements.coverRemoteInput.value = item.url;
        }
        if (this.elements.coverDataInput) {
          this.elements.coverDataInput.value = '';
        }
        this.setCoverPreview(item.url);
        this.highlightCover(item.key);
        pushFlash('封面将随保存同步。', 'info');
        return;
      }

      if (item.file && this.elements.coverDataInput) {
        this.prepareCoverFromFile(item.file)
          .then(({ dataUrl, base64 }) => {
            if (!base64) {
              pushFlash('无法解析压缩后的封面。', 'error');
              return;
            }
            this.elements.coverDataInput.value = base64;
            this.elements.coverRemoteInput.value = '';
            this.setCoverPreview(dataUrl);
            this.highlightCover(item.key);
            pushFlash('封面将随保存同步。', 'info');
          })
          .catch((error) => {
            console.error('Failed to compress cover image:', error);
            pushFlash('封面处理失败，请尝试其他文件。', 'error');
          });
      }
    }

    handleDelete(item) {
      if (!item) return;
      const key = item.key;
      const card = this.elements.gallery.querySelector(`[data-neibr-card="${key}"]`);
      if (card) {
        card.remove();
      }
      this.items.delete(key);

      if (item.source === 'local-existing' && this.elements.deleteBucket) {
        const exists = this.elements.deleteBucket.querySelector(`input[value="${item.name}"]`);
        if (!exists) {
          const hidden = document.createElement('input');
          hidden.type = 'hidden';
          hidden.name = 'delete_files';
          hidden.value = item.name;
          this.elements.deleteBucket.appendChild(hidden);
        }
        pushFlash('该本地文件将在保存后删除。', 'warning');
      } else if (item.source === 'remote-existing' || item.source === 'remote-upload') {
        this.remoteEntries = this.remoteEntries.filter((entry) => entry.key !== key);
        this.refreshRemoteTextarea();
        pushFlash('外链已移除。', 'info');
      } else if (item.source === 'local-upload') {
        this.removeUploadItem(item);
        this.syncFileInput();
        pushFlash('已从待上传列表中移除。', 'info');
      }

      if (this.currentCoverKey === key) {
        this.currentCoverKey = null;
        this.highlightCover(null);
      }
    }

    handleEdit(item) {
      if (!item || !item.previewUrl) {
        pushFlash('找不到可以编辑的资源。', 'warning');
        return;
      }
      const targetUrl = item.url || item.previewUrl;
      const photopeaUrl = buildPhotopeaUrl(targetUrl);
      window.open(photopeaUrl, '_blank', 'noopener');
    }

    removeUploadItem(item) {
      const entry = [...this.uploadMap.entries()].find(([, value]) => value.key === item.key);
      if (entry) {
        const [fingerprint, value] = entry;
        this.uploadMap.delete(fingerprint);
        if (value.previewUrl) {
          URL.revokeObjectURL(value.previewUrl);
        }
      }
    }

    handleAutoCover() {
      if (this.postId && this.api.auto) {
        this.callApi(this.api.auto, 'POST')
          .then((response) => {
            if (response.status === 'ok') {
              this.setCoverPreview(response.cover);
              this.highlightCover(null);
              pushFlash(response.message || '已自动选定封面。', 'success');
              this.elements.coverDataInput.value = '';
              this.elements.coverRemoteInput.value = '';
            } else {
              pushFlash(response.message || '自动选定封面失败。', 'error');
            }
          })
          .catch(() => pushFlash('网络异常，封面未更新。', 'error'));
        return;
      }
      const firstImage = [...this.items.values()].find((media) => media.kind === 'image');
      if (firstImage) {
        this.handleSetCover(firstImage);
      } else {
        pushFlash('尚未添加图片资源，无法生成封面。', 'warning');
      }
    }

    handleResetCover() {
      if (this.postId && this.api.reset) {
        this.callApi(this.api.reset, 'DELETE')
          .then((response) => {
            if (response.status === 'ok') {
              this.setCoverPreview(response.cover || this.coverPlaceholder);
              this.highlightCover(null);
              pushFlash(response.message || '封面已重置。', 'info');
              this.elements.coverDataInput.value = '';
              this.elements.coverRemoteInput.value = '';
            } else {
              pushFlash(response.message || '重置封面失败。', 'error');
            }
          })
          .catch(() => pushFlash('网络异常，封面未重置。', 'error'));
        return;
      }
      this.setCoverPreview(this.coverPlaceholder);
      this.highlightCover(null);
      if (this.elements.coverDataInput) this.elements.coverDataInput.value = '';
      if (this.elements.coverRemoteInput) this.elements.coverRemoteInput.value = '';
      pushFlash('封面将在保存后恢复为默认图。', 'info');
    }

    setCoverPreview(src) {
      if (this.elements.coverImage) {
        this.elements.coverImage.src = src || this.coverPlaceholder;
      }
      if (this.heroImage) {
        this.heroImage.src = src || this.coverPlaceholder;
      }
    }

    highlightCover(key) {
      this.currentCoverKey = key;
      this.elements.gallery
        .querySelectorAll('[data-neibr-card]')
        .forEach((node) => node.classList.toggle('is-cover', node.dataset.neibrCard === key));
      if (!key) {
        this.currentCoverKey = null;
      }
    }

    prepareCoverFromFile(file) {
      return new Promise((resolve, reject) => {
        if (!file) {
          reject(new Error('missing file'));
          return;
        }
        const reader = new FileReader();
        reader.onload = () => {
          const dataUrl = typeof reader.result === 'string' ? reader.result : '';
          if (!dataUrl) {
            reject(new Error('empty data url'));
            return;
          }
          const img = new Image();
          img.onload = () => {
            try {
              const canvas = document.createElement('canvas');
              canvas.width = COVER_TARGET.width;
              canvas.height = COVER_TARGET.height;
              const ctx = canvas.getContext('2d');
              if (!ctx) {
                reject(new Error('canvas context unavailable'));
                return;
              }
              const sourceWidth = img.naturalWidth || img.width;
              const sourceHeight = img.naturalHeight || img.height;
              if (!sourceWidth || !sourceHeight) {
                reject(new Error('invalid image dimensions'));
                return;
              }
              const sourceRatio = sourceWidth / sourceHeight;
              const targetRatio = COVER_TARGET.width / COVER_TARGET.height;
              let sx = 0;
              let sy = 0;
              let sw = sourceWidth;
              let sh = sourceHeight;

              if (sourceRatio > targetRatio) {
                sw = Math.round(sourceHeight * targetRatio);
                sx = Math.round((sourceWidth - sw) / 2);
              } else if (sourceRatio < targetRatio) {
                sh = Math.round(sourceWidth / targetRatio);
                sy = Math.round((sourceHeight - sh) / 2);
              }

              ctx.drawImage(img, sx, sy, sw, sh, 0, 0, COVER_TARGET.width, COVER_TARGET.height);

              canvas.toBlob(
                (blob) => {
                  if (!blob) {
                    reject(new Error('failed to create blob'));
                    return;
                  }
                  const blobReader = new FileReader();
                  blobReader.onload = () => {
                    const result = typeof blobReader.result === 'string' ? blobReader.result : '';
                    const payload = result && result.includes(',') ? result.split(',')[1] : '';
                    resolve({ dataUrl: result, base64: payload });
                  };
                  blobReader.onerror = () => reject(new Error('blob read error'));
                  blobReader.readAsDataURL(blob);
                },
                'image/jpeg',
                COVER_TARGET.quality,
              );
            } catch (error) {
              reject(error);
            }
          };
          img.onerror = () => reject(new Error('image decode error'));
          img.src = dataUrl;
        };
        reader.onerror = () => reject(new Error('file read error'));
        reader.readAsDataURL(file);
      });
    }

    addRemoteFromInput() {
      const { remoteInput } = this.elements;
      if (!remoteInput) return;
      const url = remoteInput.value.trim();
      if (!url) {
        pushFlash('请先输入外链地址。', 'warning');
        return;
      }
      if (this.remoteEntries.some((entry) => entry.url === url)) {
        pushFlash('该外链已添加，无需重复操作。', 'info');
        return;
      }
      this.addRemoteEntry({ url }, false);
      this.refreshRemoteTextarea();
      remoteInput.value = '';
      remoteInput.focus();
      pushFlash('外链已添加。', 'success');
    }

    refreshRemoteTextarea() {
      if (this.elements.remoteTextarea) {
        const lines = this.remoteEntries.map((entry) => entry.url);
        this.elements.remoteTextarea.value = lines.join('\n');
      }
    }

    syncFileInput() {
      const { fileInput } = this.elements;
      if (!fileInput) return;
      const dt = new DataTransfer();
      this.uploadMap.forEach((value) => dt.items.add(value.file));
      fileInput.files = dt.files;
    }

    removeCardByKey(key) {
      const { gallery } = this.elements;
      if (!gallery) return;
      const node = gallery.querySelector(`[data-neibr-card="${key}"]`);
      if (node) node.remove();
    }

    callApi(url, method = 'POST', payload) {
      const options = {
        method,
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
        },
        credentials: 'same-origin',
      };
      if (payload) {
        options.body = JSON.stringify(payload);
      }
      return fetch(url, options).then((response) => response.json());
    }
  }

  window.neibrPushFlash = pushFlash;

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-neibr-media-form]').forEach((form) => {
      // eslint-disable-next-line no-new
      new NeibrMediaManager(form);
    });
  });
})();
