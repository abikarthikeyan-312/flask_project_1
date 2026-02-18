# app/services/question_bank_ingestion_service.py

import pandas as pd
from io import BytesIO

from app.extensions import db
from app.models.subject_version import SubjectVersion
from app.models.question_bank import QuestionBank, QuestionBankItem
from app.models.question_master import QuestionMaster

from app.services.question_bank_excel_validation_service import (
    validate_question_bank_excel
)

import hashlib
import re


class QuestionBankIngestionError(Exception):
    pass


# ---------------------------------------------------
# Text Normalization + Hashing
# ---------------------------------------------------

def _normalize(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _hash(text: str) -> str:
    return hashlib.sha256(_normalize(text).encode("utf-8")).hexdigest()


# ---------------------------------------------------
# Main Ingestion Service
# ---------------------------------------------------

def ingest_question_bank_excel(
    *,
    file_bytes: bytes,
    subject_version_id: int,
    uploaded_by: int
) -> QuestionBank:
    """
    Ingest Question Bank with File-Level Deduplication.
    """

    # ---------------------------------------------
    # 1️⃣ Calculate File Hash (The Fingerprint)
    # ---------------------------------------------
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    # ---------------------------------------------
    # 2️⃣ Check for Duplicate Upload
    # ---------------------------------------------
    existing_bank = QuestionBank.query.filter_by(
        subject_version_id=subject_version_id,
        file_hash=file_hash
    ).first()

    if existing_bank:
        # ✅ STOP! Return the existing bank. 
        # No new items will be created (saving 200 rows).
        return existing_bank

    # ---------------------------------------------
    # 3️⃣ Validation (If not duplicate)
    # ---------------------------------------------
    validation = validate_question_bank_excel(
        file_bytes=file_bytes,
        subject_version_id=subject_version_id
    )

    if not validation["valid"]:
        raise QuestionBankIngestionError(
            "Excel validation failed. Fix errors before upload."
        )

    # ---------------------------------------------
    # 4️⃣ Create New Bank (With Hash)
    # ---------------------------------------------
    existing_count = QuestionBank.query.filter_by(
        subject_version_id=subject_version_id
    ).count()

    bank = QuestionBank(
        subject_version_id=subject_version_id,
        version_no=existing_count + 1,
        is_default=(existing_count == 0),
        status="ACTIVE",
        uploaded_by=uploaded_by,
        file_hash=file_hash # ✅ Save the hash
    )

    db.session.add(bank)
    db.session.flush()

    # ---------------------------------------------
    # 5️⃣ Insert Items (Same logic as before)
    # ---------------------------------------------
    
    # Reload Excel
    raw_df = pd.read_excel(BytesIO(file_bytes), header=None)
    header_row_idx = None
    REQUIRED_COLUMNS = {"UNIT", "SECTION", "K LEVEL", "QUESTIONS"}

    for i in range(min(40, len(raw_df))):
        row_values = {str(v).strip().upper() for v in raw_df.iloc[i].values if pd.notna(v)}
        if REQUIRED_COLUMNS.issubset(row_values):
            header_row_idx = i
            break

    df = pd.read_excel(BytesIO(file_bytes), header=header_row_idx)
    df.columns = [c.strip().upper() for c in df.columns]

    sv = SubjectVersion.query.get(subject_version_id)

    for _, row in df.iterrows():
        question_text = str(row["QUESTIONS"]).strip()
        unit = int(row["UNIT"])
        section = str(row["SECTION"]).strip().upper()
        k_level = str(row.get("K LEVEL", "N/A")).strip()
        marks = sv.pattern.structure_json["sections"][section]["marks"]

        q_hash = _hash(question_text) # (Uses the helper _hash function for text)

        # Check QuestionMaster
        master = QuestionMaster.query.filter_by(
            subject_id=sv.subject_id,
            question_hash=q_hash
        ).first()

        if not master:
            master = QuestionMaster(
                subject_id=sv.subject_id,
                question_hash=q_hash,
                question_text=question_text,
                default_unit=unit,
                default_section=section,
                default_marks=marks,
                k_level=k_level
            )
            db.session.add(master)
            db.session.flush()

        # Insert Item
        item = QuestionBankItem(
            question_bank_id=bank.id,
            question_id=master.id,
            unit=unit,
            section=section,
            marks=marks,
            k_level=k_level
        )
        db.session.add(item)

    db.session.commit()
    return bank