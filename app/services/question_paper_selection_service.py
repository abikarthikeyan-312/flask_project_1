# app/services/question_paper_selection_service.py

from random import sample
from collections import defaultdict

from app.extensions import db
from app.models.question_paper import QuestionPaper
from app.models.question_bank import QuestionBankItem


class QuestionSelectionError(Exception):
    pass


def auto_select_questions_for_paper(paper_id: int) -> QuestionPaper:
    """
    Phase 5B.5
    Randomly select questions respecting:
      - unit (from weightage)
      - marks (from pattern)
      - section (derived from marks)
      - total required placeholders
    """

    paper = QuestionPaper.query.get_or_404(paper_id)

    if paper.status != "GENERATED":
        raise QuestionSelectionError(
            "Only GENERATED papers can be auto-filled"
        )

    if not paper.source_question_bank_id:
        raise QuestionSelectionError(
            "No Question Bank linked to this paper"
        )

    # -------------------------------------------------
    # 1️⃣ Group placeholders by (unit, marks)
    # -------------------------------------------------
    required_map = defaultdict(list)

    for item in paper.items:
        if item.source_question_id:
            continue  # idempotent safe

        key = (item.unit, item.marks)
        required_map[key].append(item)

    # -------------------------------------------------
    # 2️⃣ Randomly select from QuestionBankItem
    # -------------------------------------------------
    for (unit, marks), items in required_map.items():
        required_count = len(items)

        candidates = (
            QuestionBankItem.query
            .filter_by(
                question_bank_id=paper.source_question_bank_id,
                unit=unit,
                marks=marks
            )
            .all()
        )

        if len(candidates) < required_count:
            raise QuestionSelectionError(
                f"Not enough questions for "
                f"Unit {unit}, Marks {marks} "
                f"(required {required_count}, found {len(candidates)})"
            )

        selected = sample(candidates, required_count)

        # -------------------------------------------------
        # 3️⃣ Assign questions to placeholders
        # -------------------------------------------------
        for paper_item, bank_item in zip(items, selected):
            paper_item.source_question_id = bank_item.id
            paper_item.original_text = bank_item.question.question_text
            paper_item.k_level = bank_item.k_level
            paper_item.source_type = "QBANK"

    db.session.commit()
    return paper
