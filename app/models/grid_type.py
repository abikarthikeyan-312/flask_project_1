from app.extensions import db

class GridType(db.Model):
    __tablename__ = "grid_type"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    has_problem_column = db.Column(db.Boolean, default=False)
