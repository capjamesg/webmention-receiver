from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from .config import SECRET_KEY
import dateutil.parser
import os

# init SQLAlchemy so we can use it later in our models
db = SQLAlchemy()

def create_app():
    app = Flask(__name__)

    # read config.py file
    app.config.from_pyfile(os.path.join(".", "config.py"), silent=False)

    db.init_app(app)

    app.secret_key = SECRET_KEY

    from .models import User

    login_manager = LoginManager()
    login_manager.login_view = 'main.login'
    login_manager.init_app(app)
    
    @app.template_filter("convert_time")
    def _jinja2_filter_datetime(date, fmt=None):
        date = dateutil.parser.parse(date)
        native = date.replace(tzinfo=None)
        format= "%b %d, %Y (%H:%M:%S)"
        return native.strftime(format) 

    # blueprint for non-auth parts of app
    from .main import main as main_blueprint

    app.register_blueprint(main_blueprint)

    from .auth.auth import auth as auth_blueprint

    app.register_blueprint(auth_blueprint)

    from .send.send_views import send as send_blueprint

    app.register_blueprint(send_blueprint)

    from .seed import seed_db as seed_blueprint

    app.register_blueprint(seed_blueprint)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("404.html", title="Page not found", error=404), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("404.html", title="Server error", error=500), 500

    @app.errorhandler(405)
    def method_not_allowed(e):
        return render_template("404.html", title="Method not allowed", error=405), 405

    return app

create_app()