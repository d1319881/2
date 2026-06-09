# 儲存路徑: 路由開發/app/routes/auth.py
import functools
from flask import render_template, redirect, url_for, request, flash, session
from app.routes import auth_bp
from app.models.user import User

# --- 身分驗證與權限控制裝飾器 ---
def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('請先登入系統。', 'warning')
            return redirect(url_for('auth.login_page'))
        return f(*args, **kwargs)
    return decorated_function

def manager_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('請先登入系統。', 'warning')
            return redirect(url_for('auth.login_page'))
        if session.get('role') != 'manager':
            flash('權限不足，此功能僅限店長存取。', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/register', methods=['GET'])
def register_page():
    """
    顯示員工/管理員註冊頁面
    :return: 渲染 templates/auth/register.html
    """
    if 'user_id' in session:
        return redirect(url_for('main.index'))
    return render_template('auth/register.html')

@auth_bp.route('/register', methods=['POST'])
def register():
    """
    處理使用者註冊表單提交
    :return: 註冊成功重導向至登入頁 /auth/login；失敗則重新渲染註冊頁並帶入錯誤訊息
    """
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    name = request.form.get('name', '').strip()
    role = request.form.get('role', 'staff').strip()
    max_weekly_hours = request.form.get('max_weekly_hours', '40.0')
    max_daily_hours = request.form.get('max_daily_hours', '8.0')

    # 基本輸入驗證
    if not username or not password or not name:
        flash('請填寫所有必要欄位 (帳號、密碼、姓名)。', 'danger')
        return render_template('auth/register.html'), 400

    try:
        max_weekly_hours = float(max_weekly_hours)
        max_daily_hours = float(max_daily_hours)
    except ValueError:
        flash('最大工時數值格式不正確。', 'danger')
        return render_template('auth/register.html'), 400

    # 建立使用者
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
        return render_template('auth/register.html'), 400

    flash('註冊成功，請登入。', 'success')
    return redirect(url_for('auth.login_page'))

@auth_bp.route('/login', methods=['GET'])
def login_page():
    """
    顯示使用者登入頁面
    :return: 渲染 templates/auth/login.html
    """
    if 'user_id' in session:
        return redirect(url_for('main.index'))
    return render_template('auth/login.html')

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    處理使用者登入驗證表單
    :return: 登入成功寫入 Session 並重導向至 /；失敗則重新渲染登入頁並顯示錯誤訊息
    """
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()

    if not username or not password:
        flash('請輸入帳號與密碼。', 'danger')
        return render_template('auth/login.html'), 400

    user = User.query.filter_by(username=username, is_deleted=False).first()

    if not user or not user.check_password(password):
        flash('帳號或密碼錯誤。', 'danger')
        return render_template('auth/login.html'), 400

    # 登入成功，將資訊寫入 Session
    session['user_id'] = user.id
    session['username'] = user.username
    session['role'] = user.role
    session['name'] = user.name

    flash(f'歡迎回來，{user.name}！', 'success')
    return redirect(url_for('main.index'))

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """
    使用者登出，清除 Session 資訊
    :return: 重導向至登入頁面 /auth/login
    """
    session.clear()
    flash('您已成功登出。', 'success')
    return redirect(url_for('auth.login_page'))
