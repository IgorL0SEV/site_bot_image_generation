import os
import uuid
from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from models import db, User, ImageHistory
from logo_generator import generate_logo

# Временная зона Минска
MINSK_TZ = ZoneInfo("Europe/Minsk")

app = Flask(__name__, instance_relative_config=True)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "test_secret")

os.makedirs(app.instance_path, exist_ok=True)
results_dir = os.path.join(app.instance_path, "results")
os.makedirs(results_dir, exist_ok=True)

app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(app.instance_path, 'site.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def create_tables():
    with app.app_context():
        db.create_all()
        print("Database tables created successfully!")

# Jinja-фильтр для перевода времени в Минск
@app.template_filter('to_minsk_time')
def to_minsk_time(utc_dt):
    if utc_dt is None:
        return ""
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=ZoneInfo("UTC"))
    minsk_dt = utc_dt.astimezone(MINSK_TZ)
    return minsk_dt.strftime("%d.%m.%Y %H:%M")

@app.route("/register", methods=["GET", "POST"])
def register():
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
    logout_user()
    return redirect(url_for("login"))

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    user = current_user
    now_utc = datetime.now(ZoneInfo("UTC"))
    one_hour_ago = now_utc - timedelta(hours=1)
    recent = ImageHistory.query.filter_by(user_id=user.id).filter(ImageHistory.timestamp > one_hour_ago).count()

    if request.method == "POST":
        prompt = request.form.get("prompt", "").strip()
        if not prompt:
            flash("Заполните поле с описанием!")
        elif recent >= 5:
            flash("❗ Лимит: не более 5 генераций в час.")
        else:
            try:
                # 1. Сохраняем UTC для базы (timestamp)
                utc_now = datetime.now(ZoneInfo("UTC"))
                # 2. Для имени файла и подписи используем минское время
                minsk_now = utc_now.astimezone(MINSK_TZ)
                file_id = uuid.uuid4().hex
                filename = f"{minsk_now.strftime('%Y-%m-%d_%H-%M-%S')}_{file_id}.jpg"
                path = os.path.join(results_dir, filename)

                image_data = generate_logo(prompt)
                with open(path, "wb") as f:
                    f.write(image_data)

                record = ImageHistory(
                    prompt=prompt,
                    filename=filename,
                    user_id=user.id,
                    timestamp=utc_now,  # всегда UTC!
                )
                db.session.add(record)
                db.session.commit()

                # Сохраняем только 10 последних
                all_user_imgs = ImageHistory.query.filter_by(user_id=user.id).order_by(ImageHistory.timestamp.desc()).all()
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
    history = ImageHistory.query.filter_by(user_id=user.id).order_by(ImageHistory.timestamp.desc()).limit(10).all()
    minsk_now_str = datetime.now(MINSK_TZ).strftime("%d.%m.%Y %H:%M")

    return render_template(
        "index.html",
        history=history,
        current_time=minsk_now_str
    )

@app.route("/results/<filename>")
@login_required
def get_result(filename):
    path = os.path.join(results_dir, filename)
    if not os.path.exists(path):
        return "", 404
    return send_file(path, mimetype="image/jpeg")

if __name__ == "__main__":
    create_tables()
    app.run(debug=True)

