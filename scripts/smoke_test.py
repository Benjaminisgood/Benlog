#!/usr/bin/env python3
"""Start Benlog against a temporary SQLite database and exercise the main path.

Usage (from the repository root, with dependencies installed):

    python scripts/smoke_test.py
"""

import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
EMAIL = 'smoke-admin@example.com'
USERNAME = 'smokeadmin'
PASSWORD = 'smoke-test-pass-123'
MARKER = 'Smoke test hello'
XSS = '<script>alert(1)</script>'


def _free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def _wait_until(url, proc, timeout=30):
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f'服务提前退出，退出码 {proc.returncode}')
        try:
            response = requests.get(url, timeout=1)
            if response.status_code < 500:
                return response
        except requests.RequestException as exc:
            last_error = exc
        time.sleep(0.3)
    raise RuntimeError(f'等待服务超时: {last_error}')


def _csrf(html):
    match = re.search(r'name="csrf-token" content="([^"]+)"', html)
    if not match:
        raise AssertionError('页面里没有 CSRF token')
    return match.group(1)


def main():
    port = _free_port()
    base = f'http://127.0.0.1:{port}'
    with tempfile.TemporaryDirectory(prefix='benlog-smoke-') as tmp:
        env = os.environ.copy()
        env.update({
            'BENLOG_INSTANCE_PATH': tmp,
            'DATABASE_URL': 'sqlite:///' + str(Path(tmp) / 'site.db'),
            'SECRET_KEY': 'smoke-test-secret-key',
            'FLASK_DEBUG': '0',
            'ADMIN_EMAIL': EMAIL,
            'ADMIN_USERNAME': USERNAME,
            'ADMIN_PASSWORD': PASSWORD,
            'ALLOW_REGISTRATION': '0',
            'STORAGE_BACKEND': 'local',
            'HOST': '127.0.0.1',
            'PORT': str(port),
        })
        env.pop('FLASK_RUN_FROM_CLI', None)
        proc = subprocess.Popen(
            [sys.executable, '-m', 'flask', '--app', 'Benlog.app:create_app', 'run',
             '--host', '127.0.0.1', '--port', str(port), '--no-reload'],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            home = _wait_until(base + '/', proc)
            assert home.status_code == 200, home.status_code
            assert 'Benlog' in home.text

            session = requests.Session()
            login_page = session.get(base + '/setting/login', timeout=10)
            assert login_page.status_code == 200
            token = _csrf(login_page.text)
            logged_in = session.post(
                base + '/setting/login',
                data={'email': EMAIL, 'password': PASSWORD, 'csrf_token': token},
                timeout=10,
                allow_redirects=False,
            )
            assert logged_in.status_code in (302, 303), logged_in.text[:300]
            assert 'session' in logged_in.headers.get('Set-Cookie', '').lower() or session.cookies

            blog = session.get(base + '/blog/', timeout=10)
            assert blog.status_code == 200, blog.text[:300]
            created = session.post(
                base + '/blog/new',
                data={'csrf_token': _csrf(blog.text)},
                timeout=10,
                allow_redirects=False,
            )
            assert created.status_code in (302, 303), created.text[:400]
            edit_url = created.headers['Location']
            if edit_url.startswith('/'):
                edit_url = base + edit_url
            editor = session.get(edit_url, timeout=10)
            assert editor.status_code == 200, editor.text[:400]
            assert 'markdown' in editor.text.lower() or '正文' in editor.text

            saved = session.post(
                edit_url,
                data={
                    'csrf_token': _csrf(editor.text),
                    'title': '冒烟测试',
                    'summary': '一条用于检查的文章',
                    'tags': 'smoke',
                    'cover': '',
                    'status': 'published',
                    'content': f'# 标题\n\n{MARKER}\n\n{XSS}\n',
                },
                timeout=10,
                allow_redirects=False,
            )
            assert saved.status_code in (302, 303), saved.text[:400]
            view_url = saved.headers['Location']
            if view_url.startswith('/'):
                view_url = base + view_url
            article = session.get(view_url, timeout=10)
            assert article.status_code == 200, article.text[:400]
            assert MARKER in article.text
            article_body = re.search(r'class="markdown-body">(.*?)</article>', article.text, re.S)
            assert article_body, '文章正文没有渲染出来'
            fragment = article_body.group(1).lower()
            assert '<script' not in fragment
            assert 'javascript:' not in fragment
            assert '冒烟测试' in article.text

            edited = session.get(edit_url, timeout=10)
            assert MARKER in edited.text

            again = session.get(base + '/', timeout=10)
            assert again.status_code == 200
            assert 'Benlog' in again.text
            print('smoke test ok')
        except Exception:
            output = ''
            if proc.stdout:
                try:
                    proc.kill()
                    output = proc.stdout.read() or ''
                except Exception:
                    output = ''
            if output:
                print(output[-4000:], file=sys.stderr)
            raise
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()


if __name__ == '__main__':
    main()
