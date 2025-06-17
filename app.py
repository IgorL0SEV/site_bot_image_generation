import os
import uuid
from flask import Flask, render_template, request, send_file, flash, redirect, url_for, session
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

from models import db, User, ImageHistory
from logo_generator import generate_logo

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "test_secret")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///site.db"
db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.before_first_request
def create_tables():
    db.create_all()

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
    # --- Лимит генераций: не более 5 за час ---
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    recent = ImageHistory.query.filter_by(user_id=user.id).filter(ImageHistory.timestamp > one_hour_ago).count()
    if request.method == "POST":
        prompt = request.form.get("prompt", "").strip()
        if not prompt:
            flash("Заполните поле с описанием!")
        elif recent >= 5:
            flash("❗ Лимит: не более 5 генераций в час.")
        else:
            try:
                image_data = generate_logo(prompt)
                file_id = uuid.uuid4().hex
                filename = f"{file_id}.jpg"
                path = os.path.join("results", filename)
                os.makedirs("results", exist_ok=True)
                with open(path, "wb") as f:
                    f.write(image_data)
                # сохраняем в историю пользователя
                record = ImageHistory(prompt=prompt, filename=filename, user_id=user.id)
                db.session.add(record)
                db.session.commit()
                # только 10 последних — удаляем лишние
                all_user_imgs = ImageHistory.query.filter_by(user_id=user.id).order_by(ImageHistory.timestamp.desc()).all()
                for extra in all_user_imgs[10:]:
                    old_path = os.path.join("results", extra.filename)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                    db.session.delete(extra)
                db.session.commit()
                return redirect(url_for("index"))
            except Exception as e:
                flash(f"Ошибка генерации: {e}")

    # История (10 последних)
    history = ImageHistory.query.filter_by(user_id=user.id).order_by(ImageHistory.timestamp.desc()).limit(10).all()
    return render_template("index.html", history=history)

@app.route("/results/<filename>")
@login_required
def get_result(filename):
    path = os.path.join("results", filename)
    if not os.path.exists(path):
        return "", 404
    return send_file(path, mimetype="image/jpeg")

if __name__ == "__main__":
    app.run(debug=True)


