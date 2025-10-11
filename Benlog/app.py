from flask import Flask
import os
import logging
from datetime import timedelta




def create_app():
    base_dir = os.path.abspath(os.path.dirname(__file__))
    
    app = Flask(__name__,
                instance_relative_config=True,
                template_folder=os.path.join(base_dir, 'templates'),
                static_folder=os.path.join(base_dir, 'static'))

    app.config.from_mapping(
        SECRET_KEY='default-secret-key',
        SQLALCHEMY_DATABASE_URI='sqlite:///' + os.path.join(app.instance_path, 'site.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        DEBUG=False,
        DOC_CREATION_PASSWORD='0715',
        REMEMBER_COOKIE_DURATION=timedelta(days=30),
        MAX_CONTENT_LENGTH=64 * 1024 * 1024,  # 64MB upload limit
        OSS_ACCESS_KEY_ID     = '',
        OSS_ACCESS_KEY_SECRET = '',
        OSS_ENDPOINT          = 'oss-cn-shanghai-internal.aliyuncs.com',
        OSS_BUCKET_NAME       = '',





    )
    

    app.config.from_pyfile('config.py', silent=True)
    
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass


    from Blog import blog_bp
    from Edu import edu_bp
    from Index import index_bp
    from Neibr import neibr_bp 
    from Neibr import init_app as neibr_init_app
    from Settings import init_app as settings_init_app
    from Settings import setting_bp
    from Gallery import gallery_bp

    app.register_blueprint(index_bp)
    app.register_blueprint(blog_bp, url_prefix='/blog')
    app.register_blueprint(edu_bp, url_prefix='/edu')
    app.register_blueprint(neibr_bp, url_prefix='/neibr')
    app.register_blueprint(setting_bp, url_prefix='/setting')
    app.register_blueprint(gallery_bp, url_prefix='/gallery')


    settings_init_app(app)
    neibr_init_app(app)

    app.logger.setLevel(logging.DEBUG)
    logging.basicConfig(level=logging.DEBUG)

    return app


def main():
    app = create_app()
    app.run(host='0.0.0.0', port=80)

if __name__ == '__main__':
    main()
