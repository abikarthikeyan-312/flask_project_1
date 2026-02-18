#app/services/question_bank_excel_validation_service.py
import pandas as pd
from io import BytesIO

from app.models.subject_version import SubjectVersion
from app.models.weightage import SubjectWeightage


REQUIRED_COLUMNS = {"UNIT", "SECTION","MARKS", "K LEVEL", "QUESTIONS"}


class ExcelValidationError(Exception):
    pass


def validate_question_bank_excel(
    *,
    file_bytes: bytes,
    subject_version_id: int
) -> dict:
    errors = []

    # -------------------------------------------------
    # 1️⃣ Load SubjectVersion + Pattern + Weightage
    # -------------------------------------------------
    sv = SubjectVersion.query.get_or_404(subject_version_id)

    if not sv.pattern:
        return _fail("PATTERN_MISSING", "Pattern not assigned to subject")

    sections_cfg = sv.pattern.structure_json.get("sections", {})
    allowed_sections = set(sections_cfg.keys())

    weightages = (
        SubjectWeightage.query
        .filter_by(subject_version_id=subject_version_id)
        .all()
    )

    if not weightages:
        return _fail("WEIGHTAGE_MISSING", "Weightage not defined for subject")

    # (unit, section) → required count
    weightage_map = {}
    for w in weightages:
        weightage_map[(w.unit, "A")] = w.sec_a_count or 0
        weightage_map[(w.unit, "B")] = w.sec_b_count or 0
        weightage_map[(w.unit, "C")] = w.sec_c_count or 0

    used_count = {k: 0 for k in weightage_map.keys()}

    # -------------------------------------------------
    # 2️⃣ Load Excel (raw)
    # -------------------------------------------------
    try:
        raw_df = pd.read_excel(BytesIO(file_bytes), header=None)
    except Exception:
        return _fail("FILE_INVALID", "Unable to read Excel file")

    # -------------------------------------------------
    # 3️⃣ Subject Code Validation (first 15 rows, any cell)
    # -------------------------------------------------
    subject_code = sv.subject.code.strip().upper()
    found_code = False

    for r in range(min(15, len(raw_df))):
        row_text = " ".join(
            str(v).upper() for v in raw_df.iloc[r].values if pd.notna(v)
        )
        if subject_code in row_text:
            found_code = True
            break

    if not found_code:
        return _fail(
            "SUBJECT_CODE_MISMATCH",
            f"Subject code '{subject_code}' not found in first 15 rows"
        )

    # -------------------------------------------------
    # 4️⃣ Detect Header Row (scan first 40 rows)
    # -------------------------------------------------
    header_row_idx = None
    for i in range(min(40, len(raw_df))):
        row_values = {
            str(v).strip().upper()
            for v in raw_df.iloc[i].values
            if pd.notna(v)
        }
        if REQUIRED_COLUMNS.issubset(row_values):
            header_row_idx = i
            break

    if header_row_idx is None:
        return _fail(
            "HEADER_NOT_FOUND",
            "Required columns not found within first 40 rows"
        )

    df = pd.read_excel(BytesIO(file_bytes), header=header_row_idx)
    df.columns = [c.strip().upper() for c in df.columns]

    # -------------------------------------------------
    # 5️⃣ Row-level Structural Validation + Counting
    # -------------------------------------------------
    for idx, row in df.iterrows():
        excel_row = header_row_idx + idx + 2

        unit = row.get("UNIT")
        section = str(row.get("SECTION")).strip().upper()

        # Unit validation
        if unit not in range(1, 6):
            errors.append(_row_err(
                "UNIT_INVALID",
                excel_row,
                f"Invalid unit '{unit}' (allowed 1–5)"
            ))
            continue

        # Section validation
        if section not in allowed_sections:
            errors.append(_row_err(
                "SECTION_INVALID",
                excel_row,
                f"Invalid section '{section}' (allowed {', '.join(sorted(allowed_sections))})"
            ))
            continue

        key = (unit, section)

        # Weightage existence
        if key not in weightage_map:
            errors.append(_row_err(
                "WEIGHTAGE_NOT_ALLOWED",
                excel_row,
                f"Unit {unit} Section {section} not allowed by weightage"
            ))
            continue

        used_count[key] += 1

    # -------------------------------------------------
    # 6️⃣ Aggregate Validation (ONCE per unit/section)
    # -------------------------------------------------
    for (unit, section), required in weightage_map.items():
        provided = used_count.get((unit, section), 0)

        if provided < required:
            errors.append({
                "type": "INSUFFICIENT_QUESTIONS",
                "message": (
                    f"Unit {unit} Section {section}: "
                    f"required {required}, found {provided}"
                )
            })

        

    # -------------------------------------------------
    # 7️⃣ Final Decision
    # -------------------------------------------------
    if errors:
        return {"valid": False, "errors": errors}

    return {
        "valid": True,
        "summary": {
            "rows": len(df),
            "units": sorted(df["UNIT"].dropna().unique().tolist())
        }
    }


# -------------------------------------------------
# Helpers
# -------------------------------------------------
def _fail(code, message):
    return {
        "valid": False,
        "errors": [{
            "type": code,
            "message": message
        }]
    }


def _row_err(code, row, message):
    return {
        "type": code,
        "row": row,
        "message": message
    }
