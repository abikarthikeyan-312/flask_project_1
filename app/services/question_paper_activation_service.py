#app\services\question_paper_activation_service.py
from app.extensions import db
from app.models.question_paper import QuestionPaper

#✅ This service is the ONLY place that changes ACTIVE state
class PaperActivationError(Exception):
    pass


def activate_question_paper(
    *,
    paper_id: int,
    activated_by: int
) -> QuestionPaper:
    """
    Makes a QuestionPaper ACTIVE.
    Ensures only ONE ACTIVE paper per subject_version.
    """

    paper = QuestionPaper.query.get(paper_id)

    if not paper:
        raise PaperActivationError("Invalid QuestionPaper")

    subject_version_id = paper.subject_version_id

    # 1. Demote existing ACTIVE paper (if any)
    active_paper = (
        QuestionPaper.query
        .filter_by(
            subject_version_id=subject_version_id,
            status="ACTIVE"
        )
        .first()
    )

    if active_paper and active_paper.id != paper.id:
        active_paper.status = "ARCHIVED"
        active_paper.last_modified_by = activated_by

    # 2. Activate selected paper
    paper.status = "ACTIVE"
    paper.last_modified_by = activated_by

    db.session.commit()
    return paper
