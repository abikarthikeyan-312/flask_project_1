# app/models/question_bank.py
from datetime import datetime
import pytz  # ✅ Import pytz
from app.extensions import db

# ✅ Helper for IST Time
def get_ist_time():
    return datetime.now(pytz.timezone('Asia/Kolkata'))

class QuestionBank(db.Model):
    __tablename__ = "question_bank"

    id = db.Column(db.Integer, primary_key=True)
    
    # ... (other columns remain the same) ...
    subject_version_id = db.Column(
            db.Integer,
            db.ForeignKey("subject_version.id", ondelete="CASCADE"),
            nullable=False
        )    
    version_no = db.Column(db.Integer, default=1)
    status = db.Column(db.String(20), default="ACTIVE") 
    file_hash = db.Column(db.String(64), nullable=True)

    is_default = db.Column(db.Boolean, default=False, nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    
    uploaded_at = db.Column(db.DateTime, default=get_ist_time)
    
    items = db.relationship("QuestionBankItem", backref="bank", cascade="all, delete-orphan")
    subject_version = db.relationship(
        'SubjectVersion', 
        backref=db.backref('question_banks', cascade="all, delete-orphan")
    )
class QuestionBankItem(db.Model):
    __tablename__ = "question_bank_item"

    id = db.Column(db.Integer, primary_key=True)

    question_bank_id = db.Column(
        db.Integer,
        db.ForeignKey("question_bank.id", ondelete="CASCADE"),
        nullable=False
    )

    question_id = db.Column(
        db.Integer,
        db.ForeignKey("question_master.id"),
        nullable=False
    )
    question = db.relationship("QuestionMaster")
    unit = db.Column(db.Integer, nullable=False)
    section = db.Column(db.String(1), nullable=False)   # A / B / C
    marks = db.Column(db.Integer, nullable=False)
    k_level = db.Column(db.String(20), nullable=True)
    
    created_at = db.Column(db.DateTime, default=get_ist_time)
