# app/models/question_paper.py

from datetime import datetime
import pytz  # ✅ Import pytz
from app.extensions import db

# ✅ Helper for IST Time
def get_ist_time():
    return datetime.now(pytz.timezone('Asia/Kolkata'))


class QuestionPaper(db.Model):
    __tablename__ = "question_paper"

    id = db.Column(db.Integer, primary_key=True)

    subject_version_id = db.Column(
        db.Integer,
        db.ForeignKey("subject_version.id", ondelete="CASCADE"),
        nullable=False
    )
    source_question_bank_id = db.Column(
        db.Integer,
        db.ForeignKey("question_bank.id"),
        nullable=True
    )
    paper_code = db.Column(
        db.String(20),
        nullable=False
    )
    # Examples: A, B, C, SET-1, BACKUP-2, UUID if needed
    paper_type = db.Column(
        db.String(20),
        nullable=False,
        default="NORMAL"
    )

    status = db.Column(
        db.String(30),
        nullable=False,
        default="GENERATED"
    )
    # GENERATED | UNDER_SCRUTINY | FINALIZED | ARCHIVED (informational only)

    title = db.Column(
        db.String(255)
    )
    # Optional: "Emergency Paper", "Leak Replacement"

    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=get_ist_time,
        nullable=False
    )

    last_modified_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    last_modified_at = db.Column(
        db.DateTime,
        default=get_ist_time,
        onupdate=get_ist_time,
        nullable=False
    )

    # ----------------------------
    # Relationships
    # ----------------------------
    subject_version = db.relationship(
        "SubjectVersion",
        backref=db.backref("question_papers", lazy=True)
    )

    creator = db.relationship(
        "User",
        foreign_keys=[created_by],
        backref=db.backref("created_papers", lazy=True)
    )

    modifier = db.relationship(
        "User",
        foreign_keys=[last_modified_by],
        backref=db.backref("modified_papers", lazy=True)
    )

    # ✅ FIXED RELATIONSHIP
    items = db.relationship(
        "QuestionPaperItem",
        back_populates="question_paper",  # Changed from backref to back_populates
        lazy=True,
        cascade="all, delete-orphan",
        order_by="QuestionPaperItem.order_index"
    )

    # ----------------------------
    # Helpers
    # ----------------------------
    def mark_status(self, status: str, user_id: int):
        self.status = status
        self.last_modified_by = user_id

    @property
    def is_editable(self):
        # Always editable as per your final rule
        return True