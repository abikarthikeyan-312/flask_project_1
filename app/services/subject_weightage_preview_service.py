#app\services\subject_weightage_preview_service.py
from app.models.subject_version import SubjectVersion
from app.models.subject_version_pattern import SubjectVersionPattern
from app.models.pattern import Pattern
from app.models.weightage import SubjectWeightage


class WeightagePreviewError(Exception):
    pass


def get_subject_weightage_preview(*, subject_id: int, department_id: int, batch: int, semester: int):
    """
    Read-only preview of:
    - subject_version
    - pattern
    - unit-wise weightage
    """

    # 1️⃣ Resolve SubjectVersion
    subject_version = SubjectVersion.query.filter_by(
        subject_id=subject_id,
        department_id=department_id,
        batch=batch,
        semester=semester,
        is_active=True
    ).first_or_404()

    if not subject_version.pattern_id:
        raise WeightagePreviewError("Pattern not assigned to subject version")

    pattern = Pattern.query.get(subject_version.pattern_id)

    # 3️⃣ Load Weightage rows
    weightages = (
        SubjectWeightage.query
        .filter_by(subject_version_id=subject_version.id)
        .order_by(SubjectWeightage.unit)
        .all()
    )

    if not weightages:
        raise WeightagePreviewError("Weightage not defined")

    # 4️⃣ Shape response (frontend friendly)
    sections = pattern.structure_json.get("sections", {})

    return {
        "subject_version_id": subject_version.id,
        "subject": {
            "id": subject_version.subject.id,
            "name": subject_version.subject.name,
            "code": subject_version.subject.code
        },
        "pattern": {
            "name": pattern.name,
            "sectionA": sections.get("A", {}).get("total", 0),
            "sectionB": sections.get("B", {}).get("total", 0),
            "sectionC": sections.get("C", {}).get("total", 0),
        },
        "weightage": [
            {
                "unit": w.unit,
                "A": w.sec_a_count,
                "B": w.sec_b_count,
                "C": w.sec_c_count
            }
            for w in weightages
        ]
    }
