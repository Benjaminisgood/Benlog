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





















DYNAMIC_PAGES_FOLDER = os.path.abspath(
    os.path.join(os.path.dirname(__file__), 'dynamic_pages')
)
if not os.path.exists(DYNAMIC_PAGES_FOLDER):
    raise FileNotFoundError(f"目录 {DYNAMIC_PAGES_FOLDER} 不存在！")

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
    管理员编辑：
      GET  渲染编辑表单
      POST 保存 JSON 并重定向（文件名可改）
    """
    json_path = os.path.join(DYNAMIC_PAGES_FOLDER, f"{page}.json")
    if not os.path.exists(json_path):
        abort(404, "页面不存在")

    data = json.load(open(json_path, 'r', encoding='utf-8'))
    # 组装组件列表
    page_components = [
        data[key] for key in sorted(
            [k for k in data if k.isdigit()], key=lambda x: int(x)
        )
    ]
    # 取 filename，若无则用 URL 参数
    filename = data.get('filename', page)

    if request.method == 'POST':
        # 从表单读取新的文件名（可为空则保持不变）
        new_filename = request.form['filename'].strip() or filename
        data['filename'] = new_filename

        # 重构 JSON，只保留 filename + 数字键组件
        new_data = {'filename': new_filename}
        count = int(request.form.get('elements_count', 0))
        for i in range(1, count + 1):
            prefix = f"elements-{i}-"
            ctype = request.form.get(prefix + 'type')
            if not ctype:
                continue
            comp = {'type': ctype}
            for k, v in request.form.items():
                if k.startswith(prefix) and k != prefix + 'type':
                    field = k[len(prefix):]
                    comp[field] = v.strip()
            new_data[str(i)] = comp

        # 写回 JSON
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(new_data, f, ensure_ascii=False, indent=4)
        flash("页面已保存！", "success")
        return redirect(url_for('index.dynamic_page', page=new_filename))

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

























