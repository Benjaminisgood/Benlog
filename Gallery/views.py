import os
import random
from collections import Counter
from datetime import datetime
from PIL import Image
from flask import (
    request, redirect, flash,
    render_template, abort,
    current_app, url_for, jsonify,
    send_from_directory
)
from flask_login import login_required
from werkzeug.utils import secure_filename
from . import gallery_bp

# 当前模块目录
MODULE_DIR = os.path.dirname(__file__)
# Blueprint 静态目录  (…/Gallery/static/galleries)
GALLERIES_DIR = os.path.join(MODULE_DIR, gallery_bp.static_folder)
os.makedirs(GALLERIES_DIR, exist_ok=True)

# ======== 媒体扩展名映射 ========
MEDIA_EXTENSIONS = {
    "image": ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp',
              '.svg', '.tiff', '.nef', '.cr2', '.raw', '.dng',
              '.heic', '.heif'),
    "audio": ('.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac',
              '.wma', '.opus', '.aiff', '.alac', '.webm'),
    "ebook": ('.pdf', '.epub', '.txt', '.docx', '.pptx', '.xlsx',
              '.doc', '.ppt', '.xls', '.mobi'),
    "video": ('.mp4', '.webm', '.mov', '.avi')          
}

# ---------- 工具函数 ----------
def ensure_directory_exists(folder_name):
    path = os.path.join(GALLERIES_DIR, folder_name)
    os.makedirs(path, exist_ok=True)
    return path


def ensure_thumbnail_directory(folder_name):
    thumb_dir = os.path.join(GALLERIES_DIR, folder_name, 'thumbnails')
    os.makedirs(thumb_dir, exist_ok=True)
    return thumb_dir

def generate_thumbnail(folder_name, filename):
    """生成图片的缩略图，若不存在则创建"""
    thumb_dir = ensure_thumbnail_directory(folder_name)
    thumb_path = os.path.join(thumb_dir, f"thumb_{filename}")
    original_path = os.path.join(GALLERIES_DIR, folder_name, filename)
    
    if not os.path.exists(thumb_path):
        try:
            img = Image.open(original_path)
            img.thumbnail((200, 200))  # 设置缩略图尺寸
            img.save(thumb_path)
        except Exception as e:
            current_app.logger.error(f"缩略图生成失败 {filename}: {e}")
            return filename  # 生成失败时返回原图文件名
    return f"thumb_{filename}"




def detect_media_type(folder_path):                       # ★ 自动侦测
    counter = Counter()
    for fname in os.listdir(folder_path):
        low = fname.lower()
        for mtype, exts in MEDIA_EXTENSIONS.items():
            if low.endswith(exts):
                counter[mtype] += 1
                break
    if not counter:                                       # 空文件夹
        return "image"
    return counter.most_common(1)[0][0]

def get_media_list(folder_name, media_type):
    path = ensure_directory_exists(folder_name)
    exts = MEDIA_EXTENSIONS[media_type]
    return [f for f in os.listdir(path) if f.lower().endswith(exts)]

def calc_batch_size(total, media_type="image"):                               # ★ 批量策略
    """
    经验策略：
    - <= 12 张 → 全部一次性加载
    - 13-60 张 → 12
    - >  60 张 → 18
    你可按需调整。
    """
    if total <= 12:
        return total
    if total <= 60:
        return 12
    return 9 if media_type == "video" else 18

def get_media_batch(media_list, offset=0, batch_size=12):
    return media_list[offset: offset + batch_size]

# ---------- 视图 ----------
# 所有画廊列表
@gallery_bp.route('/')
def index():
    galleries = sorted(
        d for d in os.listdir(GALLERIES_DIR)
        if os.path.isdir(os.path.join(GALLERIES_DIR, d))
    )
    return render_template('gallery_index.html',
                           title="所有画廊",
                           galleries=galleries)

# 单个画廊页
@gallery_bp.route('/<folder>')
def gallery_page(folder):
    path = ensure_directory_exists(folder)
    media_type = detect_media_type(path)                  # ★
    media_list = get_media_list(folder, media_type)

    random.seed(folder)                                   # ★ 一律随机
    random.shuffle(media_list)

    batch_size = calc_batch_size(len(media_list), media_type)         # ★
    first_batch = get_media_batch(media_list, 0, batch_size)
    thumbnails = [
        generate_thumbnail(folder, fname)
        for fname in first_batch
    ]

    return render_template('gallery.html',
                           title=folder,                  # ★ 标题即文件夹名
                           folder=folder,
                           media_type=media_type,
                           items=first_batch,
                           thumbnails=thumbnails,
                           batch_size=batch_size,         # ★ 传给前端方便无限加载
                           total=len(media_list))

# 无限加载接口
@gallery_bp.route('/load_more')
def gallery_load_more():
    folder = request.args.get('folder') or abort(400, "Missing folder")
    offset = int(request.args.get('offset', 0) or 0)

    path = ensure_directory_exists(folder)
    media_type = detect_media_type(path)                  # ★ 再次侦测以防类型变化
    media_list = get_media_list(folder, media_type)
    random.seed(folder)
    random.shuffle(media_list)

    batch_size = calc_batch_size(len(media_list), media_type)         # 与首批保持一致
    batch = get_media_batch(media_list, offset, batch_size)

    thumbnails = [
    generate_thumbnail(folder, fname)
    for fname in batch
]
    return jsonify({'items': batch, 'thumbnails': thumbnails})


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
def rename_file(folder_name):  # ✅ 必须显式接受 folder_name
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