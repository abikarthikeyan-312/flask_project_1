from app.extensions import db

class SubjectVersion(db.Model):
    __tablename__ = "subject_version"

    id = db.Column(db.Integer, primary_key=True)

    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=False)

    batch = db.Column(db.Integer, nullable=False)
    semester = db.Column(db.Integer, nullable=False)

    version = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

    subject = db.relationship("Subject")
    department = db.relationship("Department")
    pattern_id = db.Column(
        db.Integer,
        db.ForeignKey("pattern.id"),
        nullable=True
    )

    pattern = db.relationship("Pattern", lazy = "joined")

    __table_args__ = (
        db.UniqueConstraint(
            "subject_id", "department_id", "batch", "version",
            name="uq_subject_version"
        ),
    )
