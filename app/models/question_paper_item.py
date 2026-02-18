# app/models/question_paper_item.py

from datetime import datetime
import pytz  # ✅ Import pytz
from app.extensions import db

# ✅ Helper for IST Time
def get_ist_time():
    return datetime.now(pytz.timezone('Asia/Kolkata'))

class QuestionPaperItem(db.Model):
    __tablename__ = "question_paper_item"

    id = db.Column(db.Integer, primary_key=True)
    question_paper_id = db.Column(
        db.Integer, 
        db.ForeignKey("question_paper.id", ondelete="CASCADE"), 
        nullable=False
    )

    # Core fields
    unit = db.Column(db.Integer, nullable=False)
    section = db.Column(db.String(1), nullable=False)
    marks = db.Column(db.Integer, nullable=False)
    k_level = db.Column(db.String(20), nullable=True)
    order_index = db.Column(db.Integer, nullable=False)

    # Source tracking
    source_type = db.Column(db.String(20), default="QBANK")  # QBANK | MANUAL
    source_question_id = db.Column(db.Integer, nullable=True) # ID of QuestionBankItem

    # Content
    original_text = db.Column(db.Text, nullable=False) # The snapshot of text
    manual_text_override = db.Column(db.Text, nullable=True) # If manually edited
    
    # Flags
    is_duplicate_flag = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=get_ist_time)
    last_modified_at = db.Column(db.DateTime, default=get_ist_time)

    # Relationships
    question_paper = db.relationship("QuestionPaper", back_populates="items")

    @property
    def display_text(self):
        """Returns the text to show (override wins if present)"""
        return self.manual_text_override if self.manual_text_override else self.original_text

    def swap_with_bank_question(self, bank_item):
        """
        Swaps this item with a new QuestionBankItem.
        Updates the text snapshot from the QuestionMaster.
        """
        self.source_question_id = bank_item.id
        
        # 🔴 OLD ERROR: self.original_text = bank_item.question_text
        # 🟢 FIX: Access via the 'question' relationship to QuestionMaster
        self.original_text = bank_item.question.question_text
        self.k_level = bank_item.k_level
        self.source_type = "QBANK"
        self.manual_text_override = None  # Reset any manual edits
        self.is_duplicate_flag = False    # Reset flags
        self.last_modified_at = get_ist_time()

    def apply_manual_edit(self, new_text):
        self.manual_text_override = new_text
        self.source_type = "MANUAL"
        self.last_modified_at = get_ist_time()