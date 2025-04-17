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

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

#
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
#
# 
#预先定义每种媒体对应的扩展名
MEDIA_EXTENSIONS = {
    "image": ('.png', '.jpg', '.jpeg', '.gif'),
    "audio": ('.mp3', '.wav', '.ogg', '.m4a'),
    "ebook": ('.pdf', '.epub', '.txt', '.docx')
}
# 用于确保目录存在，如果没有则创建目录
def ensure_directory_exists(folder):
    folder_path = os.path.join('Benlog/static/gallery', folder)
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        print(f"Created directory: {folder_path}")

def get_media_from_folder(folder_name, media_type):
    """
    通用从指定文件夹获取媒体文件列表的函数。
    
    参数:
      folder_name: 媒体文件夹名称（如 '摄影展'、'音乐和弹唱作品' 等）
      media_type: 媒体类型，支持 "image", "audio", "ebook"
      
    返回:
      符合扩展名条件的文件名列表
    """
    extensions = MEDIA_EXTENSIONS.get(media_type)
    if not extensions:
        return []
    
    ensure_directory_exists(folder_name)

    media = []
    folder_path = os.path.join(BASE_DIR, 'Benlog', 'static', 'gallery', folder_name)
    if os.path.exists(folder_path):
        for file in os.listdir(folder_path):
            if file.lower().endswith(extensions):
                media.append(file)
    return media

def get_media_batch(media_list, offset=0, batch_size=12):
    """
    从媒体列表中获取指定偏移量和批次数量的媒体项，便于懒加载。
    """
    return media_list[offset:offset+batch_size]


def render_gallery_page(title, folder, media_type, batch_size=None, randomize=False):
    """
    通用渲染媒体画廊页面。
    
    参数:
      title: 页面标题
      folder: 文件夹名称
      media_type: 媒体类型："image", "audio", "ebook"
      batch_size: 若传入则仅加载指定数量，适用于初始批量显示
      randomize: 是否进行随机排序（例如图片展示）
      
    返回:
      渲染后的模板页面，统一传递媒体列表给模板变量 items
    """
    ensure_directory_exists(folder)

    media_list = get_media_from_folder(folder, media_type)
    if randomize and media_type == "image":
        random.seed(folder)
        random.shuffle(media_list)
    if batch_size:
        media_list = get_media_batch(media_list, offset=0, batch_size=batch_size)
    return render_template(
        'gallery.html',
        title=title,
        folder=folder,
        media_type=media_type,
        items=media_list  # 模板统一用 items 接收数据
    )

# 1. 配置映射：key → (页面标题, 文件夹名, 媒体类型, 批量加载数量, 是否随机)
GALLERY_CONFIG = {
    "photograph":    ("摄影",          "photograph",   "image", 12,   True),
    "darwin_album":  ("达尔文的专属相册","darwin_album", "image", 12, True),
    "paintings":     ("我的绘画作品",   "paintings",    "image", 12, True),
    "audios":        ("音乐和弹唱作品",  "audios",       "audio", 6, False),
    "ebooks":        ("电子书籍资源",   "ebooks",       "ebook", 6, False),
    "attachments":    ("附件资源",       "attachments",   "ebook", None, False),
}

# 2. 动态画廊路由
@index_bp.route('/gallery/<page_key>')
def gallery_page(page_key):
    # 1) 尝试从配置加载
    config = GALLERY_CONFIG.get(page_key)

    # 2) 如果有配置就解包，否则使用默认值
    if config:
        title, folder, media_type, batch_size, randomize = config
    else:
        title      = page_key        # 默认标题就用 page_key
        folder     = page_key        # 默认媒体目录名也是 page_key
        media_type = 'image'         # 默认只展示图片
        batch_size = 10              # 默认每页 10 个
        randomize  = False           # 默认不打乱顺序

    ensure_directory_exists(folder)
    return render_gallery_page(
        title=title,
        folder=folder,
        media_type=media_type,
        batch_size=batch_size,
        randomize=randomize
    )
# 统一的加载更多接口，支持所有媒体类型
@index_bp.route('/gallery/load_more')
def gallery_load_more():
    """
    根据前端传入 offset、folder、media_type 加载下一批数据，每批默认 12 项。
    接口返回 JSON 格式数据，格式为 {'items': [...] }。
    """
    folder = request.args.get('folder')
    if not folder:
        abort(400, description="Missing folder parameter")
    
    media_type = request.args.get('media_type', 'image')
    try:
        offset = int(request.args.get('offset', 0))
    except ValueError:
        offset = 0
    batch_size = 12
    media_list = get_media_from_folder(folder, media_type)
    if media_type == "image":
        random.seed(folder)
        random.shuffle(media_list)
    next_batch = get_media_batch(media_list, offset=offset, batch_size=batch_size)
    return jsonify({'items': next_batch})

# 4. 可选：自动列出所有画廊

@index_bp.route('/galleries')
def galleries_index():
    base = os.path.join(BASE_DIR, 'Benlog', 'static', 'gallery')
    if not os.path.isdir(base):
        abort(404, description="画廊目录不存在")
    folders = [
        d for d in os.listdir(base)
        if os.path.isdir(os.path.join(base, d))
    ]
    return render_template('galleries_index.html', folders=folders)




















####################################################################
# 动态页面存放目录
DYNAMIC_PAGES_FOLDER = 'Index/dynamic_pages'

@index_bp.route('/<page>')
def dynamic_page(page):
    """
    统一处理静态页面与占位页面：
    - 若 page 存在于 STATIC_PAGE_MAPPING，则返回对应静态模板
    - 若 page 存在于 PLACEHOLDER_MAPPING，则返回通用占位模板 placeholder.html
    - 若 page 存在于 dynamic_pages 文件夹的 JSON 文件，则渲染动态页面
    - 否则返回 404
    """
    # 1. 处理静态页面
    STATIC_PAGE_MAPPING = {
        "resume": ("resume.html", "Resume"),
        "aboutme": ("aboutme.html", "About Me"),
        "study": ("study.html", "课题方向"),
        "interest": ("interest.html", "最近在做的事和兴趣"),
    }
    # 静态页面优先处理
    if page in STATIC_PAGE_MAPPING:
        template, title = STATIC_PAGE_MAPPING[page]
        return render_template(template, title=title)

    # 2. 处理占位页面
    PLACEHOLDER_MAPPING = {
        "message_board": "留言板",
        "survey": "问卷调查",
        "store": "个人商店",  
        "consultation": "咨询预约",
        "feedback": "意见反馈", 
        "pdf_translate": "PDF 翻译",
    }
    if page in PLACEHOLDER_MAPPING:
        feature_name = PLACEHOLDER_MAPPING[page]
        return render_template('placeholder.html', title=feature_name, feature_name=feature_name)

    # 3. 动态页面：拼路径，加载 JSON
    json_path = os.path.join(DYNAMIC_PAGES_FOLDER, f"{page}.json")
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            page_data = json.load(f)
    except FileNotFoundError:
        # 找不到文件，404
        print(page)
        print(f"动态页面文件 {json_path} 不存在")
        abort(404, description="dynamic页面不存在")
    except json.JSONDecodeError:
        # JSON 解析错误，500
        abort(500, description="页面数据错误")

    # 渲染动态页面模板
    return render_template('dynamic_page.html', page_data=page_data)
    


























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


# Load the quick-links.json file from /Index/dynamic_links directory
def load_quick_links():
    links_file_path = os.path.join(os.path.dirname(__file__), 'dynamic_links', 'quick-links.json')
    with open(links_file_path, 'r', encoding='utf-8') as file:
        return json.load(file)
def load_friend_links():
    links_file_path = os.path.join(os.path.dirname(__file__), 'dynamic_links', 'friend-links.json')
    with open(links_file_path, 'r', encoding='utf-8') as file:
        return json.load(file)


@index_bp.route('/')
def home():
    quick_links = load_quick_links()
    friend_links = load_friend_links()
    # —— 新增：扫描所有 gallery 子文件夹 —— 
    galleries_dir = os.path.join(BASE_DIR,'Benlog', 'static', 'gallery')
    # 确保目录存在
    if not os.path.isdir(galleries_dir):
        os.makedirs(galleries_dir)  # Google: [Python os.makedirs](https://www.google.com/search?q=Python+os.makedirs)
    # 列出所有子文件夹
    galleries = [
        d for d in os.listdir(galleries_dir)
        if os.path.isdir(os.path.join(galleries_dir, d))
    ]  # Google: [Python os.listdir](https://www.google.com/search?q=Python+os.listdir)

    return render_template(
        'index.html',
        quick_links=quick_links,
        friend_links=friend_links,
        galleries=galleries,       # 把扫描结果传给模板
        title="首页"
    )

























