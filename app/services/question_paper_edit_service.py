#app\services\question_paper_edit_service.py
from app.extensions import db
from app.models.question_paper_item import QuestionPaperItem
from app.models.question_bank import QuestionBankItem


class PaperEditError(Exception):
    pass


# -------------------------------------------------
# Internal guard (Phase 4C rule)
# -------------------------------------------------
def _assert_editable(paper_item: QuestionPaperItem):
    if paper_item.question_paper.status == "ACTIVE":
        raise PermissionError(
            "ACTIVE question paper cannot be modified"
        )


# -------------------------------------------------
# Swap with QuestionBankItem
# -------------------------------------------------
def swap_question_with_bank(
    *,
    paper_item_id: int,
    new_bank_item_id: int
) -> QuestionPaperItem:
    """
    Replace a paper question with another from QuestionBank.
    """

    paper_item = QuestionPaperItem.query.get(paper_item_id)
    if not paper_item:
        raise PaperEditError("Invalid QuestionPaperItem")

    _assert_editable(paper_item)   # ✅ MISSING EARLIER

    bank_item = QuestionBankItem.query.get(new_bank_item_id)
    if not bank_item:
        raise PaperEditError("Invalid QuestionBankItem")

    paper_item.swap_with_bank_question(bank_item)

    db.session.commit()
    return paper_item


# -------------------------------------------------
# Manual text override
# -------------------------------------------------
def apply_manual_edit(
    *,
    paper_item_id: int,
    new_text: str
) -> QuestionPaperItem:
    """
    Manually override a question after scrutiny.
    """

    if not new_text.strip():
        raise PaperEditError("Edited text cannot be empty")

    paper_item = QuestionPaperItem.query.get(paper_item_id)
    if not paper_item:
        raise PaperEditError("Invalid QuestionPaperItem")

    _assert_editable(paper_item)   # ✅ MISSING EARLIER

    paper_item.apply_manual_edit(new_text)

    db.session.commit()
    return paper_item


# -------------------------------------------------
# Duplicate flagging
# -------------------------------------------------
def mark_duplicate(
    *,
    paper_item_id: int,
    is_duplicate: bool = True
) -> QuestionPaperItem:
    """
    Flag a question as duplicate during scrutiny.
    """

    paper_item = QuestionPaperItem.query.get(paper_item_id)
    if not paper_item:
        raise PaperEditError("Invalid QuestionPaperItem")

    _assert_editable(paper_item)   # ✅ MISSING EARLIER

    paper_item.is_duplicate_flag = is_duplicate

    db.session.commit()
    return paper_item
