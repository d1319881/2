# 儲存路徑: 路由開發/app/routes/main.py
from datetime import datetime, time, timedelta
from flask import render_template, redirect, url_for, session, request, flash
from app.routes import main_bp
from app.models.leave import Leave
from app.models.shift import Shift
from app.models.user import User
from app.routes.auth import login_required, manager_required

@main_bp.route('/', methods=['GET'])
def index():
    """
    系統首頁分流控制器
    :return: 根據 Session 角色重導向至店長或員工儀表板；未登入重導向至 /auth/login
    """
    if 'user_id' not in session:
        return redirect(url_for('auth.login_page'))
    
    role = session.get('role')
    if role == 'manager':
        return redirect(url_for('main.manager_dashboard'))
    elif role == 'staff':
        return redirect(url_for('main.staff_dashboard'))
    else:
        session.clear()
        return redirect(url_for('auth.login_page'))

@main_bp.route('/dashboard/manager', methods=['GET'])
@manager_required
def manager_dashboard():
    """
    顯示店長後台管理儀表板
    包含：今日缺工警示、今日出勤人數統計、待審核請假數量、今日班表名單
    :return: 渲染 templates/main/dashboard.html (管理員版面)
    """
    # 取得今日日期區間 (以伺服器/本地時間為準)
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, time.min)
    today_end = datetime.combine(today, time.max)

    # 1. 待審核請假數量
    pending_leaves = Leave.get_all(status='Pending')
    pending_leaves_count = len(pending_leaves)

    # 2. 今日缺工班次 (staff_id 為 NULL 且是今日班表)
    understaffed_shifts = Shift.query.filter(
        Shift.staff_id == None,
        Shift.start_time >= today_start,
        Shift.start_time <= today_end,
        Shift.is_deleted == False
    ).all()

    # 3. 今日已排定班次 (今日出勤名單)
    assigned_shifts = Shift.query.filter(
        Shift.staff_id != None,
        Shift.start_time >= today_start,
        Shift.start_time <= today_end,
        Shift.is_deleted == False
    ).all()

    # 4. 今日出勤人數 (不重複的人數)
    attendance_count = len(set(shift.staff_id for shift in assigned_shifts if shift.staff_id))

    return render_template(
        'main/dashboard.html',
        role='manager',
        datetime_today=today.strftime('%Y-%m-%d'),
        pending_leaves_count=pending_leaves_count,
        understaffed_shifts=understaffed_shifts,
        assigned_shifts=assigned_shifts,
        attendance_count=attendance_count
    )

@main_bp.route('/dashboard/staff', methods=['GET'])
@login_required
def staff_dashboard():
    """
    顯示員工個人前台儀表板
    包含：個人當週排班表、請假審核狀態與歷史記錄
    :return: 渲染 templates/main/dashboard.html (一般員工版面)
    """
    user_id = session.get('user_id')

    # 計算當週週一至週日時間區間
    today = datetime.utcnow().date()
    monday = today - timedelta(days=today.weekday())
    start_of_week = datetime.combine(monday, time.min)
    end_of_week = datetime.combine(monday + timedelta(days=6), time.max)

    # 1. 個人當週已發佈班表 (is_draft 為 False)
    weekly_shifts = Shift.query.filter(
        Shift.staff_id == user_id,
        Shift.start_time >= start_of_week,
        Shift.start_time <= end_of_week,
        Shift.is_draft == False,
        Shift.is_deleted == False
    ).order_by(Shift.start_time.asc()).all()

    # 2. 個人請假審核狀態與歷史記錄
    leave_history = Leave.get_leaves_by_user(user_id)

    return render_template(
        'main/dashboard.html',
        role='staff',
        datetime_today=today.strftime('%Y-%m-%d'),
        weekly_shifts=weekly_shifts,
        leave_history=leave_history
    )

@main_bp.route('/employees', methods=['GET'])
@manager_required
def employee_management():
    """
    顯示店長員工管理頁面
    :return: 渲染 templates/employee/management.html
    """
    employees = User.get_all()
    return render_template('employee/management.html', employees=employees)

@main_bp.route('/employees/add', methods=['POST'])
@manager_required
def employee_add():
    """
    新增員工
    """
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    name = request.form.get('name', '').strip()
    role = request.form.get('role', 'staff').strip()
    max_weekly_hours = request.form.get('max_weekly_hours', '40.0')
    max_daily_hours = request.form.get('max_daily_hours', '8.0')

    if not username or not password or not name:
        flash('請填寫所有必要欄位 (帳號、密碼、姓名)。', 'danger')
        return redirect(url_for('main.employee_management'))

    try:
        max_weekly_hours = float(max_weekly_hours)
        max_daily_hours = float(max_daily_hours)
    except ValueError:
        flash('最大工時數值格式不正確。', 'danger')
        return redirect(url_for('main.employee_management'))

    user = User.create(
        username=username,
        password=password,
        name=name,
        role=role,
        max_weekly_hours=max_weekly_hours,
        max_daily_hours=max_daily_hours
    )

    if not user:
        flash('此帳號名稱已被註冊。', 'danger')
    else:
        flash(f'成功新增員工：{name}！', 'success')

    return redirect(url_for('main.employee_management'))

@main_bp.route('/employees/<int:user_id>/update', methods=['POST'])
@manager_required
def employee_update(user_id):
    """
    更新員工資料
    """
    user = User.get_by_id(user_id)
    if not user:
        flash('找不到該筆員工資料。', 'danger')
        return redirect(url_for('main.employee_management'))

    name = request.form.get('name', '').strip()
    role = request.form.get('role', 'staff').strip()
    max_weekly_hours = request.form.get('max_weekly_hours', '40.0')
    max_daily_hours = request.form.get('max_daily_hours', '8.0')

    if not name:
        flash('姓名不能為空。', 'danger')
        return redirect(url_for('main.employee_management'))

    try:
        max_weekly_hours = float(max_weekly_hours)
        max_daily_hours = float(max_daily_hours)
    except ValueError:
        flash('最大工時數值格式不正確。', 'danger')
        return redirect(url_for('main.employee_management'))

    user.update(
        name=name,
        role=role,
        max_weekly_hours=max_weekly_hours,
        max_daily_hours=max_daily_hours
    )
    flash(f'員工 {name} 的資料已更新！', 'success')
    return redirect(url_for('main.employee_management'))

@main_bp.route('/employees/<int:user_id>/delete', methods=['POST'])
@manager_required
def employee_delete(user_id):
    """
    軟刪除/停用員工
    """
    user = User.get_by_id(user_id)
    if not user:
        flash('找不到該筆員工資料。', 'danger')
        return redirect(url_for('main.employee_management'))

    # 防止自己刪除自己
    if user.id == session.get('user_id'):
        flash('您不能停用自己！', 'danger')
        return redirect(url_for('main.employee_management'))

    user.delete()
    flash(f'員工 {user.name} 已成功停用！', 'success')
    return redirect(url_for('main.employee_management'))
