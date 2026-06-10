# 儲存路徑: 路由開發/app/routes/__init__.py
from flask import Blueprint

# 定義各功能模組的 Blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
main_bp = Blueprint('main', __name__)
schedule_bp = Blueprint('schedule', __name__, url_prefix='/schedule')
leave_bp = Blueprint('leave', __name__)
api_bp = Blueprint('api', __name__, url_prefix='/api')

def register_blueprints(app):
    """
    在 Flask app 實例中註冊所有的 Blueprint 路由
    """
    # 導入各個路由模組以使路由裝飾器生效
    from app.routes import auth, main, schedule, leave, api

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(schedule_bp)
    app.register_blueprint(leave_bp)
    app.register_blueprint(api_bp)
