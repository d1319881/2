# 儲存路徑: 路由開發/app/utils/scheduler.py
from datetime import datetime, timedelta, time
from app.models import db
from app.models.user import User
from app.models.shift import Shift

class AutoScheduler:
    @staticmethod
    def run_auto_schedule(start_date_str, end_date_str):
        """
        智慧自動排班引擎
        :param start_date_str: 'YYYY-MM-DD'
        :param end_date_str: 'YYYY-MM-DD'
        :return: 建立的 Shift 物件清單
        """
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
        # 取得所有非管理員員工
        staffs = User.query.filter_by(role='staff', is_deleted=False).all()
        
        created_shifts = []
        current_date = start_date
        
        # 定義每日預設班表人力需求
        # 早班 08:00 - 16:00 (需要 2 人)
        # 晚班 16:00 - 24:00 (需要 2 人)
        shift_templates = [
            {"title": "早班", "start_time": time(8, 0), "end_time": time(16, 0), "slots": 2},
            {"title": "晚班", "start_time": time(16, 0), "end_time": time(0, 0), "slots": 2}
        ]
        
        while current_date <= end_date:
            for temp in shift_templates:
                # 處理跨日班表 (如 16:00 - 24:00)
                shift_start = datetime.combine(current_date, temp["start_time"])
                if temp["end_time"] == time(0, 0):
                    shift_end = datetime.combine(current_date + timedelta(days=1), time(0, 0))
                else:
                    shift_end = datetime.combine(current_date, temp["end_time"])
                
                # 對於每個槽位，找尋合適員工
                for slot in range(temp["slots"]):
                    assigned_staff_id = None
                    
                    # 篩選沒有衝突的候選人
                    candidates = []
                    for staff in staffs:
                        # 檢查衝突 (不可上班、重複、請假、日限、週限)
                        has_conflict, _ = Shift.check_scheduling_conflict(staff.id, shift_start, shift_end)
                        if not has_conflict:
                            # 計算目前該週已排定工時 (用於平均分配)
                            weekly_hours = Shift.get_user_weekly_hours(staff.id, shift_start)
                            
                            # 檢查偏好
                            pref = staff.get_preferences()
                            preferred_shifts = pref.get("preferred_shifts", [])
                            is_preferred = temp["title"] in preferred_shifts
                            
                            candidates.append({
                                "staff": staff,
                                "weekly_hours": weekly_hours,
                                "is_preferred": is_preferred
                            })
                    
                    if candidates:
                        # 排序策略：
                        # 1. 優先選擇偏好此班別的員工 (is_preferred 降序)
                        # 2. 優先選擇目前排班時數較少的員工 (weekly_hours 升序)
                        candidates.sort(key=lambda x: (not x["is_preferred"], x["weekly_hours"]))
                        selected_staff = candidates[0]["staff"]
                        assigned_staff_id = selected_staff.id
                        
                        # 建立並先暫時加入 session 以供下一輪 check_scheduling_conflict 能看得到工時累加
                        temp_shift = Shift(
                            title=temp["title"],
                            start_time=shift_start,
                            end_time=shift_end,
                            staff_id=assigned_staff_id,
                            is_draft=True
                        )
                        db.session.add(temp_shift)
                        created_shifts.append(temp_shift)
                    else:
                        # 缺工/無合適人選，直接建立空班以供後續店長手動微調
                        temp_shift = Shift(
                            title=temp["title"],
                            start_time=shift_start,
                            end_time=shift_end,
                            staff_id=None,
                            is_draft=True
                        )
                        db.session.add(temp_shift)
                        created_shifts.append(temp_shift)
            
            current_date += timedelta(days=1)
            
        db.session.commit()
        return created_shifts
