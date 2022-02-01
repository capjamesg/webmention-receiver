from flask_login import UserMixin

from .__init__ import db


class User(UserMixin, db.Model):
    id = db.Column(
        db.Integer, primary_key=True
    )  # primary keys are required by SQLAlchemy
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    api_key = db.Column(db.String(100))
