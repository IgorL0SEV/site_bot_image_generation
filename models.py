from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

# Инициализация базы SQLAlchemy
db = SQLAlchemy()

class User(UserMixin, db.Model):
    """
    Модель пользователя для авторизации на сайте (Flask-Login).
    """
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)  # хранит хэш пароля

    # История генераций (только для сайта)
    histories = db.relationship('ImageHistory', backref='user', lazy=True)

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"

class ImageHistory(db.Model):
    """
    История генераций логотипов (общая для сайта и Telegram-бота).
    Если логотип сгенерирован на сайте, используется user_id (User).
    Если через Telegram-бота — используется tg_user_id.
    """
    id = db.Column(db.Integer, primary_key=True)
    prompt = db.Column(db.String(256), nullable=False)         # Текст запроса (промпт)
    filename = db.Column(db.String(128), nullable=False)       # Имя файла картинки (например, с датой)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)# Время генерации

    # --- Пользователь сайта (ForeignKey на User), если логотип создан через сайт ---
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    # --- Telegram user ID, если генерация была через Telegram-бота ---
    tg_user_id = db.Column(db.BigInteger, nullable=True)

    # Источник генерации ("site" или "bot")
    source = db.Column(db.String(10), default="site", nullable=False)

    def __repr__(self):
        if self.user_id:
            return f"<ImageHistory(site user {self.user_id}, prompt='{self.prompt[:10]}...')>"
        elif self.tg_user_id:
            return f"<ImageHistory(tg_user {self.tg_user_id}, prompt='{self.prompt[:10]}...')>"
        return "<ImageHistory(unknown)>"


