from datetime import datetime
from sqlalchemy import and_, or_
from app.models import db

class Leave(db.Model):
    """
    員工請假申請與審核模型
    """
    __tablename__ = 'leaves'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    leave_type = db.Column(db.String(50), nullable=False)  # 'Vacation', 'Sick', 'Personal'
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='Pending', nullable=False)  # 'Pending', 'Approved', 'Rejected'
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    reviewer = db.relationship('User', foreign_keys=[reviewed_by], backref='reviewed_leaves', lazy=True)

    def __repr__(self):
        return f"<Leave {self.staff.name}: {self.leave_type} ({self.status})>"

    # --- 審核業務邏輯方法 (遵循 Sequence Diagram 設計) ---
    def approve(self, reviewer_id):
        """
        核准請假：
        1. 變更假單狀態為 'Approved'
        2. 記錄審核店長與審核時間
        3. 自動搜尋請假時間區間內該員工已排定的班次，並將該些班次設為「空班/缺工」狀態，以便店長重新調度
        """
        from app.models.shift import Shift

        self.status = 'Approved'
        self.reviewed_by = reviewer_id
        self.reviewed_at = datetime.utcnow()

        affected_shifts = Shift.query.filter(
            Shift.staff_id == self.staff_id,
            Shift.is_deleted == False,
            or_(
                and_(Shift.start_time <= self.start_time, Shift.end_time > self.start_time),
                and_(Shift.start_time < self.end_time, Shift.end_time >= self.end_time),
                and_(Shift.start_time >= self.start_time, Shift.end_time <= self.end_time)
            )
        ).all()

        for shift in affected_shifts:
            shift.staff_id = None
            shift.is_draft = True

        db.session.commit()
        return self

    def reject(self, reviewer_id, comment=None):
        """拒絕請假"""
        self.status = 'Rejected'
        self.reviewed_by = reviewer_id
        self.reviewed_at = datetime.utcnow()
        if comment:
            self.reason = f"{self.reason or ''} (店長退回備註: {comment})".strip()
        
        db.session.commit()
        return self

    # --- CRUD 方法 (遵循 db-design 規範) ---
    @classmethod
    def create(cls, staff_id, start_time, end_time, leave_type, reason=None):
        """送出請假申請"""
        overlapping = cls.query.filter(
            cls.staff_id == staff_id,
            cls.status == 'Approved',
            cls.is_deleted == False,
            or_(
                and_(cls.start_time <= start_time, cls.end_time > start_time),
                and_(cls.start_time < end_time, cls.end_time >= end_time),
                and_(cls.start_time >= start_time, cls.end_time <= end_time)
            )
        ).first()

        if overlapping:
            raise ValueError(f"此員工在此區間已有核准的請假 ({overlapping.leave_type})，不可重複申請")

        leave = cls(
            staff_id=staff_id,
            start_time=start_time,
            end_time=end_time,
            leave_type=leave_type,
            reason=reason,
            status='Pending'
        )
        db.session.add(leave)
        db.session.commit()
        return leave

    @classmethod
    def get_all(cls, include_deleted=False, status=None):
        """取得所有假單"""
        query = cls.query
        if not include_deleted:
            query = query.filter_by(is_deleted=False)
        if status:
            query = query.filter_by(status=status)
        return query.all()

    @classmethod
    def get_by_id(cls, leave_id):
        """根據 ID 取得請假單"""
        return cls.query.filter_by(id=leave_id, is_deleted=False).first()

    @classmethod
    def get_leaves_by_user(cls, user_id, include_deleted=False):
        """取得特定員工的所有請假單紀錄"""
        query = cls.query.filter_by(staff_id=user_id)
        if not include_deleted:
            query = query.filter_by(is_deleted=False)
        return query.all()

    def update(self, **kwargs):
        """更新請假資訊"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        db.session.commit()
        return self

    def delete(self):
        """軟刪除假單"""
        self.is_deleted = True
        db.session.commit()
        return True
