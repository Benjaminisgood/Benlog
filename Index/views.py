# Index/views.py
from flask import render_template, abort, request, jsonify
import requests
import urllib3
from . import index_bp
import os
import openai
import random  # 引入 random 模块
import logging

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

@index_bp.route('/')
def home():
    """Site homepage - shows welcome message and navigation."""
    return render_template('index.html', title="Home")
###############################################################
# 预先定义每种媒体对应的扩展名
MEDIA_EXTENSIONS = {
    "image": ('.png', '.jpg', '.jpeg', '.gif'),
    "audio": ('.mp3', '.wav', '.ogg', '.m4a'),
    "ebook": ('.pdf', '.epub', '.txt', '.docx')
}

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

###############################################################################
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

# 各个路由均调用上面统一的渲染函数
@index_bp.route('/photograph')
def photograph():
    """展示【摄影】页面，仅初始加载 12 张图片，支持懒加载"""
    return render_gallery_page("摄影", "photograph", "image", batch_size=12, randomize=True)

@index_bp.route('/darwin_album')
def darwin_album():
    """展示【达尔文的专属相册】页面，展示全部图片"""
    return render_gallery_page("达尔文的专属相册", "达尔文的专属相册", "image")

@index_bp.route('/paintings')
def paintings():
    """展示【我的绘画作品】页面，展示全部图片"""
    return render_gallery_page("我的绘画作品", "我的绘画作品", "image")

@index_bp.route('/audios')
def audios():
    """展示【音乐和弹唱作品】页面，展示全部音频文件"""
    return render_gallery_page("音乐和弹唱作品", "音乐和弹唱作品", "audio")

@index_bp.route('/ebooks')
def ebooks():
    """展示【电子书和论文】页面，展示全部电子书及论文"""
    return render_gallery_page("电子书论文", "电子书和论文", "ebook")

###########################################################################
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

####################################################################
# 静态页面映射字典（URL标识符 -> (模板文件, 页面标题)）
STATIC_PAGE_MAPPING = {
    "lezhi": ("lezhi.html", "乐志"),
    "resume": ("resume.html", "Resume"),
    "aboutme": ("aboutme.html", "About Me"),
    "study": ("study.html", "课题方向"),
    "interest": ("interest.html", "最近在做的事和兴趣"),
}

# 占位页面映射字典（URL标识符 -> 功能显示名称）
PLACEHOLDER_MAPPING = {
    "message_board": "留言板板",
    "survey": "问卷调查",
    "chat": "聊天机器人",
    # 如果某个页面既存在于静态页面又存在于占位字典
    # 则建议以静态页面为准，避免冲突
    "store": "个人商店",  
    "consultation": "咨询预约",
    "feedback": "意见反馈", 
    "pdf_translate": "PDF 翻译",
}

@index_bp.route('/<page>')
def dynamic_page(page):
    """
    统一处理静态页面与占位页面：
    - 若 page 存在于 STATIC_PAGE_MAPPING，则返回对应静态模板
    - 若 page 存在于 PLACEHOLDER_MAPPING，则返回通用占位模板 placeholder.html
    - 否则返回 404
    """
    # 静态页面优先处理
    if page in STATIC_PAGE_MAPPING:
        template, title = STATIC_PAGE_MAPPING[page]
        return render_template(template, title=title)
    # 处理占位页面
    elif page in PLACEHOLDER_MAPPING:
        feature_name = PLACEHOLDER_MAPPING[page]
        return render_template('placeholder.html', title=feature_name, feature_name=feature_name)
    else:
        abort(404)