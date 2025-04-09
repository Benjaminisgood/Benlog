from setuptools import setup, find_packages

setup(
    name="Benlog",
    version="0.1.0",
    # 自动查找所有包（含 __init__.py 的目录），比如 Blog、Edu、Index、Neibr
    packages=find_packages(),
    # 将顶层的 app.py 文件也作为模块打包
    include_package_data=True,
    install_requires=[
        "Flask",
        "markdown",
        "python-frontmatter",
        "Flask-SQLAlchemy",
        "flask-login",
        "flask-migrate",
        "gunicorn",
        "requests",
        "pymdown-extensions",
        "openai"
    ],
    entry_points={
        "console_scripts": [
            # 指定命令行入口：用户在安装后执行 'benlog' 命令即调用 app.py 中的 main() 函数
            "benlog=Benlog.app:main",
        ],
    },
    author="Ben",
    author_email="1093158714@qq.com",
    url="http://benjaling.icu",  # 或者其他项目主页地址
)