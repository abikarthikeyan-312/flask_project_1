from app.extensions import db
from app.models.subject_version import SubjectVersion
from app.models.weightage import SubjectWeightage
from app.services.pattern_service import get_active_pattern_for_subject_version


# ----------------------------
# VALIDATION
# ----------------------------

def _validate_weightage_counts(unit: int, a: int, b: int, c: int):
    if unit not in range(1, 6):
        raise ValueError("Unit must be between 1 and 5")

    for val, name in [(a, "Section A"), (b, "Section B"), (c, "Section C")]:
        if val < 0:
            raise ValueError(f"{name} count cannot be negative")

    if a == b == c == 0:
        raise ValueError("At least one section must have a count greater than zero")


# ----------------------------
# READ
# ----------------------------

def get_weightage_by_subject_version(subject_version_id: int):
    return (
        SubjectWeightage.query
        .filter_by(subject_version_id=subject_version_id)
        .order_by(SubjectWeightage.unit)
        .all()
    )


# ----------------------------
# CREATE / UPDATE (UPSERT)
# ----------------------------

def add_or_update_multiple_weightages(subject_version_id: int, rows: list[dict]):

    if not rows:
        raise ValueError("No weightage data provided")

    # ✅ PATTERN VALIDATION FIRST
    validate_weightage_against_pattern(subject_version_id, rows)

    # overwrite existing safely
    SubjectWeightage.query.filter_by(
        subject_version_id=subject_version_id
    ).delete()

    for row in rows:
        db.session.add(
            SubjectWeightage(
                subject_version_id=subject_version_id,
                unit=row["unit"],
                sec_a_count=row["a"],
                sec_b_count=row["b"],
                sec_c_count=row["c"]
            )
        )

    db.session.commit()


def validate_weightage_against_pattern(subject_version_id: int, rows: list[dict]):
    # Fetch the SubjectVersion to access the assigned pattern directly
    sv = SubjectVersion.query.get(subject_version_id)
    if not sv or not sv.pattern:
        raise ValueError("No active pattern assigned to this subject version.")

    pattern = sv.pattern
    # In production-grade models, pattern details are in structure_json
    rules = pattern.structure_json or {}
    section_rules = rules.get("sections", {})

    # 1. Initialize totals for each section
    totals = {"A": 0, "B": 0, "C": 0}

    # 2. Sum the counts provided in the rows (for units 1-5)
    for row in rows:
        totals["A"] += int(row.get("a", 0))
        totals["B"] += int(row.get("b", 0))
        totals["C"] += int(row.get("c", 0))

    # 3. Compare aggregate totals against pattern requirements
    errors = []
    for sec_key in ["A", "B", "C"]:
        if sec_key in section_rules:
            # 'total' represents the "Total in Paper" defined in the Pattern
            required = int(section_rules[sec_key].get("total", 0))
            current = totals[sec_key]
            
            if current != required:
                errors.append(
                    f"Section {sec_key}: Sum of all units must be {required} "
                    f"(currently {current})"
                )

    if errors:
        # Join multiple errors for a comprehensive flash message
        raise ValueError(" | ".join(errors))
# ----------------------------
# DELETE
# ----------------------------

def delete_weightage_by_subject_version(subject_version_id: int):
    SubjectWeightage.query.filter_by(
        subject_version_id=subject_version_id
    ).delete()
    db.session.commit()
