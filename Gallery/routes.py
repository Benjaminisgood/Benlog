# ------------------- Gallery/routes.py -------------------
from flask import (
    render_template, request, redirect,
    url_for, flash
)
from flask_login import login_required
from werkzeug.utils import secure_filename
from .oss_utils import (
    list_albums, list_objects,
    generate_signed_url, delete_object, _get_bucket
)
from . import gallery_bp


@gallery_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    """
    单页视图：
    - 无 prefix 时显示相册列表（gallery_albums.html）
    - 否则显示该相册下的媒体文件（gallery_index.html），支持上传、删除和分页
    """
    # 处理上传
    if request.method == 'POST':
        files = request.files.getlist('file')
        if not files:
            flash('Please select at least one file to upload.', 'error')
            return redirect(url_for('gallery.index', prefix=request.args.get('prefix')))
        bucket = _get_bucket()
        prefix = request.args.get('prefix', '') or ''
        for f in files:
            filename = secure_filename(f.filename)
            bucket.put_object(f"{prefix}{filename}", f.stream)
        flash(f'Uploaded {len(files)} file(s).', 'success')
        return redirect(url_for('gallery.index', prefix=prefix))

    # 无 prefix：列出相册
    prefix = request.args.get('prefix')
    if not prefix:
        albums = list_albums()
        return render_template('gallery_albums.html', albums=albums)

    # 有 prefix：列出文件并分页
    marker = request.args.get('marker')
    limit = int(request.args.get('limit', 50))
    keys, next_marker = list_objects(prefix=prefix, marker=marker, max_keys=limit)

    files = []
    for key in keys:
        is_img = key.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))
        is_video = key.lower().endswith(('.mp4', '.mov', '.webm'))
        files.append({
            'key': key,
            'url': generate_signed_url(key),
            'is_image': is_img,
            'is_video': is_video
        })

    return render_template(
        'gallery_index.html',
        files=files,
        prefix=prefix,
        marker=marker,
        next_marker=next_marker,
        limit=limit
    )


@gallery_bp.route('/delete/<path:key>', methods=['POST'])
@login_required
def delete(key):
    delete_object(key)
    flash(f'Deleted: {key}', 'warning')
    return redirect(url_for('gallery.index', prefix=request.args.get('prefix')))


@gallery_bp.context_processor
def inject_helpers():
    def page_url(marker, prefix=None, limit=None):
        args = {}
        if prefix:
            args['prefix'] = prefix
        if marker:
            args['marker'] = marker
        if limit:
            args['limit'] = limit
        return url_for('gallery.index', **args)
    return dict(page_url=page_url)
