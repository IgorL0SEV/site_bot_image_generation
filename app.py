import os
import uuid
from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from models import db, User, ImageHistory
from logo_generator import generate_logo

# Часовой пояс Минска
TZ = ZoneInfo("Europe/Minsk")

# Инициализация Flask с поддержкой instance-папки
app = Flask(__name__, instance_relative_config=True)

# Конфигурируем секретный ключ и путь к базе данных (в instance/)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "test_secret")

# Создаём папку instance и results внутри неё
os.makedirs(app.instance_path, exist_ok=True)
results_dir = os.path.join(app.instance_path, "results")
os.makedirs(results_dir, exist_ok=True)

# Абсолютный путь к базе данных
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(app.instance_path, 'site.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Инициализация базы данных
db.init_app(app)

# Фильтр для шаблонов: UTC → Minsk
@app.template_filter('to_minsk_time')
def to_minsk_time_filter(utc_datetime):
    """Переводит UTC время в минское (datetime)"""
    if utc_datetime is None:
        return ""
    if utc_datetime.tzinfo is None:
        utc_datetime = utc_datetime.replace(tzinfo=ZoneInfo("UTC"))
    return utc_datetime.astimezone(TZ)

@app.template_filter('strftime')
def _jinja2_filter_datetime(value, fmt='%d.%m.%Y %H:%M'):
    if value is None:
        return ""
    return value.strftime(fmt)

# Настройка Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Пожалуйста, войдите в аккаунт, чтобы получить доступ!"

@login_manager.user_loader
def load_user(user_id):
    """Загрузка пользователя по ID (используется Flask-Login)"""
    return User.query.get(int(user_id))

def create_tables():
    """Создаёт таблицы базы данных, если их нет"""
    with app.app_context():
        db.create_all()
        print("Database tables created successfully!")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Регистрация нового пользователя"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if not username or not password:
            flash("Заполните все поля")
            return render_template("register.html")
        if User.query.filter_by(username=username).first():
            flash("Пользователь уже существует!")
            return render_template("register.html")
        user = User(username=username, password=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        flash("Регистрация успешна, войдите!")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Авторизация пользователя"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password, password):
            flash("Неверный логин или пароль")
            return render_template("login.html")
        login_user(user)
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    """Выход из аккаунта"""
    logout_user()
    return redirect(url_for("login"))

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Главная страница: генерация логотипов и история"""
    user = current_user

    # Лимит генераций: не более 5 за последний час (UTC)
    now_utc = datetime.now(ZoneInfo("UTC"))
    one_hour_ago_utc = now_utc - timedelta(hours=1)

    recent = ImageHistory.query.filter_by(user_id=user.id).filter(
        ImageHistory.timestamp > one_hour_ago_utc
    ).count()

    if request.method == "POST":
        prompt = request.form.get("prompt", "").strip()
        if not prompt:
            flash("Заполните поле с описанием!")
        elif recent >= 5:
            flash("❗ Лимит: не более 5 генераций в час.")
        else:
            try:
                # Время генерации (UTC для базы, Minsk для имени файла)
                save_time_utc = datetime.now(ZoneInfo("UTC"))
                filename_time_minsk = save_time_utc.astimezone(TZ)
                timestamp = filename_time_minsk.strftime("%Y-%m-%d_%H-%M-%S")
                file_id = uuid.uuid4().hex
                filename = f"{timestamp}_{file_id}.jpg"
                path = os.path.join(results_dir, filename)

                image_data = generate_logo(prompt)
                with open(path, "wb") as f:
                    f.write(image_data)

                # Сохраняем время генерации в UTC
                record = ImageHistory(
                    prompt=prompt,
                    filename=filename,
                    user_id=user.id,
                    timestamp=save_time_utc
                )
                db.session.add(record)
                db.session.commit()

                # Оставляем только 10 последних файлов в истории пользователя
                all_user_imgs = ImageHistory.query.filter_by(user_id=user.id).order_by(
                    ImageHistory.timestamp.desc()
                ).all()
                for extra in all_user_imgs[10:]:
                    old_path = os.path.join(results_dir, extra.filename)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                    db.session.delete(extra)
                db.session.commit()

                return redirect(url_for("index"))
            except Exception as e:
                flash(f"Ошибка генерации: {e}")

    # История последних 10 логотипов
    history = ImageHistory.query.filter_by(user_id=user.id).order_by(
        ImageHistory.timestamp.desc()
    ).limit(10).all()

    # Текущее время в Минске для отображения
    current_minsk_time = datetime.now(TZ).strftime("%d.%m.%Y %H:%M")

    return render_template("index.html",
                           history=history,
                           current_time=current_minsk_time)

@app.route("/results/<filename>")
@login_required
def get_result(filename):
    """Отдача файла логотипа по имени"""
    path = os.path.join(results_dir, filename)
    if not os.path.exists(path):
        return "", 404
    return send_file(path, mimetype="image/jpeg")

if __name__ == "__main__":
    create_tables()
    app.run(debug=True)
