# Index/views.py
from flask import render_template, abort, request, jsonify
import requests
import urllib3
from . import index_bp
import os
import openai
import random  # 引入 random 模块

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def get_images_from_folder(folder_name):
    images = []
    folder_path = os.path.join(BASE_DIR, 'Benlog', 'static', 'gallery', folder_name)
    if os.path.exists(folder_path):
        for file in os.listdir(folder_path):
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                images.append(file)
    return images

def get_audio_from_folder(folder_name):
    audios = []
    folder_path = os.path.join(BASE_DIR, 'Benlog', 'static', 'gallery', folder_name)
    if os.path.exists(folder_path):
        for file in os.listdir(folder_path):
            if file.lower().endswith(('.mp3', '.wav', '.ogg', '.m4a')):
                audios.append(file)
    return audios

def get_books_from_folder(folder_name):
    books = []
    folder_path = os.path.join(BASE_DIR, 'Benlog', 'static', 'gallery', folder_name)
    if os.path.exists(folder_path):
        for file in os.listdir(folder_path):
            if file.lower().endswith(('.pdf', '.epub', '.txt', '.docx')):
                books.append(file)
    return books

@index_bp.route('/')
def home():
    """Site homepage - shows welcome message and navigation."""
    return render_template('index.html', title="Home")

@index_bp.route('/<page>')
def placeholder(page):
    """
    Placeholder page for features not yet implemented.
    `page` can be 'board', 'survey', 'chat', etc.
    """
    # Map page identifiers to a display name
    placeholders = {
        "board": "留言板",
        "survey": "问卷调查",
        "chat": "聊天机器人",
    }
    feature_name = placeholders.get(page, "该模块")  # default to "该" (meaning "this") if not found
    # Render a generic placeholder page
    return render_template('placeholder.html', title=feature_name, feature_name=feature_name)

@index_bp.route('/gallery')
def gallery():
    """用于展示【摄影展】页面，初始加载 12 张图片"""
    folder = '摄影展'
    images = get_images_from_folder(folder)
    # 固定随机种子，使同一文件夹的随机排序一致
    random.seed(folder)
    random.shuffle(images)
    # 取出前 12 张图片
    initial_batch = images[:12]
    return render_template('gallery.html', title="摄影展", folder=folder, images=initial_batch, media_type="image")

@index_bp.route('/gallery/load_more')
def gallery_load_more():
    """根据 offset 加载下一批图片，每次 12 张"""
    folder = request.args.get('folder', '摄影展')
    try:
        offset = int(request.args.get('offset', 0))
    except ValueError:
        offset = 0
    images = get_images_from_folder(folder)
    random.seed(folder)
    random.shuffle(images)
    batch_size = 12
    next_images = images[offset:offset+batch_size]
    return jsonify({'images': next_images})

@index_bp.route('/darwin_album')
def darwin_album():
    """用于展示【达尔文的专属相册】页面"""
    folder = '达尔文的专属相册'
    images = get_images_from_folder(folder)
    return render_template('gallery.html', title="达尔文的专属相册", folder=folder, images=images, media_type="image")

@index_bp.route('/paintings')
def paintings():
    """用于展示【我的绘画作品】页面"""
    folder = '我的绘画作品'
    images = get_images_from_folder(folder)
    return render_template('gallery.html', title="我的绘画作品", folder=folder, images=images, media_type="image")

@index_bp.route('/audios')
def audios():
    folder = '音乐和弹唱作品'
    audios = get_audio_from_folder(folder)
    return render_template('gallery.html', title="音乐和弹唱作品", folder=folder, audios=audios, media_type="audio")

@index_bp.route('/ebooks')
def ebooks():
    """用于展示【音乐作品】页面"""
    folder = '电子书和论文'
    books = get_books_from_folder(folder)
    return render_template('gallery.html', title="电子书论文", folder=folder, books=books, media_type="ebook")


api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY 环境变量未设置，请先设置！")

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

@index_bp.route('/lezhi')
def lezhi():
    return render_template('lezhi.html', title="乐志")

@index_bp.route('/resume')
def resume():
    """简历页面"""
    return render_template('resume.html', title="Resume")

@index_bp.route('/aboutme')
def aboutme():
    """自我介绍页面"""
    return render_template('aboutme.html', title="About Me")

@index_bp.route('/study')
def study():
    """课题研究方向页面"""
    return render_template('study.html', title="课题方向")

@index_bp.route('/interest')
def interest():
    return render_template('interest.html', title="最近在做的事和兴趣")
