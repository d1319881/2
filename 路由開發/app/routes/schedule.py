# 儲存路徑: 路由開發/app/routes/schedule.py
from datetime import datetime, time, timedelta
from flask import render_template, redirect, url_for, request, flash, session
from app.routes import schedule_bp
from app.models import db
from app.models.shift import Shift
from app.models.user import User
from app.routes.auth import login_required, manager_required
from app.utils.scheduler import AutoScheduler

@schedule_bp.route('/view', methods=['GET'])
@login_required
def view_schedule():
    """
    一般員工唯讀班表檢視頁面
    內嵌唯讀之 FullCalendar.js 行事曆，不開放拖拉修改
    :return: 渲染 templates/schedule/view.html
    """
    return render_template('schedule/view.html')

@schedule_bp.route('/manage', methods=['GET'])
@manager_required
def manage_schedule():
    """
    店長專用排班管理控制台
    內嵌可拖拉、點擊編輯的 FullCalendar.js 控制介面，並提供一鍵自動排班按鈕
    :return: 渲染 templates/schedule/manage.html
    """
    staff_list = User.query.filter_by(role='staff', is_deleted=False).all()
    return render_template('schedule/manage.html', staff_list=staff_list)

@schedule_bp.route('/auto', methods=['POST'])
@manager_required
def auto_schedule():
    """
    觸發後端智慧自動排班引擎
    讀取傳入的排班日期範圍（start_date 與 end_date），呼叫演算法產出排班草稿
    :return: 執行成功重導向至 /schedule/manage 預覽草稿
    """
    start_date_str = request.form.get('start_date', '').strip()
    end_date_str = request.form.get('end_date', '').strip()

    if not start_date_str or not end_date_str:
        flash('請填寫排班開始與結束日期。', 'danger')
        return redirect(url_for('schedule.manage_schedule'))

    try:
        # 簡單驗證日期順序
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        if start_date > end_date:
            flash('開始日期不能大於結束日期。', 'danger')
            return redirect(url_for('schedule.manage_schedule'))

        # 呼叫排班引擎
        created_shifts = AutoScheduler.run_auto_schedule(start_date_str, end_date_str)
        flash(f'自動排班完成！已成功為您生成 {len(created_shifts)} 個班次草稿。', 'success')
    except ValueError as e:
        flash(f'排班失敗: {str(e)}', 'danger')
    except Exception as e:
        flash(f'排班過程發生系統錯誤: {str(e)}', 'danger')

    return redirect(url_for('schedule.manage_schedule'))

@schedule_bp.route('/publish', methods=['POST'])
@manager_required
def publish_schedule():
    """
    正式發佈特定時間範圍內的排班草稿
    將該時間範圍內所有班表的 is_draft 標記設為 False，使一般員工可看見
    :return: 發佈成功重導向至 /schedule/manage
    """
    start_date_str = request.form.get('start_date', '').strip()
    end_date_str = request.form.get('end_date', '').strip()

    if not start_date_str or not end_date_str:
        flash('請選擇發佈的開始與結束日期。', 'danger')
        return redirect(url_for('schedule.manage_schedule'))

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        end_datetime = datetime.combine(end_date.date(), time.max)

        # 查詢所有草稿並將其發佈
        draft_shifts = Shift.query.filter(
            Shift.start_time >= start_date,
            Shift.end_time <= end_datetime,
            Shift.is_draft == True,
            Shift.is_deleted == False
        ).all()

        if not draft_shifts:
            flash('在該區間內找不到任何待發佈的排班草稿。', 'warning')
            return redirect(url_for('schedule.manage_schedule'))

        for shift in draft_shifts:
            shift.is_draft = False
        
        db.session.commit()
        flash(f'發佈成功！已將 {len(draft_shifts)} 個班次正式發佈，一般員工現在可以查看。', 'success')
    except ValueError:
        flash('日期格式錯誤。', 'danger')
    except Exception as e:
        flash(f'發佈失敗: {str(e)}', 'danger')

    return redirect(url_for('schedule.manage_schedule'))
