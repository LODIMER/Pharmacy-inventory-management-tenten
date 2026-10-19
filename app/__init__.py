from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from pathlib import Path

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please sign in to continue."


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    app.config["SECRET_KEY"] = "pharmacy-tenten-dev-key"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + str(
        Path(app.instance_path) / "pharmacy.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"] = str(Path(app.instance_path) / "uploads")
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from app.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.users import users_bp
    from app.routes.products import products_bp
    from app.routes.inventory import inventory_bp
    from app.routes.dispensing import dispensing_bp
    from app.routes.requisitions import requisitions_bp
    from app.routes.suppliers import suppliers_bp
    from app.routes.reports import reports_bp
    from app.routes.audit import audit_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(dispensing_bp)
    app.register_blueprint(requisitions_bp)
    app.register_blueprint(suppliers_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(audit_bp)

    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        from app.models import Alert, ROLE_LABELS

        unread = 0
        if current_user.is_authenticated and current_user.is_staff():
            unread = Alert.query.filter_by(is_read=False).count()
        return {"unread_alerts": unread, "ROLE_LABELS": ROLE_LABELS}

    @app.errorhandler(403)
    def forbidden(_e):
        from flask import render_template

        return render_template("403.html"), 403

    with app.app_context():
        db.create_all()
        from app.seed import seed_if_empty

        seed_if_empty()

    return app
