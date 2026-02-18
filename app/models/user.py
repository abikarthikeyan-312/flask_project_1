from app.extensions import db
from werkzeug.security import generate_password_hash, check_password_hash

user_schools = db.Table(
    "user_schools",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id")),
    db.Column("school_id", db.Integer, db.ForeignKey("school.id")),
)

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(255))
    role = db.Column(db.String(50))

    schools = db.relationship(
        "School",
        secondary=user_schools,
        backref="users"
    )

    def set_password(self, raw_password):
        self.password = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password, raw_password)
