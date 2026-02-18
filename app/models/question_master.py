# app/models/question_master.py
import pytz  # ✅ Import pytz
from app.extensions import db
from datetime import datetime

# ✅ Helper for IST Time
def get_ist_time():
    return datetime.now(pytz.timezone('Asia/Kolkata'))


class QuestionMaster(db.Model):
    __tablename__ = "question_master"

    id = db.Column(db.Integer, primary_key=True)

    subject_id = db.Column(
        db.Integer,
        db.ForeignKey("subject.id"),
        nullable=False
    )

    question_hash = db.Column(db.String(64), unique=True, nullable=False)
    question_text = db.Column(db.Text, nullable=False)

    # ✅ METADATA COLUMNS
    default_marks = db.Column(db.Integer, nullable=True)
    k_level = db.Column(db.String(20), nullable=True)
    default_unit = db.Column(db.Integer, nullable=True)      # <-- NEW
    default_section = db.Column(db.String(10), nullable=True) # <-- NEW

    created_at = db.Column(db.DateTime, default=get_ist_time)

    # Relationships
    subject = db.relationship("Subject", backref="master_questions")
    bank_items = db.relationship("QuestionBankItem", backref="master_question", lazy=True)

    __table_args__ = (
        db.UniqueConstraint(
            "subject_id",
            "question_hash",
            name="uq_subject_question_hash"
        ),
    )