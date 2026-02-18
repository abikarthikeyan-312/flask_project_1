from app.extensions import db

class Subject(db.Model):
    __tablename__ = "subject"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    grid_type_id = db.Column(db.Integer, db.ForeignKey("grid_type.id"))

    grid_type = db.relationship("GridType")
