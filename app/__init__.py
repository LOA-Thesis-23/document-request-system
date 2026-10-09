import os
from dotenv import load_dotenv
from flask import Flask
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
bcrypt = Bcrypt()


def create_app():
    app = Flask(__name__)

    # Reads DATABASE_URL from Vercel/env, or falls back to local SQLite if unset
    db_url = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    
    # Fixes legacy 'postgres://' scheme for SQLAlchemy compatibility
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    bcrypt.init_app(app)

    login_manager.login_view = 'auth.login'

    from app import models

    from app.routes.admin import admin_bp
    from app.routes.auth import auth_bp
    from app.routes.cashier import cashier_bp
    from app.routes.registrar import registrar_bp
    from app.routes.staff import staff_bp
    from app.routes.student import student_bp

    app.register_blueprint(student_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(cashier_bp)
    app.register_blueprint(registrar_bp)

    return app
