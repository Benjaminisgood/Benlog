# Index/views.py
from flask import render_template, abort, request, jsonify
from flask import Blueprint, redirect, url_for, flash
import requests
import urllib3
from . import index_bp
import os
from os.path import join
import openai
import random  # 引入 random 模块
import logging
import json
from flask_login import login_required, current_user
import re
import frontmatter
import markdown
from datetime import datetime
from html.parser import HTMLParser
from markupsafe import Markup, escape
from Neibr.models import Post as NeibrPost
from Settings.models import User


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

BLOG_POSTS_DIR = os.path.join(BASE_DIR, 'Blog', 'posts')
EDU_NOTES_DIR = os.path.join(BASE_DIR, 'Edu', 'notes')
NEIBR_STORAGE_DIR = os.path.join(BASE_DIR, 'Neibr', 'neibr')


class _HTMLStripper(HTMLParser):
    """Utility helper to strip HTML tags and retrieve text content."""

    def __init__(self):
        super().__init__()
        self._chunks = []

    def handle_data(self, data):  # pragma: no cover - trivial
        self._chunks.append(data)

    def get_data(self):
        return ''.join(self._chunks)


def strip_html(text: str) -> str:
    parser = _HTMLStripper()
    parser.feed(text)
    parser.close()
    return parser.get_data()


def condense_text(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def build_snippet(source_text: str, query: str, radius: int = 80) -> Markup:
    """Return a short snippet containing the query, wrapped with <mark> tags."""
    cleaned = condense_text(source_text)
    if not cleaned:
        return Markup('')

    lowered = cleaned.lower()
    query_lower = query.lower()
    match_index = lowered.find(query_lower)

    if match_index == -1:
        truncated = cleaned[: radius * 2]
        suffix = '...' if len(cleaned) > len(truncated) else ''
        return Markup(escape(truncated)) + Markup(suffix)

    start = max(0, match_index - radius)
    end = min(len(cleaned), match_index + len(query) + radius)

    prefix = '...' if start > 0 else ''
    suffix = '...' if end < len(cleaned) else ''

    before = cleaned[start:match_index]
    match = cleaned[match_index:match_index + len(query)]
    after = cleaned[match_index + len(query):end]

    return (
        Markup(prefix)
        + Markup(escape(before))
        + Markup(f"<mark>{escape(match)}</mark>")
        + Markup(escape(after))
        + Markup(suffix)
    )


def metadata_to_blob(metadata) -> str:
    if not isinstance(metadata, dict):
        return ''

    tokens = []
    for value in metadata.values():
        if isinstance(value, (list, tuple, set)):
            tokens.extend(str(item) for item in value)
        elif isinstance(value, (str, int, float)):
            tokens.append(str(value))

    return ' '.join(tokens)


def search_blog_posts(query: str):
    results = []
    query_lower = query.lower()

    if not os.path.isdir(BLOG_POSTS_DIR):
        return results

    for filename in os.listdir(BLOG_POSTS_DIR):
        if not filename.endswith(('.md', '.html')):
            continue

        filepath = os.path.join(BLOG_POSTS_DIR, filename)
        slug = filename.rsplit('.', 1)[0]

        try:
            if filename.endswith('.md'):
                post_data = frontmatter.load(filepath)
                title = post_data.get('title') or slug
                body_markdown = post_data.content or ''
                html_content = markdown.markdown(body_markdown)
                plain_text = strip_html(html_content)
                tags = post_data.get('tags')
                metadata_blob = metadata_to_blob(post_data.metadata)
                search_blob = ' '.join(filter(None, [title, plain_text, metadata_blob]))
            else:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    raw_html = f.read()
                title_match = re.search(r'<title>(.*?)</title>', raw_html, re.IGNORECASE | re.DOTALL)
                title = title_match.group(1).strip() if title_match else slug
                plain_text = strip_html(raw_html)
                tags = None
                search_blob = ' '.join(filter(None, [title, plain_text]))
        except Exception:
            continue

        if query_lower not in search_blob.lower():
            continue

        last_modified = datetime.fromtimestamp(os.path.getmtime(filepath))
        snippet_source = plain_text or search_blob
        if plain_text and query_lower not in plain_text.lower():
            snippet_source = search_blob
        snippet = build_snippet(snippet_source, query)

        if tags:
            if isinstance(tags, (list, tuple, set)):
                tags_text = ', '.join(str(tag) for tag in tags)
            else:
                tags_text = str(tags)
        else:
            tags_text = None

        results.append({
            'module': 'Blog',
            'title': title,
            'slug': slug,
            'url': url_for('blog.show_post', slug=slug),
            'snippet': snippet,
            'timestamp': last_modified,
            'tags': tags_text,
        })

    results.sort(key=lambda item: item['timestamp'], reverse=True)
    return results


def search_edu_notes(query: str):
    results = []
    query_lower = query.lower()

    if not os.path.isdir(EDU_NOTES_DIR):
        return results

    for filename in os.listdir(EDU_NOTES_DIR):
        if not filename.endswith(('.md', '.html')):
            continue

        filepath = os.path.join(EDU_NOTES_DIR, filename)
        slug = filename.rsplit('.', 1)[0]

        try:
            if filename.endswith('.md'):
                note_data = frontmatter.load(filepath)
                title = note_data.get('title') or slug
                body_markdown = note_data.content or ''
                html_content = markdown.markdown(body_markdown)
                plain_text = strip_html(html_content)
                tags = note_data.get('tags')
                metadata_blob = metadata_to_blob(note_data.metadata)
                search_blob = ' '.join(filter(None, [title, plain_text, metadata_blob]))
            else:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    raw_html = f.read()
                title_match = re.search(r'<title>(.*?)</title>', raw_html, re.IGNORECASE | re.DOTALL)
                title = title_match.group(1).strip() if title_match else slug
                plain_text = strip_html(raw_html)
                tags = None
                search_blob = ' '.join(filter(None, [title, plain_text]))
        except Exception:
            continue

        if query_lower not in search_blob.lower():
            continue

        last_modified = datetime.fromtimestamp(os.path.getmtime(filepath))
        snippet_source = plain_text or search_blob
        if plain_text and query_lower not in plain_text.lower():
            snippet_source = search_blob
        snippet = build_snippet(snippet_source, query)

        if tags:
            if isinstance(tags, (list, tuple, set)):
                tags_text = ', '.join(str(tag) for tag in tags)
            else:
                tags_text = str(tags)
        else:
            tags_text = None

        results.append({
            'module': 'Edu',
            'title': title,
            'slug': slug,
            'url': url_for('edu.show_note', slug=slug),
            'snippet': snippet,
            'timestamp': last_modified,
            'tags': tags_text,
        })

    results.sort(key=lambda item: item['timestamp'], reverse=True)
    return results


def _load_neibr_post_body(post: NeibrPost) -> str:
    folder_path = os.path.join(NEIBR_STORAGE_DIR, str(post.user_id), str(post.id))
    text_path = os.path.join(folder_path, 'post.txt')
    if not os.path.exists(text_path):
        return ''
    try:
        with open(text_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except OSError:
        return ''


def search_neibr_posts(query: str):
    results = []
    query_lower = query.lower()

    base_query = NeibrPost.query
    if current_user.is_authenticated:
        posts = (
            base_query
            .filter((NeibrPost.is_hidden == False) | (NeibrPost.user_id == current_user.id))  # noqa: E712
            .order_by(NeibrPost.creation_time.desc())
            .all()
        )
    else:
        posts = (
            base_query
            .filter_by(is_hidden=False)
            .order_by(NeibrPost.creation_time.desc())
            .all()
        )

    if not posts:
        return results

    user_cache = {}

    for post in posts:
        body = _load_neibr_post_body(post)
        components = [post.title or '', post.tags or '', body]
        search_blob = ' '.join(filter(None, components))

        if query_lower not in search_blob.lower():
            continue

        if post.user_id not in user_cache:
            user_cache[post.user_id] = User.query.get(post.user_id)

        author = user_cache[post.user_id].username if user_cache[post.user_id] else '匿名'
        snippet = build_snippet(search_blob, query)

        tags_text = post.tags or None

        results.append({
            'module': 'Neibr',
            'title': post.title,
            'url': url_for('neibr.post_detail', title=post.title, pid=post.id),
            'snippet': snippet,
            'timestamp': post.creation_time,
            'tags': tags_text,
            'author': author,
            'owner_id': post.user_id,
            'post_id': post.id,
        })

    return results


@index_bp.route('/search')
def search():
    query = (request.args.get('q') or '').strip()

    if not query:
        flash('请输入检索关键词。', 'warning')
        return redirect(url_for('index.home'))

    blog_results = search_blog_posts(query)
    edu_results = search_edu_notes(query)
    neibr_results = search_neibr_posts(query)

    grouped_results = [
        {'module': 'Blog', 'matches': blog_results},
        {'module': 'Edu', 'matches': edu_results},
        {'module': 'Neibr', 'matches': neibr_results},
    ]

    total_matches = sum(len(group['matches']) for group in grouped_results)

    # 仅保留有结果的模块，便于模板渲染
    grouped_results = [group for group in grouped_results if group['matches']]

    return render_template(
        'search_results.html',
        query=query,
        grouped_results=grouped_results,
        total_matches=total_matches,
        title='检索结果'
    )





















DYNAMIC_PAGES_FOLDER = os.path.abspath(
    os.path.join(os.path.dirname(__file__), 'dynamic_pages')
)
if not os.path.exists(DYNAMIC_PAGES_FOLDER):
    os.makedirs(DYNAMIC_PAGES_FOLDER)
    
@index_bp.route('/<page>', methods=['GET'])
def dynamic_page(page):
    """
    公共预览：读取 JSON，按数字键排序组装组件列表，
    filename 退化为 URL 中的 page 参数
    """
    json_path = os.path.join(DYNAMIC_PAGES_FOLDER, f"{page}.json")
    if not os.path.exists(json_path):
        abort(404, "页面未找到")

    data = json.load(open(json_path, 'r', encoding='utf-8'))
    # 取 filename，若无则用 URL 参数
    filename = data.get('filename', page)

    # 按数字键排序，构建页面组件列表
    page_components = [
        data[key] for key in sorted(
            [k for k in data if k.isdigit()], key=lambda x: int(x)
        )
    ]

    return render_template(
        'dynamic_viewer.html',
        filename=filename,
        page_components=page_components
    )

@index_bp.route('/<page>/edit', methods=['GET', 'POST'])
@login_required
def edit_dynamic_page(page):
    """
    管理员编辑动态页面：
      GET  渲染编辑表单
      POST 保存 JSON，并在文件名（filename）变更时重命名文件
    """
    # 旧的 JSON 路径
    old_json_path = os.path.join(DYNAMIC_PAGES_FOLDER, f"{page}.json")
    if not os.path.exists(old_json_path):
        abort(404, "页面不存在")

    # 读取整个 JSON
    with open(old_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 组装组件列表用于渲染
    page_components = [
        data[k] for k in sorted(
            [k for k in data if k.isdigit()],
            key=lambda x: int(x)
        )
    ]

    # 当前保存在 JSON 中的文件名（有时 data['filename'] 里存了最新名字）
    filename = data.get('filename', page)

    if request.method == 'POST':
        # 从表单读取新的文件名
        raw_new = request.form['filename'].strip()
        new_filename = raw_new or filename  # 为空时保留旧名

        # 如果文件名确实变了，先做重命名
        if new_filename != filename:
            # 生成安全的文件名
            safe = re.sub(r'[^0-9A-Za-z_-]', '_', new_filename)
            new_json_path = os.path.join(DYNAMIC_PAGES_FOLDER, f"{safe}.json")
            if os.path.exists(new_json_path):
                flash("目标文件名已存在，请换一个", "danger")
                return redirect(url_for('index.edit_dynamic_page', page=page))
            try:
                os.rename(old_json_path, new_json_path)
            except Exception as e:
                flash(f"重命名失败：{e}", "danger")
                return redirect(url_for('index.edit_dynamic_page', page=page))
            # 更新路径与 filename 变量
            old_json_path = new_json_path
            filename = safe
            data['filename'] = safe

        # 重新构建 JSON 对象：保留 filename，重新写入数字键组件
        new_data = {'filename': filename}
        count = int(request.form.get('elements_count', 0))
        for i in range(1, count + 1):
            prefix = f"elements-{i}-"
            ctype = request.form.get(prefix + 'type')
            if not ctype:
                continue
            comp = {'type': ctype}
            # 收集所有以 elements-i- 开头的字段
            for key, val in request.form.items():
                if key.startswith(prefix) and key != prefix + 'type':
                    field = key[len(prefix):]
                    comp[field] = val.strip()
            new_data[str(i)] = comp

        # 写回（重命名后 old_json_path 已是新文件路径）
        try:
            with open(old_json_path, 'w', encoding='utf-8') as f:
                json.dump(new_data, f, ensure_ascii=False, indent=4)
            flash("页面已保存！", "success")
        except Exception as e:
            flash(f"保存失败：{e}", "danger")
            # 如果刚才重命名过，可能需要回滚，略…

        # 重定向到预览页，use new filename
        return redirect(url_for('index.dynamic_page', page=filename))

    # GET 渲染编辑模板
    return render_template(
        'dynamic_editor.html',
        page=filename,
        page_components=page_components
    )

























logging.basicConfig(level=logging.INFO)

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    logging.warning("OPENAI_API_KEY 环境变量未设置，请先设置！")

@index_bp.route('/llm', methods=['POST'])
def llm_query():
    query = request.form.get('query')
    # 1. 设置正确的 API URL（使用 OpenAI 的 completions 端点）
    gpt_api_url = "https://api.openai.com/v1/completions"

    # 2. 构造 HTTP Header，包含 API Key
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # 3. 构造 payload，参数可以根据需要进行调整
    payload = {
        "model": "text-davinci-003",  # 或者你所使用的其他模型，例如 gpt-3.5-turbo (注意对应调用接口不同)
        "prompt": query,
        "max_tokens": 150,
        #"temperature": 0.7
    }
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    try:
        # 4. 发送请求到 OpenAI API，并解析返回结果
        response = requests.post(gpt_api_url, headers=headers, json=payload, verify=False)
        response.raise_for_status()
        data = response.json()
        if "choices" in data and len(data["choices"]) > 0:
            answer = data["choices"][0]["text"].strip()
        else:
            answer = "没有返回答案"
    except Exception as e:
        answer = "请求出错：" + str(e)
    
    return render_template('llm.html', query=query, answer=answer)


# Helper: 确保目录和文件存在
def ensure_json_file(path, default):
    dirpath = os.path.dirname(path)
    os.makedirs(dirpath, exist_ok=True)
    if not os.path.isfile(path):
        # 写入默认内容
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(default, f, ensure_ascii=False, indent=2)

def load_quick_links():
    links_file = os.path.join(
        os.path.dirname(__file__),
        'dynamic_links',
        'quick-links.json'
    )
    # 如果目录或文件不存在，就创建
    ensure_json_file(links_file, default=[])
    # 读取并返回
    with open(links_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_friend_links():
    links_file = os.path.join(
        os.path.dirname(__file__),
        'dynamic_links',
        'friend-links.json'
    )
    ensure_json_file(links_file, default=[])
    with open(links_file, 'r', encoding='utf-8') as f:
        return json.load(f)


@index_bp.route('/')
def home():
    quick_links = load_quick_links()
    friend_links = load_friend_links()

    return render_template(
        'index.html',
        quick_links=quick_links,
        friend_links=friend_links,
        title="首页"
    )
















