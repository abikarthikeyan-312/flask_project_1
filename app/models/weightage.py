from app.extensions import db

class SubjectWeightage(db.Model):
    __tablename__ = "subject_weightage"

    id = db.Column(db.Integer, primary_key=True)
    subject_version_id = db.Column(
        db.Integer, db.ForeignKey("subject_version.id"), nullable=False
    )    
    unit = db.Column(db.Integer)
    sec_a_count = db.Column(db.Integer, default=0)
    sec_b_count = db.Column(db.Integer, default=0)
    sec_c_count = db.Column(db.Integer, default=0)

    subject_version = db.relationship("SubjectVersion")
    