from flask_sqlalchemy import SQLAlchemy

# 初始化 SQLAlchemy 實例
db = SQLAlchemy()

# 導出所有 Model 類別，方便外部載入
from app.models.user import User
from app.models.shift import Shift
from app.models.leave import Leave

__all__ = ['db', 'User', 'Shift', 'Leave']
