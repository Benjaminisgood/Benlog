from flask import Flask
import os

def create_app():
    # 获取当前文件（app.py）所在的目录的绝对路径
    base_dir = os.path.abspath(os.path.dirname(__file__))
    
    # 创建 Flask 应用
    # 如果需要从 instance 目录加载配置，可以设置 instance_relative_config=True
    app = Flask(__name__,
                instance_relative_config=True,  # 使 Flask 从 instance 目录加载配置文件
                template_folder=os.path.join(base_dir, 'templates'),  # 指定全局模板路径
                static_folder=os.path.join(base_dir, 'static'))         # 指定全局静态文件路径

    # 使用 from_mapping() 加载默认配置
    app.config.from_mapping(
        # 设置默认密钥，生产环境应覆盖这个配置
        SECRET_KEY='default-secret-key',
        # 默认使用 SQLite 数据库
        SQLALCHEMY_DATABASE_URI='sqlite:///' + os.path.join(app.instance_path, 'site.db'),
        # 禁用 SQLAlchemy 的修改跟踪
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        # 其他默认配置项，如调试开关、文档创建密码等
        DEBUG=False,
        DOC_CREATION_PASSWORD='0715'
    )
    
    # 尝试加载用户在 instance/config.py 中提供的配置，
    # 若该文件存在，其内容会覆盖上面的默认配置
    app.config.from_pyfile('config.py', silent=True)
    
    # 确保 instance 文件夹存在（Flask 会将其用作存放私有数据的目录）
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass


    # 注册蓝图
    from Blog import blog_bp
    from Edu import edu_bp
    from Index import index_bp
    from Neibr import neibr_bp, init_app  
      
    app.register_blueprint(index_bp)               # Index blueprint on the root
    app.register_blueprint(blog_bp, url_prefix='/blog')
    app.register_blueprint(edu_bp, url_prefix='/edu')
    app.register_blueprint(neibr_bp, url_prefix='/neibr')

# 初始化 Neibr 模块的数据库和登录管理
    init_app(app)
    
    return app


def main():
    # 创建应用实例
    app = create_app()
    # 根据实际情况，生产环境中不建议启用 debug 模式
    app.run(host='0.0.0.0', port=80)

if __name__ == '__main__':
    main()
