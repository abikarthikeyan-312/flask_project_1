from app.extensions import db

class Pattern(db.Model):
    __tablename__ = "pattern"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

    total_marks = db.Column(db.Integer, nullable=False)
    structure_json = db.Column(db.JSON, nullable=False)

    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f"<Pattern {self.name}>"