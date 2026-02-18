# app/services/question_paper_service.py

from datetime import datetime
from app.extensions import db

from app.models.subject_version import SubjectVersion
from app.models.weightage import SubjectWeightage
from app.models.question_bank import QuestionBank
from app.models.question_paper import QuestionPaper
from app.models.question_paper_item import QuestionPaperItem

class PaperGenerationError(Exception):
    pass

# 🔴 DELETE THIS HARDCODED DICT
# SECTION_MARKS = { "A": 2, "B": 5, "C": 10 } 

def generate_question_paper_skeleton(
    *,
    subject_version_id: int,
    created_by: int,
    paper_code: str,
    paper_type: str = "NORMAL",
    question_bank_id: int | None = None
) -> QuestionPaper:
    """
    Phase 3:
    Create QuestionPaper + placeholder QuestionPaperItems.
    Now uses DYNAMIC MARKS from the Subject Pattern.
    """

    # -------------------------------------------------
    # 1. Validate Subject Version + Pattern
    # -------------------------------------------------
    subject_version = SubjectVersion.query.get(subject_version_id)
    if not subject_version:
        raise PaperGenerationError("Invalid subject version")
        
    if not subject_version.pattern:
         raise PaperGenerationError("Subject Version has no Pattern assigned")

    # ✅ GET MARKS DYNAMICALLY FROM DB PATTERN
    sections_config = subject_version.pattern.structure_json.get("sections", {})
    
    # Safely get marks, defaulting to 0 if section doesn't exist in pattern
    marks_map = {
        "A": sections_config.get("A", {}).get("marks", 0),
        "B": sections_config.get("B", {}).get("marks", 0),
        "C": sections_config.get("C", {}).get("marks", 0),
    }

    # -------------------------------------------------
    # 2. Resolve Question Bank
    # -------------------------------------------------
    if question_bank_id:
        bank = QuestionBank.query.get(question_bank_id)
        if not bank:
            raise PaperGenerationError("Invalid Question Bank selected")
    else:
        bank = (
            QuestionBank.query
            .filter_by(
                subject_version_id=subject_version_id,
                is_default=True,
                status="ACTIVE"
            )
            .first()
        )

    if not bank:
        raise PaperGenerationError("No Question Bank found. Upload a Question Bank before generating paper.")

    # -------------------------------------------------
    # 3. Load Weightage
    # -------------------------------------------------
    weightages = (
        SubjectWeightage.query
        .filter_by(subject_version_id=subject_version_id)
        .order_by(SubjectWeightage.unit)
        .all()
    )

    if not weightages:
        raise PaperGenerationError("Weightage not defined")

    # -------------------------------------------------
    # 4. Create QuestionPaper
    # -------------------------------------------------
    paper = QuestionPaper(
        subject_version_id=subject_version_id,
        source_question_bank_id=bank.id,
        paper_code=paper_code,
        paper_type=paper_type,
        status="GENERATED",
        created_by=created_by,
        created_at=datetime.utcnow(),
        last_modified_by=created_by,
        last_modified_at=datetime.utcnow()
    )

    db.session.add(paper)
    db.session.flush()  # get paper.id

    # -------------------------------------------------
    # 5. Create Placeholder Items (Using Dynamic Marks)
    # -------------------------------------------------
    order_index = 1

    for w in weightages:
        unit = w.unit

        # Section A
        for _ in range(w.sec_a_count or 0):
            _add_item(paper.id, "A", unit, marks_map["A"], order_index)
            order_index += 1

        # Section B
        for _ in range(w.sec_b_count or 0):
            _add_item(paper.id, "B", unit, marks_map["B"], order_index)
            order_index += 1

        # Section C
        for _ in range(w.sec_c_count or 0):
            _add_item(paper.id, "C", unit, marks_map["C"], order_index)
            order_index += 1

    db.session.commit()
    return paper

# ... (create_question_bank and _add_item functions remain unchanged) ...
def create_question_bank(*, subject_version_id: int, uploaded_by: int) -> QuestionBank:
    existing_default = (
        QuestionBank.query
        .filter_by(
            subject_version_id=subject_version_id,
            is_default=True
        )
        .first()
    )

    is_default = existing_default is None  # first upload wins

    bank = QuestionBank(
        subject_version_id=subject_version_id,
        uploaded_by=uploaded_by,
        is_default=is_default,
        status="ACTIVE"
    )

    db.session.add(bank)
    db.session.commit()
    return bank

def _add_item(
    paper_id: int,
    section: str,
    unit: int,
    marks: int,
    order_index: int
):
    item = QuestionPaperItem(
        question_paper_id=paper_id,
        section=section,
        unit=unit,
        marks=marks,
        order_index=order_index,
        source_type="QBANK",
        original_text="[TO BE SELECTED]",
        created_at=datetime.utcnow(),
        last_modified_at=datetime.utcnow()
    )
    db.session.add(item)