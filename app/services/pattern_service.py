from app.extensions import db
from app.models.pattern import Pattern


# ----------------------------
# READ
# ----------------------------

def get_patterns():
    return Pattern.query.order_by(Pattern.name).all()


def get_pattern_by_id(pattern_id: int):
    return Pattern.query.get_or_404(pattern_id)


# ----------------------------
# CREATE
# ----------------------------

def create_pattern_from_form(form):
    """
    Converts pattern grid form into structure_json
    """
    if Pattern.query.filter_by(name=form["name"].strip()).first():
        raise ValueError("Existing pattern cannot be changed")

    try:
        sections = {}
        total_marks = 0

        for sec in ["A", "B", "C"]:
            count = int(form.get(f"count_{sec}", 0))
            total = int(form.get(f"total_{sec}", 0))
            marks = int(form.get(f"marks_{sec}", 0))
            note = form.get(f"note_{sec}", "").strip()

            if count == 0 and total == 0:
                continue  # skip unused sections

            sections[sec] = {
                "count": count,
                "total": total,
                "marks": marks,
                "note": note
            }

            total_marks += count * marks

        if not sections:
            raise ValueError("At least one section is required")

        pattern = Pattern(
            name=form["name"].strip(),
            total_marks=total_marks,
            structure_json={"sections": sections},
            is_active=True
        )

        db.session.add(pattern)
        db.session.commit()

    except Exception:
        db.session.rollback() # ✅ ALWAYS rollback on error
        raise 


def format_pattern_sections(pattern):
    sections_view = []

    structure = pattern.structure_json or {}
    sections = structure.get("sections", {})  # ✅ correct level

    for sec, cfg in sections.items():
        count = cfg.get("count", 0)
        marks = cfg.get("marks", 0)
        total_in_paper = cfg.get("total")
        note = cfg.get("note", "")

        section_total = count * marks

        expression = f"{marks} × {count} = {section_total}"

        if total_in_paper:
            details = f"{marks} marks, answer {count} out of {total_in_paper}"
        else:
            details = f"{marks} marks per question"

        sections_view.append({
            "section": f"Sec {sec}",
            "expression": expression,
            "details": details,
            "note": note
        })

    return sections_view

def format_pattern_for_subject(pattern: Pattern):
    sections = pattern.structure_json.get("sections", {})
    view = []

    for sec, cfg in sections.items():
        view.append({
            "section": f"Sec {sec}",
            "expression": f"{cfg['marks']} × {cfg['count']}",
            "details": f"{cfg['count']} out of {cfg['total']}",
            "note": cfg.get("note", "")
        })

    return view

# ----------------------------
# DELETE
# ----------------------------

def delete_pattern(pattern_id: int):
    pattern = get_pattern_by_id(pattern_id)
    db.session.delete(pattern)
    db.session.commit()


def get_active_pattern_for_subject_version(subject_version_id: int):
    """
    TEMPORARY PLACEHOLDER

    Pattern is not yet linked to subject_version.
    This will be implemented in the next phase.
    """
    return None
