# 儲存路徑: 路由開發/app/routes/api.py
from datetime import datetime
from flask import jsonify, request, session
from app.routes import api_bp
from app.models.shift import Shift
from app.models.user import User
from app.routes.auth import login_required, manager_required

@api_bp.route('/shifts', methods=['GET'])
@login_required
def get_shifts_api():
    """
    提供給 FullCalendar.js 的非同步排班資料 API
    讀取查詢參數 start 與 end，回傳該日期區間內的所有排班事件
    若是員工角色，將自動過濾 is_draft=True 的草稿班表
    :return: JSON 格式之班表陣列
    """
    start_str = request.args.get('start')
    end_str = request.args.get('end')

    if not start_str or not end_str:
        return jsonify({"error": "Missing start or end query parameters"}), 400

    try:
        # 移除可能帶有 'Z' 的時間格式以方便 python 解析
        if 'T' in start_str:
            start_time = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
        else:
            start_time = datetime.strptime(start_str, '%Y-%m-%d')
            end_time = datetime.strptime(end_str, '%Y-%m-%d')
    except Exception as e:
        return jsonify({"error": f"Invalid date format: {str(e)}"}), 400

    role = session.get('role')
    user_id = session.get('user_id')

    # 查詢該時間區間內的班次
    if role == 'manager':
        shifts = Shift.get_shifts_by_range(start_time, end_time, include_deleted=False)
    else:
        # 一般員工只能看到已發佈的班表 (is_draft=False)
        shifts = Shift.get_shifts_by_range(start_time, end_time, include_deleted=False, is_draft=False)

    events = []
    for shift in shifts:
        staff_name = shift.staff.name if shift.staff else '缺工/空班'
        
        # 定義顏色：
        # 紅色 (#dc3545) = 缺工
        # 橘黃色 (#ffc107) = 草稿 (店長專屬)
        # 綠色 (#28a745) = 正式班表
        if not shift.staff_id:
            color = "#dc3545"
        elif shift.is_draft:
            color = "#ffc107"
        else:
            color = "#28a745"

        events.append({
            "id": shift.id,
            "title": f"{shift.title} - {staff_name}",
            "start": shift.start_time.isoformat(),
            "end": shift.end_time.isoformat(),
            "color": color,
            "textColor": "#ffffff" if color != "#ffc107" else "#212529",
            "extendedProps": {
                "is_draft": shift.is_draft,
                "staff_id": shift.staff_id,
                "title_only": shift.title
            }
        })

    return jsonify(events)

@api_bp.route('/shift/update', methods=['POST'])
@manager_required
def update_shift_api():
    """
    店長在 FullCalendar 上進行拖拉修改或人員替換時的 AJAX API
    接收 JSON 格式之 shift_id、start_time、end_time 與 staff_id。
    後端在寫入前將自動觸發 `check_scheduling_conflict` 進行動態合規與缺工預檢
    - 若完全合規：寫入資料庫，回傳 status: 'success'
    - 若違反限制（例如超過工時）：不寫入資料庫，回傳 status: 'warning/error' 及具體原因，讓前端日曆顯示高亮警告
    :return: 預檢結果之 JSON 回應
    """
    data = request.get_json() or {}
    shift_id = data.get('shift_id')
    staff_id = data.get('staff_id')
    start_time_str = data.get('start_time')
    end_time_str = data.get('end_time')
    title = data.get('title')

    if not shift_id:
        return jsonify({"status": "error", "message": "缺少班次 ID"}), 400

    shift = Shift.get_by_id(shift_id)
    if not shift:
        return jsonify({"status": "error", "message": "找不到該班次"}), 404

    # 處理空班指派
    if staff_id == "null" or staff_id == "None" or staff_id == "" or staff_id is None:
        actual_staff_id = None
    else:
        try:
            actual_staff_id = int(staff_id)
        except ValueError:
            return jsonify({"status": "error", "message": "員工 ID 格式不正確"}), 400

    # 支援班次刪除
    if data.get('delete') is True:
        try:
            shift.delete()
            return jsonify({"status": "success", "message": "班次已成功刪除！"})
        except Exception as e:
            return jsonify({"status": "error", "message": f"刪除失敗: {str(e)}"}), 500

    # 準備更新參數
    update_data = {}
    if title:
        update_data['title'] = title
    if start_time_str:
        update_data['start_time'] = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
    if end_time_str:
        update_data['end_time'] = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
    
    update_data['staff_id'] = actual_staff_id

    try:
        # 更新並執行排班防錯檢查
        shift.update(**update_data)
        return jsonify({"status": "success", "message": "班次更新成功！"})
    except ValueError as e:
        # 排班衝突、工時超標等商業邏輯警告
        return jsonify({"status": "warning", "message": str(e)})
    except Exception as e:
        return jsonify({"status": "error", "message": f"系統錯誤: {str(e)}"}), 500
