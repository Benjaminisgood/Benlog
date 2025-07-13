# ------------------- Gallery/routes.py -------------------
from flask import (
    render_template, request, redirect,
    url_for, flash
)
from flask_login import login_required
from werkzeug.utils import secure_filename
from .oss_utils import (
    list_albums,       # 列举所有相册（OSS 前缀）
    list_objects,      # 列举相册下的对象并支持分页
    generate_signed_url,# 生成带签名的访问 URL
    delete_object,     # 删除指定对象
    _get_bucket        # 获取已配置的 Bucket 实例
)
from . import gallery_bp
from Gallery.oss_utils import load_visible_albums, save_visible_albums




def _handle_upload(prefix: str):
    """
    处理多文件上传到 OSS 的逻辑：
    1. 验证至少选择一个文件
    2. 对文件名进行安全转换
    3. 在 OSS Bucket 中以前缀 + 文件名形成 key 上传
    4. 返回上传成功的文件数
    """
    files = request.files.getlist('file')
    if not files:
        # 没有文件则抛出异常，外层 catch 会处理重定向和 flash 提示
        raise ValueError('Please select at least one file to upload.')

    bucket = _get_bucket()
    uploaded_count = 0
    for f in files:
        filename = secure_filename(f.filename)
        key = f"{prefix}{filename}"
        bucket.put_object(key, f.stream)
        uploaded_count += 1
    return uploaded_count


@gallery_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    """
    单页视图入口：
    - GET 请求：
        * 无 prefix -> 列出相册列表（gallery_albums.html）
        * 有 prefix -> 列出该相册下文件（gallery_index.html），并支持分页
    - POST 请求：
        * 处理上传，自动识别是否在某个相册下
    """
    prefix = request.args.get('prefix', '') or ''
    visible_config = load_visible_albums()

    # --- POST：处理文件上传 ---
    if request.method == 'POST':
        try:
            count = _handle_upload(prefix)
            flash(f'Uploaded {count} file(s).', 'success')
        except ValueError as e:
            flash(str(e), 'error')
        # 上传完成后重定向到当前相册或根目录
        return redirect(url_for('gallery.index', prefix=prefix))

    # --- GET：根据 prefix 展示 ---
    if not prefix:
        albums = list_albums()

        # ✅ 为每个相册选取首张图片作为封面
        album_infos = []
        for album in albums:
            if not visible_config.get(album, {}).get("visible", False):
                continue
            keys, _ = list_objects(prefix=album, max_keys=20)  # 限定只取少量即可
            image_key = next((k for k in keys if k.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif'))), None)
            cover_url = generate_signed_url(image_key) if image_key else None
            album_infos.append({
                'name': album.rstrip('/'),
                'prefix': album,
                'cover_url': cover_url
            })

        return render_template('gallery_albums.html', albums=album_infos)


    # 有 prefix：列出该相册下的文件，支持分页参数 marker 和 limit
    marker = request.args.get('marker')
    try:
        limit = int(request.args.get('limit', 20))  # 改为 20
    except ValueError:
        limit = 20

    # 通过 OSS 查询文件列表和下页游标
    # 获取原始 key 列表
    raw_keys, next_marker = list_objects(prefix=prefix, marker=marker, max_keys=limit)

    # ✅ 过滤掉以 '/' 结尾的 key（这些是目录，不是媒体文件）
    keys = [k for k in raw_keys if not k.endswith('/')]


    files = []
    for key in keys:
        lower_key = key.lower()
        is_img = lower_key.endswith(('.png', '.jpg', '.jpeg', '.gif', '.nef', '.raw'))
        is_video = lower_key.endswith(('.mp4', '.mov', '.webm'))
        if is_img:
            files.append({
                'key': key,
                'thumb_url': generate_signed_url(key, style='thumb'),
                'full_url': generate_signed_url(key),
                'is_image': True,
                'is_video': False
            })
        elif is_video:
            files.append({
                'key': key,
                'thumb_url': None,
                'full_url': generate_signed_url(key),
                'is_image': False,
                'is_video': True
            })
    audio_url = None
    for f in files:
        if f['key'].lower().endswith(('.mp3', '.m4a', '.ogg')):
            audio_url = f['url']
            break
    # 渲染 gallery_index.html，传递分页和文件数据
    return render_template(
        'gallery_index.html',
        files=files,
        prefix=prefix,
        marker=marker,
        next_marker=next_marker,
        limit=limit,
        bg_audio_url=audio_url
    )


@gallery_bp.route('/delete/<path:key>', methods=['POST'])
@login_required
def delete(key):
    """
    删除指定的 OSS 对象
    """
    delete_object(key)
    flash(f'Deleted: {key}', 'warning')
    # 删除后重定向到当前相册
    return redirect(url_for('gallery.index', prefix=request.args.get('prefix', '')))


@gallery_bp.context_processor
def inject_helpers():
    """
    向模板注入 page_url 辅助函数，方便生成分页链接
    """
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
