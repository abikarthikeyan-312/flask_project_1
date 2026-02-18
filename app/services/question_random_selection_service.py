import random
from collections import defaultdict

from app.models.subject_version import SubjectVersion
from app.models.weightage import SubjectWeightage


class RandomSelectionError(Exception):
    pass


def select_random_questions(
    *,
    subject_version_id: int,
    questions: list[dict],
    seed: int | None = None
) -> dict:
    """
    Randomly select questions respecting:
    - unit
    - section
    - weightage counts

    Returns grouped result for UI preview.
    """

    if seed is not None:
        random.seed(seed)

    # -------------------------------------------------
    # 1️⃣ Load weightage
    # -------------------------------------------------
    weightages = (
        SubjectWeightage.query
        .filter_by(subject_version_id=subject_version_id)
        .all()
    )

    if not weightages:
        raise RandomSelectionError("Weightage not defined")

    # required_count[(unit, section)] = count
    required_count = {}
    for w in weightages:
        required_count[(w.unit, "A")] = w.sec_a_count or 0
        required_count[(w.unit, "B")] = w.sec_b_count or 0
        required_count[(w.unit, "C")] = w.sec_c_count or 0

    # -------------------------------------------------
    # 2️⃣ Group questions by (unit, section)
    # -------------------------------------------------
    pool = defaultdict(list)

    for q in questions:
        key = (q["unit"], q["section"])
        pool[key].append(q)

    # -------------------------------------------------
    # 3️⃣ Validate availability (ONE error per group)
    # -------------------------------------------------
    errors = []

    for key, required in required_count.items():
        available = len(pool.get(key, []))
        if available < required:
            unit, section = key
            errors.append({
                "type": "INSUFFICIENT_QUESTIONS",
                "message": (
                    f"Unit {unit} Section {section}: "
                    f"required {required}, found {available}"
                )
            })

    if errors:
        return {"valid": False, "errors": errors}

    # -------------------------------------------------
    # 4️⃣ Random selection
    # -------------------------------------------------
    selected = []
    used_ids = set()

    for key, required in required_count.items():
        if required == 0:
            continue

        candidates = pool[key][:]
        random.shuffle(candidates)

        chosen = candidates[:required]
        for q in chosen:
            if q["id"] in used_ids:
                continue
            used_ids.add(q["id"])
            selected.append(q)

    # -------------------------------------------------
    # 5️⃣ Group for UI
    # -------------------------------------------------
    grouped = defaultdict(list)
    for q in selected:
        grouped[(q["unit"], q["section"])].append(q)

    return {
        "valid": True,
        "selected_count": len(selected),
        "grouped": {
            f"Unit {u} Section {s}": qs
            for (u, s), qs in grouped.items()
        }
    }
