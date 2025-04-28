import os
import random
import json
import logging
from datetime import datetime

import frontmatter
import markdown
from flask import (
    request, redirect, flash,
    render_template, abort,
    current_app, url_for, jsonify
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from . import gallery_bp

# 当前模块目录（Gallery 目录）
MODULE_DIR = os.path.dirname(__file__)
# Blueprint 定义的静态目录（相对于 MODULE_DIR）
GALLERIES_DIR = os.path.join(MODULE_DIR, gallery_bp.static_folder)

# 确保主 galleries 目录存在
os.makedirs(GALLERIES_DIR, exist_ok=True)

# 扫描所有子文件夹并渲染“所有画廊”列表
@gallery_bp.route('/')
def index():
    galleries = sorted(
        d for d in os.listdir(GALLERIES_DIR)
        if os.path.isdir(os.path.join(GALLERIES_DIR, d))
    )
    return render_template(
        'gallery_index.html',
        title="所有画廊",
        galleries=galleries
    )

# 媒体扩展名映射
MEDIA_EXTENSIONS = {
    "image": (
        '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp',
        '.svg', '.tiff', '.nef', '.cr2', '.raw', '.dng',
        '.heic', '.heif', '.indd', '.ai', '.eps'
    ),
    "audio": (
        '.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac',
        '.wma', '.opus', '.aiff', '.alac'
    ),
    "ebook": (
        '.pdf', '.epub', '.txt', '.docx', '.pptx', '.xlsx',
        '.doc', '.ppt', '.xls', '.mobi'
    ),
}

def ensure_directory_exists(folder_name):
    """
    确保某个画廊子目录存在，返回它的绝对路径。
    """
    path = os.path.join(GALLERIES_DIR, folder_name)
    os.makedirs(path, exist_ok=True)
    return path

def get_media_from_folder(folder_name, media_type):
    """
    获取指定子画廊（folder_name）内符合 media_type 的所有文件名列表。
    """
    path = ensure_directory_exists(folder_name)
    exts = MEDIA_EXTENSIONS.get(media_type, ())
    return [
        fname for fname in os.listdir(path)
        if fname.lower().endswith(exts)
    ]

def get_media_batch(media_list, offset=0, batch_size=12):
    """
    对媒体列表做分页截取。
    """
    return media_list[offset:offset + batch_size]

def render_gallery_page(title, folder, media_type,
                        batch_size=None, randomize=False):
    """
    通用渲染画廊页面：
    - 确保文件夹存在
    - 获取媒体列表，可选乱序与分页
    - 返回 gallery.html 模板
    """
    ensure_directory_exists(folder)
    media_list = get_media_from_folder(folder, media_type)

    if randomize and media_type == "image":
        random.seed(folder)
        random.shuffle(media_list)

    if batch_size:
        media_list = get_media_batch(media_list, batch_size=batch_size)

    return render_template(
        'gallery.html',
        title=title,
        folder=folder,
        media_type=media_type,
        items=media_list
    )

# 画廊配置：key → (标题, 子文件夹名, 媒体类型, 初始批量, 是否随机)
GALLERY_CONFIG = {
    "photograph":   ("摄影",            "photograph", "image", 12, True),
    "darwin_album": ("达尔文的专属相册","darwin_album","image", 12, True),
    "paintings":    ("我的绘画作品",    "paintings",   "image", 12, True),
    "audios":       ("音乐和弹唱作品",  "audios",      "audio", 6,  False),
    "ebooks":       ("电子书籍资源",    "ebooks",      "ebook", 6,  False),
    "attachments":  ("附件资源",        "attachments","ebook", None, False),
}

# 单个画廊页：/gallery/<page_key>
@gallery_bp.route('/<page_key>')
def gallery_page(page_key):
    cfg = GALLERY_CONFIG.get(page_key)
    if cfg:
        title, folder, media_type, batch_size, randomize = cfg
    else:
        # 默认值
        title, folder, media_type, batch_size, randomize = (
            page_key, page_key, 'image', 10, False
        )
    return render_gallery_page(
        title, folder, media_type, batch_size, randomize
    )

# 无限加载接口：/gallery/load_more
@gallery_bp.route('/load_more')
def gallery_load_more():
    folder     = request.args.get('folder') or abort(400, "Missing folder")
    media_type = request.args.get('media_type', 'image')
    try:
        offset = int(request.args.get('offset', 0))
    except ValueError:
        offset = 0

    media_list = get_media_from_folder(folder, media_type)
    if media_type == "image":
        random.seed(folder)
        random.shuffle(media_list)

    batch = get_media_batch(media_list, offset=offset)
    return jsonify({'items': batch})


@gallery_bp.route('/manage/<folder_name>')
@login_required
def view_folder(folder_name):
    """
    查看子画廊内所有文件，渲染管理页面。
    """
    folder_path = ensure_directory_exists(folder_name)
    files = [
        f for f in os.listdir(folder_path)
        if not f.startswith('.') and os.path.isfile(os.path.join(folder_path, f))
    ]
    return render_template(
        'manage_folder.html',
        folder_name=folder_name,
        files=files
    )

@gallery_bp.route('/manage/<folder_name>/download/<filename>')
@login_required
def download_file(folder_name, filename):
    """
    下载指定文件。
    """
    folder_path = os.path.join(GALLERIES_DIR, folder_name)
    return send_from_directory(folder_path, filename, as_attachment=True)

@gallery_bp.route('/manage/<folder_name>/delete/<filename>', methods=['POST'])
@login_required
def delete_file(folder_name, filename):
    """
    删除指定文件。
    """
    file_path = os.path.join(GALLERIES_DIR, folder_name, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        flash(f'文件 "{filename}" 已删除', 'success')
    else:
        flash(f'文件 "{filename}" 不存在', 'error')
    return redirect(url_for('gallery.view_folder', folder_name=folder_name))

@gallery_bp.route('/manage/<folder_name>/upload', methods=['POST'])
@login_required
def upload_file(folder_name):
    """
    上传文件到指定子画廊。
    """
    folder_path = ensure_directory_exists(folder_name)
    file = request.files.get('file')
    if file:
        filename = secure_filename(file.filename)
        save_path = os.path.join(folder_path, filename)
        file.save(save_path)
        flash(f'文件 "{filename}" 上传成功', 'success')
    else:
        flash('未检测到上传文件', 'error')
    return redirect(url_for('gallery.view_folder', folder_name=folder_name))

@gallery_bp.route('/manage/<folder_name>/rename', methods=['POST'])
@login_required
def rename_file():
    """
    重命名子画廊中的文件。
    """
    folder_name  = request.form.get('folder-name')
    old_filename = request.form.get('old-filename')
    new_filename = secure_filename(request.form.get('new-filename'))

    folder_path = os.path.join(GALLERIES_DIR, folder_name)
    old_path = os.path.join(folder_path, old_filename)
    new_path = os.path.join(folder_path, new_filename)

    if os.path.exists(old_path):
        os.rename(old_path, new_path)
        flash(f'重命名为 "{new_filename}" 成功', 'success')
    else:
        flash('要重命名的文件不存在', 'error')

    return redirect(url_for('gallery.view_folder', folder_name=folder_name))