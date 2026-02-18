from app.extensions import db

class Department(db.Model):
    __tablename__ = "department"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey("school.id"), nullable=False)

    name = db.Column(db.String(150), nullable=False)
    level = db.Column(db.String(10), nullable=False)

    school = db.relationship("School")
