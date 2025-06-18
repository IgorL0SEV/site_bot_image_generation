import os
import uuid
from flask import Flask, render_template, request, send_file, flash, redirect, url_for, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

from models import db, User, ImageHistory
from logo_generator import generate_logo

# Загружаем переменные окружения (включая MY_API_KEY)
load_dotenv()

# Настройки путей и часового пояса
TZ = ZoneInfo("Europe/Minsk")
API_KEY = os.getenv("MY_API_KEY", "SuperSecret123")
generate_limit = int(os.getenv("generate_limit", 5)) # лимит генераций за час, указываем в .env
user_imgs_site = int(os.getenv("user_imgs_site", 5)) # количество картинок на сайте, указываем в .env


# Flask c поддержкой instance/
app = Flask(__name__, instance_relative_config=True)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "test_secret")

# Создаём папки instance/ и results/
os.makedirs(app.instance_path, exist_ok=True)
results_dir = os.path.join(app.instance_path, "results")
os.makedirs(results_dir, exist_ok=True)

# Настройки базы
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(app.instance_path, 'site.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

# Фильтр для шаблонов: UTC → Минск
@app.template_filter('to_minsk_time')
def to_minsk_time_filter(utc_datetime):
    """Jinja2 filter: конвертирует UTC время в минское"""
    if utc_datetime is None:
        return ""
    return convert_utc_to_minsk(utc_datetime).strftime("%d.%m.%Y %H:%M")

def convert_utc_to_minsk(utc_datetime):
    """Вспомогательная функция: UTC → Europe/Minsk"""
    if utc_datetime is None:
        return None
    if utc_datetime.tzinfo is None:
        utc_datetime = utc_datetime.replace(tzinfo=ZoneInfo("UTC"))
    return utc_datetime.astimezone(TZ)

# Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Пожалуйста, войдите в аккаунт, чтобы получить доступ!"

@login_manager.user_loader
def load_user(user_id):
    """Flask-Login: загрузка пользователя"""
    return User.query.get(int(user_id))

def create_tables():
    """Инициализация базы"""
    with app.app_context():
        db.create_all()
        print("Database tables created successfully!")

# === WEB-часть ===

@app.route("/register", methods=["GET", "POST"])
def register():
    """Регистрация"""
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
    """Вход"""
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
    """Выход"""
    logout_user()
    return redirect(url_for("login"))

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Главная страница: генерация и история логотипов"""
    user = current_user

    # Лимит: {generate_limit} генераций за час (по UTC)
    now_utc = datetime.now(ZoneInfo("UTC"))
    one_hour_ago_utc = now_utc - timedelta(hours=1)
    recent = ImageHistory.query.filter_by(user_id=user.id).filter(ImageHistory.timestamp > one_hour_ago_utc).count()

    if request.method == "POST":
        prompt = request.form.get("prompt", "").strip()
        if not prompt:
            flash("Заполните поле с описанием!")
        elif recent >= generate_limit:
            flash(f"❗ Лимит: не более {generate_limit} генераций в час.")
        else:
            try:
                # Сохраняем UTC для базы, Минск — для имени файла
                save_time_utc = datetime.now(ZoneInfo("UTC"))
                filename_time_minsk = save_time_utc.astimezone(TZ)
                timestamp = filename_time_minsk.strftime("%Y-%m-%d_%H-%M-%S")
                file_id = uuid.uuid4().hex
                filename = f"{timestamp}_{file_id}.jpg"
                path = os.path.join(results_dir, filename)

                image_data = generate_logo(prompt)
                with open(path, "wb") as f:
                    f.write(image_data)

                record = ImageHistory(
                    prompt=prompt,
                    filename=filename,
                    user_id=user.id,
                    timestamp=save_time_utc,
                    source="site"
                )
                db.session.add(record)
                db.session.commit()

                # Оставляем только {user_imgs_site} последних
                all_user_imgs = ImageHistory.query.filter_by(user_id=user.id).order_by(
                    ImageHistory.timestamp.desc()).all()
                for extra in all_user_imgs[user_imgs_site:]:
                    old_path = os.path.join(results_dir, extra.filename)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                    db.session.delete(extra)
                db.session.commit()
                return redirect(url_for("index"))
            except Exception as e:
                flash(f"Ошибка генерации: {e}")

    # История последних {user_imgs_site} логотипов
    history = ImageHistory.query.filter_by(user_id=user.id).order_by(
        ImageHistory.timestamp.desc()).limit(user_imgs_site).all()
    for item in history:
        item.display_time = convert_utc_to_minsk(item.timestamp)
        item.display_time_str = item.display_time.strftime("%d.%m.%Y %H:%M")

    current_minsk_time = datetime.now(TZ).strftime("%d.%m.%Y %H:%M")
    return render_template("index.html",
                           history=history,
                           current_time=current_minsk_time,
                           TZ=TZ)

@app.route("/results/<filename>")
@login_required
def get_result(filename):
    """Отдача картинки по имени файла"""
    path = os.path.join(results_dir, filename)
    if not os.path.exists(path):
        return "", 404
    return send_file(path, mimetype="image/jpeg")

# === API для внешнего доступа (бот, интеграции) ===

@app.route("/api/generate", methods=["POST"])
def api_generate():
    """
    Генерация картинки через API (POST):
    - X-API-KEY (заголовок) или "api_key" в JSON
    - prompt: обязательный текст запроса
    - user_id: если от сайта, tg_user_id: если от Telegram
    """
    # Авторизация по ключу
    auth_key = request.headers.get("X-API-KEY") or request.json.get("api_key")
    if not auth_key or auth_key != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    prompt = request.json.get("prompt", "").strip()
    user_id = request.json.get("user_id")
    tg_user_id = request.json.get("tg_user_id")

    if not prompt or (not user_id and not tg_user_id):
        return jsonify({"error": "Missing prompt or user/tg_user_id"}), 400

    try:
        image_data = generate_logo(prompt)
        now_utc = datetime.now(ZoneInfo("UTC"))
        filename_time = now_utc.astimezone(TZ).strftime("%Y-%m-%d_%H-%M-%S")
        file_id = uuid.uuid4().hex
        filename = f"{filename_time}_{file_id}.jpg"
        path = os.path.join(results_dir, filename)
        with open(path, "wb") as f:
            f.write(image_data)
        with app.app_context():
            record = ImageHistory(
                prompt=prompt,
                filename=filename,
                user_id=user_id,
                tg_user_id=tg_user_id,
                source="api",
                timestamp=now_utc
            )
            db.session.add(record)
            db.session.commit()
        return jsonify({"status": "ok", "filename": filename}), 200
    except Exception as e:
        return jsonify({"error": f"Generation failed: {e}"}), 500

if __name__ == "__main__":
    create_tables()
    app.run(debug=True)


