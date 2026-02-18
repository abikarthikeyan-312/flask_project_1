from app.extensions import db

class SubjectVersionPattern(db.Model):
    __tablename__ = "subject_version_pattern"

    id = db.Column(db.Integer, primary_key=True)

    subject_version_id = db.Column(
        db.Integer, db.ForeignKey("subject_version.id"), nullable=False
    )
    pattern_id = db.Column(
        db.Integer, db.ForeignKey("pattern.id"), nullable=False
    )

    effective_from = db.Column(db.Date, nullable=False)
    effective_to = db.Column(db.Date, nullable=True)

    subject_version = db.relationship("SubjectVersion")
    pattern = db.relationship("Pattern")
