from app.extensions import db

class School(db.Model):
    __tablename__ = "school"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

    departments = db.relationship(
        "Department",
        back_populates="school",
        cascade="all, delete-orphan"
    )
