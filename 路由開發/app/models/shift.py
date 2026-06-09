from datetime import datetime, timedelta
from sqlalchemy import and_, or_
from app.models import db

class Shift(db.Model):
    """
    工作班表模型
    """
    __tablename__ = 'shifts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(100), nullable=False)  # 例如 '早班', '晚班'
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    staff_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # NULL 代表空班/缺工
    is_draft = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        staff_name = self.staff.name if self.staff else '缺工'
        return f"<Shift {self.title}: {self.start_time} - {self.end_time} ({staff_name})>"

    # --- 屬性/計算方法 ---
    @property
    def duration_hours(self):
        """計算此班次的工時長度 (小時)"""
        diff = self.end_time - self.start_time
        return diff.total_seconds() / 3600.0

    # --- 靜態/類別輔助商務邏輯方法 ---
    @classmethod
    def get_user_daily_hours(cls, user_id, target_date):
        """
        計算特定員工在特定日期的總排班工時 (排除已刪除的班次)
        target_date 可為 datetime.date 或 datetime.datetime 物件
        """
        if isinstance(target_date, datetime):
            target_date = target_date.date()
        
        start_of_day = datetime.combine(target_date, datetime.min.time())
        end_of_day = datetime.combine(target_date, datetime.max.time())

        shifts = cls.query.filter(
            cls.staff_id == user_id,
            cls.is_deleted == False,
            cls.start_time >= start_of_day,
            cls.start_time <= end_of_day
        ).all()

        return sum(shift.duration_hours for shift in shifts)

    @classmethod
    def get_user_weekly_hours(cls, user_id, target_date):
        """
        計算特定員工在特定日期所在週的總排班工時 (週一至週日，排除已刪除)
        """
        if isinstance(target_date, datetime):
            target_date = target_date.date()
        
        # 找出該週週一的日期 (Monday is 0, Sunday is 6)
        monday = target_date - timedelta(days=target_date.weekday())
        start_of_week = datetime.combine(monday, datetime.min.time())
        end_of_week = datetime.combine(monday + timedelta(days=6), datetime.max.time())

        shifts = cls.query.filter(
            cls.staff_id == user_id,
            cls.is_deleted == False,
            cls.start_time >= start_of_week,
            cls.start_time <= end_of_week
        ).all()

        return sum(shift.duration_hours for shift in shifts)

    @classmethod
    def check_scheduling_conflict(cls, user_id, start_time, end_time, exclude_shift_id=None):
        """
        檢查某員工在指定時間範圍內是否有排班衝突 (重疊、請假或偏好限制)
        回傳: (是否有衝突 Boolean, 衝突訊息 String)
        """
        from app.models.user import User
        from app.models.leave import Leave

        user = User.get_by_id(user_id)
        if not user:
            return True, "找不到該員工或員工已被刪除"

        # 1. 檢查不可上班偏好
        pref = user.get_preferences()
        unavailable_days = pref.get("unavailable_days", [])
        
        current_time = start_time
        while current_time <= end_time:
            pref_day = (current_time.weekday() + 1) % 7
            if pref_day in unavailable_days:
                return True, f"員工 {user.name} 於星期 {pref_day} (日歷代碼) 設定為不可上班時段"
            current_time += timedelta(days=1)

        # 2. 檢查請假記錄是否重疊 (僅 Approved 的假單算衝突)
        overlapping_leave = Leave.query.filter(
            Leave.staff_id == user_id,
            Leave.status == 'Approved',
            Leave.is_deleted == False,
            or_(
                and_(Leave.start_time <= start_time, Leave.end_time > start_time),
                and_(Leave.start_time < end_time, Leave.end_time >= end_time),
                and_(Leave.start_time >= start_time, Leave.end_time <= end_time)
            )
        ).first()
        if overlapping_leave:
            return True, f"與已核准的請假時間衝突 ({overlapping_leave.leave_type})"

        # 3. 檢查是否有已排定且時間重疊的班次 (排除自己)
        query = cls.query.filter(
            cls.staff_id == user_id,
            cls.is_deleted == False,
            or_(
                and_(cls.start_time <= start_time, cls.end_time > start_time),
                and_(cls.start_time < end_time, cls.end_time >= end_time),
                and_(cls.start_time >= start_time, cls.end_time <= end_time)
            )
        )
        if exclude_shift_id:
            query = query.filter(cls.id != exclude_shift_id)

        overlapping_shift = query.first()
        if overlapping_shift:
            return True, f"與現有班次 {overlapping_shift.title} 時間重疊"

        # 4. 檢查每日工時上限限制
        current_daily_hours = cls.get_user_daily_hours(user_id, start_time)
        new_shift_hours = (end_time - start_time).total_seconds() / 3600.0
        if current_daily_hours + new_shift_hours > user.max_daily_hours:
            return True, f"排班後單日工時將達 {current_daily_hours + new_shift_hours:.1f} 小時，超過上限 {user.max_daily_hours} 小時"

        # 5. 檢查每週工時上限限制
        current_weekly_hours = cls.get_user_weekly_hours(user_id, start_time)
        if current_weekly_hours + new_shift_hours > user.max_weekly_hours:
            return True, f"排班後當週總工時將達 {current_weekly_hours + new_shift_hours:.1f} 小時，超過上限 {user.max_weekly_hours} 小時"

        return False, ""

    # --- CRUD 方法 (遵循 db-design 規範) ---
    @classmethod
    def create(cls, title, start_time, end_time, staff_id=None, is_draft=True):
        """建立新班次"""
        if staff_id:
            has_conflict, msg = cls.check_scheduling_conflict(staff_id, start_time, end_time)
            if has_conflict:
                raise ValueError(f"排班衝突警告: {msg}")

        shift = cls(
            title=title,
            start_time=start_time,
            end_time=end_time,
            staff_id=staff_id,
            is_draft=is_draft
        )
        db.session.add(shift)
        db.session.commit()
        return shift

    @classmethod
    def get_all(cls, include_deleted=False, is_draft=None):
        """取得所有排班"""
        query = cls.query
        if not include_deleted:
            query = query.filter_by(is_deleted=False)
        if is_draft is not None:
            query = query.filter_by(is_draft=is_draft)
        return query.all()

    @classmethod
    def get_by_id(cls, shift_id):
        """根據 ID 取得班表"""
        return cls.query.filter_by(id=shift_id, is_deleted=False).first()

    @classmethod
    def get_shifts_by_range(cls, start_time, end_time, include_deleted=False, is_draft=None):
        """根據時間區間取得班表 (通常給 FullCalendar 使用)"""
        query = cls.query.filter(
            cls.start_time >= start_time,
            cls.end_time <= end_time
        )
        if not include_deleted:
            query = query.filter(cls.is_deleted == False)
        if is_draft is not None:
            query = query.filter_by(is_draft=is_draft)
        return query.all()

    def update(self, **kwargs):
        """更新班表資訊"""
        new_staff_id = kwargs.get('staff_id', self.staff_id)
        new_start = kwargs.get('start_time', self.start_time)
        new_end = kwargs.get('end_time', self.end_time)

        if new_staff_id and (new_staff_id != self.staff_id or new_start != self.start_time or new_end != self.end_time):
            has_conflict, msg = self.check_scheduling_conflict(new_staff_id, new_start, new_end, exclude_shift_id=self.id)
            if has_conflict:
                raise ValueError(f"排班衝突警告: {msg}")

        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        db.session.commit()
        return self

    def delete(self):
        """軟刪除班表"""
        self.is_deleted = True
        db.session.commit()
        return True
