from flask import Flask
from flask_login import LoginManager
from werkzeug.security import generate_password_hash
from models import db, User

app = Flask(__name__)
app.config["SECRET_KEY"] = "emp-secret-key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///emp.db"

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "auth.login"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def create_admin():
    # admin is pre-existing, nobody can register as admin
    if not User.query.filter_by(role="admin").first():
        admin = User(
            name="Admin",
            email="admin@emp.com",
            password_hash=generate_password_hash("admin123"),
            role="admin",
        )
        db.session.add(admin)
        db.session.commit()


with app.app_context():
    db.create_all()
    create_admin()


@app.route("/")
def home():
    return "EMP is running"


if __name__ == "__main__":
    app.run(debug=True)