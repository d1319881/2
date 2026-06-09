import json
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import db

class User(db.Model):
    """
    使用者與員工資料表模型
    """
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='staff', nullable=False)  # 'manager' or 'staff'
    max_weekly_hours = db.Column(db.Float, default=40.0, nullable=False)
    max_daily_hours = db.Column(db.Float, default=8.0, nullable=False)
    preferences = db.Column(db.Text, nullable=True)  # 儲存 JSON 字串
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # 關聯設定 (一個員工有多個班次與請假單)
    shifts = db.relationship('Shift', backref='staff', lazy=True)
    leaves = db.relationship('Leave', foreign_keys='Leave.staff_id', backref='staff', lazy=True)

    def __repr__(self):
        return f"<User {self.name} ({self.role})>"

    # --- 密碼安全方法 ---
    def set_password(self, password):
        """將明文密碼進行雜湊後儲存"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """驗證輸入的密碼是否正確"""
        return check_password_hash(self.password_hash, password)

    # --- 偏好設定 JSON 解析方法 ---
    def get_preferences(self):
        """取得員工的排班偏好設定字典"""
        if not self.preferences:
            return {
                "unavailable_days": [],    # [0, 6] 代表週日與週六不可排班 (0=週日, 1=週一... 6=週六)
                "preferred_shifts": []     # 偏好班別名稱，如 ["早班", "中班"]
            }
        try:
            return json.loads(self.preferences)
        except (ValueError, TypeError):
            return {"unavailable_days": [], "preferred_shifts": []}

    def set_preferences(self, pref_dict):
        """設定並序列化員工排班偏好"""
        self.preferences = json.dumps(pref_dict, ensure_ascii=False)

    # --- CRUD 方法 (遵循 db-design 規範) ---
    @classmethod
    def create(cls, username, password, name, role='staff', max_weekly_hours=40.0, max_daily_hours=8.0, preferences=None):
        """新增使用者"""
        # 檢查帳號是否重複
        if cls.query.filter_by(username=username).first():
            return None
        
        user = cls(
            username=username,
            name=name,
            role=role,
            max_weekly_hours=max_weekly_hours,
            max_daily_hours=max_daily_hours
        )
        user.set_password(password)
        if preferences:
            user.set_preferences(preferences)
        
        db.session.add(user)
        db.session.commit()
        return user

    @classmethod
    def get_all(cls, include_deleted=False):
        """取得所有員工 (預設過濾已軟刪除者)"""
        if include_deleted:
            return cls.query.all()
        return cls.query.filter_by(is_deleted=False).all()

    @classmethod
    def get_by_id(cls, user_id):
        """根據 ID 取得使用者"""
        return cls.query.filter_by(id=user_id, is_deleted=False).first()

    def update(self, **kwargs):
        """更新使用者資料"""
        for key, value in kwargs.items():
            if key == 'password':
                self.set_password(value)
            elif key == 'preferences':
                self.set_preferences(value)
            elif hasattr(self, key):
                setattr(self, key, value)
        db.session.commit()
        return self

    def delete(self):
        """軟刪除使用者"""
        self.is_deleted = True
        db.session.commit()
        return True
