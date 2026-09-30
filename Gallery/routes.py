from flask import (
    render_template, request, redirect, url_for, flash, send_file, abort, current_app
)
from flask_login import login_required, current_user
from .oss_utils import (
    list_albums,
    list_objects,
    generate_signed_url,
    delete_object,
    save_upload,
    local_file,
    using_oss,
    ALLOWED_EXTENSIONS,
)
from . import gallery_bp
from Gallery.oss_utils import load_visible_albums, save_visible_albums

IMAGE_EXT = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
VIDEO_EXT = {'.mp4', '.mov', '.webm'}
AUDIO_EXT = {'.mp3', '.m4a', '.ogg'}


def _can_manage():
    return current_user.is_authenticated and (
        getattr(current_user, 'is_admin', False) or current_user.id == 1
    )


def _clean_album_name(raw):
    name = (raw or '').strip().strip('/').replace('\\', '/')
    if not name or '/' in name or name in {'.', '..'}:
        return ''
    return name


@gallery_bp.route('/media/<path:key>')
@login_required
def media(key):
    if using_oss():
        abort(404)
    path = local_file(key)
    if not path:
        abort(404)
    return send_file(path)


@gallery_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    prefix = request.args.get('prefix', '') or ''
    visible_config = load_visible_albums()

    if request.method == 'POST':
        if not _can_manage():
            abort(403)
        album_name = _clean_album_name(request.form.get('album'))
        target = prefix
        if not target and album_name:
            target = album_name + '/'
        if target and not target.endswith('/'):
            target += '/'
        try:
            files = request.files.getlist('file')
            chosen = [item for item in files if item and item.filename]
            if not chosen:
                raise ValueError('请至少选择一个文件。')
            if not target:
                raise ValueError('请先填写相册名称。')
            count = 0
            for item in chosen:
                save_upload(target, item)
                count += 1
            album_key = target
            if album_key not in visible_config:
                visible_config[album_key] = {'visible': True, 'note': ''}
                save_visible_albums(visible_config)
            flash(f'已上传 {count} 个文件。', 'success')
        except ValueError as exc:
            flash(str(exc), 'error')
        except Exception as exc:
            current_app.logger.exception('图库上传失败')
            flash(f'上传失败：{exc}', 'error')
        return redirect(url_for('gallery.index', prefix=target or prefix))

    if not prefix:
        try:
            albums = list_albums()
        except Exception as exc:
            current_app.logger.exception('读取相册失败')
            flash(f'读取图库失败：{exc}', 'error')
            albums = []
        album_infos = []
        for album in albums:
            info = visible_config.get(album, {})
            visible = info if isinstance(info, bool) else bool(isinstance(info, dict) and info.get('visible'))
            if not visible:
                continue
            keys, _ = list_objects(prefix=album, max_keys=20)
            image_key = next((key for key in keys if key.lower().endswith(tuple(IMAGE_EXT))), None)
            cover_url = generate_signed_url(image_key) if image_key else None
            album_infos.append({
                'name': album.rstrip('/'),
                'prefix': album,
                'cover_url': cover_url,
            })
        return render_template(
            'gallery_albums.html',
            albums=album_infos,
            can_manage=_can_manage(),
            allowed_extensions=', '.join(sorted(ALLOWED_EXTENSIONS)),
        )

    marker = request.args.get('marker')
    try:
        limit = int(request.args.get('limit', 20))
    except ValueError:
        limit = 20

    try:
        raw_keys, next_marker = list_objects(prefix=prefix, marker=marker, max_keys=limit)
    except Exception as exc:
        current_app.logger.exception('读取相册文件失败')
        flash(f'读取相册失败：{exc}', 'error')
        raw_keys, next_marker = [], None

    keys = [key for key in raw_keys if key and not key.endswith('/')]
    files = []
    audio_url = None
    for key in keys:
        lower_key = key.lower()
        is_img = lower_key.endswith(tuple(IMAGE_EXT))
        is_video = lower_key.endswith(tuple(VIDEO_EXT))
        is_audio = lower_key.endswith(tuple(AUDIO_EXT))
        if is_audio and not audio_url:
            audio_url = generate_signed_url(key)
        if is_img:
            files.append({
                'key': key,
                'thumb_url': generate_signed_url(key, style='thumb'),
                'full_url': generate_signed_url(key),
                'is_image': True,
                'is_video': False,
            })
        elif is_video:
            files.append({
                'key': key,
                'thumb_url': None,
                'full_url': generate_signed_url(key),
                'is_image': False,
                'is_video': True,
            })

    return render_template(
        'gallery_index.html',
        files=files,
        prefix=prefix,
        marker=marker,
        next_marker=next_marker,
        limit=limit,
        bg_audio_url=audio_url,
        can_manage=_can_manage(),
        allowed_extensions=', '.join(sorted(ALLOWED_EXTENSIONS)),
    )


@gallery_bp.route('/delete/<path:key>', methods=['POST'])
@login_required
def delete(key):
    if not _can_manage():
        abort(403)
    delete_object(key)
    flash(f'已删除：{key}', 'warning')
    return redirect(url_for('gallery.index', prefix=request.args.get('prefix', '')))


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
