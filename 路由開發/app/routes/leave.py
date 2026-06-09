# 儲存路徑: 路由開發/app/routes/leave.py
from datetime import datetime
from flask import render_template, redirect, url_for, request, flash, session
from app.routes import leave_bp
from app.models.leave import Leave
from app.models.shift import Shift
from app.routes.auth import login_required, manager_required

@leave_bp.route('/leave/apply', methods=['GET'])
@login_required
def leave_apply_page():
    """
    顯示員工請假申請表單頁面
    :return: 渲染 templates/leave/apply.html
    """
    if session.get('role') != 'staff':
        flash('僅限一般員工可以申請請假。', 'warning')
        return redirect(url_for('main.index'))
    return render_template('leave/apply.html')

@leave_bp.route('/leave/apply', methods=['POST'])
@login_required
def leave_apply():
    """
    處理員工請假表單提交
    :return: 申請成功重導向至 /dashboard/staff 並顯示成功提示；失敗則顯示衝突警告
    """
    if session.get('role') != 'staff':
        flash('僅限一般員工可以申請請假。', 'warning')
        return redirect(url_for('main.index'))

    start_time_str = request.form.get('start_time', '').strip()
    end_time_str = request.form.get('end_time', '').strip()
    leave_type = request.form.get('leave_type', 'Personal').strip()
    reason = request.form.get('reason', '').strip()

    if not start_time_str or not end_time_str or not leave_type:
        flash('請填寫請假時間與假別。', 'danger')
        return render_template('leave/apply.html'), 400

    try:
        # datetime-local input sends in format 'YYYY-MM-DDTHH:MM'
        start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
        end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
    except ValueError:
        flash('請假日期格式不正確。', 'danger')
        return render_template('leave/apply.html'), 400

    if start_time >= end_time:
        flash('請假開始時間不能大於或等於結束時間。', 'danger')
        return render_template('leave/apply.html'), 400

    try:
        Leave.create(
            staff_id=session['user_id'],
            start_time=start_time,
            end_time=end_time,
            leave_type=leave_type,
            reason=reason
        )
        flash('請假申請已送出，等待店長審核中。', 'success')
        return redirect(url_for('main.staff_dashboard'))
    except ValueError as e:
        flash(f'申請失敗: {str(e)}', 'danger')
        return render_template('leave/apply.html'), 400

@leave_bp.route('/leave/review', methods=['GET'])
@manager_required
def leave_review_page():
    """
    店長待審核請假申請名單頁面
    :return: 渲染 templates/leave/review.html
    """
    pending_leaves = Leave.get_all(status='Pending')
    approved_leaves = Leave.get_all(status='Approved')
    rejected_leaves = Leave.get_all(status='Rejected')
    return render_template(
        'leave/review.html',
        pending_leaves=pending_leaves,
        approved_leaves=approved_leaves,
        rejected_leaves=rejected_leaves
    )

@leave_bp.route('/leave/review/<int:leave_id>/approve', methods=['POST'])
@manager_required
def leave_approve(leave_id):
    """
    店長核准請假申請
    核准後將調用 Model 自動將該員工在請假期間內已排定的班次清空 (staff_id = NULL)
    :param leave_id: 假單唯一識別碼
    :return: 重導向回 /leave/review
    """
    leave = Leave.get_by_id(leave_id)
    if not leave:
        flash('找不到該筆請假單。', 'danger')
        return redirect(url_for('leave.leave_review_page'))

    leave.approve(reviewer_id=session['user_id'])
    flash(f'已核准員工 {leave.staff.name} 的 {leave.leave_type} 請假申請。該時段已排定的班次已釋出！', 'success')
    return redirect(url_for('leave.leave_review_page'))

@leave_bp.route('/leave/review/<int:leave_id>/reject', methods=['POST'])
@manager_required
def leave_reject(leave_id):
    """
    店長拒絕請假申請，可選填寫退回原因
    :param leave_id: 假單唯一識別碼
    :return: 重導向回 /leave/review
    """
    leave = Leave.get_by_id(leave_id)
    if not leave:
        flash('找不到該筆請假單。', 'danger')
        return redirect(url_for('leave.leave_review_page'))

    comment = request.form.get('comment', '').strip()
    leave.reject(reviewer_id=session['user_id'], comment=comment)
    flash(f'已拒絕員工 {leave.staff.name} 的請假申請。', 'warning')
    return redirect(url_for('leave.leave_review_page'))

@leave_bp.route('/shift/swap/post', methods=['POST'])
@login_required
def shift_swap_post():
    """
    員工針對自己已排定的特定班次，發起線上代班換班募集
    :return: 募集成功重導向回 /dashboard/staff 顯示代班募集狀態
    """
    shift_id = request.form.get('shift_id')
    if not shift_id:
        flash('無效的班表 ID。', 'danger')
        return redirect(url_for('main.staff_dashboard'))

    try:
        shift_id = int(shift_id)
    except ValueError:
        flash('無效的班表 ID 格式。', 'danger')
        return redirect(url_for('main.staff_dashboard'))

    shift = Shift.get_by_id(shift_id)
    if not shift:
        flash('找不到該筆班次。', 'danger')
        return redirect(url_for('main.staff_dashboard'))

    if shift.staff_id != session['user_id']:
        flash('您只能針對自己被指派的班次發起代班募集。', 'danger')
        return redirect(url_for('main.staff_dashboard'))

    # 將指派員工清空為空班/缺工 (staff_id = None)，並標示為草稿狀態以利店長調整
    shift.update(staff_id=None, is_draft=True)
    flash(f'已成功將您的「{shift.title}」班表釋出並發起代班募集！', 'success')
    return redirect(url_for('main.staff_dashboard'))
