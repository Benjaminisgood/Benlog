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

    return render_template(
        'index.html',
        quick_links=quick_links,
        friend_links=friend_links,
        title="首页"
    )

























