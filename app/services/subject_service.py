# app/services/subject_service.py
import pandas as pd
from io import StringIO
from sqlalchemy.sql import exists

from app.extensions import db
from app.models.subject import Subject
from app.models.subject_version import SubjectVersion
from app.models.department import Department
from app.models.grid_type import GridType
from app.models.weightage import SubjectWeightage
from app.models.question_paper import QuestionPaper
from app.models.question_bank import QuestionBank

# =========================================================
# SUBJECT READ OPERATIONS
# =========================================================

def get_subjects(department_id=None, semester=None, batch=None):
    """
    Returns SubjectVersion-based subject list
    filtered by department / semester / batch
    """

    query = (
        db.session.query(SubjectVersion)
        .join(Subject)
        .filter(SubjectVersion.is_active == True)
    )

    if department_id:
        query = query.filter(SubjectVersion.department_id == department_id)

    if semester:
        query = query.filter(SubjectVersion.semester == semester)

    if batch:
        query = query.filter(SubjectVersion.batch == batch)

    return (
        query
        .order_by(Subject.code, SubjectVersion.version)
        .all()
    )


def get_subject_version_by_id(subject_version_id: int) -> SubjectVersion:
    return SubjectVersion.query.get_or_404(subject_version_id)

# =========================================================
# SUBJECT CREATE (NEW VERSION)
# =========================================================

def get_next_subject_version(subject_id: int, department_id: int, batch: int) -> int:
    """
    Version is per (subject + department + batch)
    """
    latest = (
        SubjectVersion.query
        .filter_by(
            subject_id=subject_id,
            department_id=department_id,
            batch=batch
        )
        .order_by(SubjectVersion.version.desc())
        .first()
    )
    return 1 if not latest else latest.version + 1


def add_subject_version(code, name, department_id, semester, batch, grid_type_id, pattern_id):
    """
    Creates a NEW subject version and handles the master Subject record.
    """
    if not all([code, name, department_id, semester, batch, grid_type_id, pattern_id]):
        raise ValueError("All fields are required")

    # 1. Handle Master Subject (Code & Grid Type)
    subject = Subject.query.filter_by(code=code.strip().upper()).first()
    if not subject:
        subject = Subject(
            code=code.strip().upper(),
            name=name.strip(),
            grid_type_id=grid_type_id
        )
        db.session.add(subject)
        db.session.flush() # Get subject.id
    else:
        # Update name or grid type if they changed in the master record
        subject.name = name.strip()
        subject.grid_type_id = grid_type_id

    # 2. Handle Versioning
    version = get_next_subject_version(subject.id, department_id, batch)

    # 3. Deactivate previous active versions for this context
    SubjectVersion.query.filter_by(
        subject_id=subject.id,
        department_id=department_id,
        batch=batch,
        is_active=True
    ).update({"is_active": False})

    # 4. Create New SubjectVersion (Link Pattern here)
    sv = SubjectVersion(
        subject_id=subject.id,
        department_id=department_id,
        semester=semester,
        batch=batch,
        version=version,
        pattern_id=pattern_id,
        is_active=True
    )

    db.session.add(sv)
    db.session.commit()
    return sv

# =========================================================
# SUBJECT CSV EXPORT
# =========================================================

def get_subjects_as_csv(batch=None, semester=None, department_id=None):
    """
    Export ACTIVE subject versions only.
    """

    records = get_subjects(batch, semester, department_id)

    rows = []
    # ✅ FIX: Iterate through SubjectVersion objects directly
    for sv in records:
        rows.append({
            "Code": sv.subject.code,
            "Subject Name": sv.subject.name,
            "Department": sv.department.name if sv.department else "",
            "Semester": sv.semester,
            "Batch": sv.batch,
            "Version": sv.version,
            "Grid Type": sv.subject.grid_type.name if sv.subject.grid_type else ""
        })

    df = pd.DataFrame(rows)

    buffer = StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    return buffer

# =========================================================
# SUPPORT / DROPDOWNS
# =========================================================

def get_grid_types():
    return GridType.query.order_by(GridType.name).all()


def get_all_departments():
    return Department.query.order_by(Department.name).all()


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def get_semesters_by_department(department_id: int):
    return (
        db.session.query(SubjectVersion.semester)
        .filter(SubjectVersion.department_id == department_id)
        .distinct()
        .order_by(SubjectVersion.semester)
        .all()
    )


def get_batches_by_department_and_semester(department_id: int, semester: int):
    return (
        db.session.query(SubjectVersion.batch)
        .filter(
            SubjectVersion.department_id == department_id,
            SubjectVersion.semester == semester
        )
        .distinct()
        .order_by(SubjectVersion.batch)
        .all()
    )


def get_subject_versions(department_id=None, semester=None, batch=None, school_id=None ):
    query = (
        db.session.query(SubjectVersion)
        .join(Subject)
        .filter(SubjectVersion.is_active == True)
    )

    # Only join and filter by school if school_id is provided (Staff logic)
    if school_id:
        query = query.join(Department).filter(Department.school_id == school_id)
        
    if department_id:
        query = query.filter(SubjectVersion.department_id == department_id)

    if semester:
        query = query.filter(SubjectVersion.semester == semester)

    if batch:
        query = query.filter(SubjectVersion.batch == batch)

    return query.order_by(Subject.code).all()


def can_delete_subject_version(subject_version_id: int) -> bool:
    """
    Checks if a subject version can be safely deleted.
    It cannot be deleted if it has associated weightage records.
    """
    has_weightage = db.session.query(
        exists().where(SubjectWeightage.subject_version_id == subject_version_id)
    ).scalar()
    
    return not has_weightage


# =========================================================
# DELETE OPERATIONS (With Safety Checks)
# =========================================================

def _check_dependencies(subject_version_id: int):
    """
    Helper to check if a subject is used in Papers or Banks.
    Raises ValueError if dependencies exist.
    """
    # 1. Check Question Papers
    paper_count = QuestionPaper.query.filter_by(subject_version_id=subject_version_id).count()
    if paper_count > 0:
        raise ValueError(
            f"Cannot delete: There are {paper_count} Question Paper(s) generated using this subject. "
            "Please delete them first."
        )

    # 2. Check Question Banks
    bank_count = QuestionBank.query.filter_by(subject_version_id=subject_version_id).count()
    if bank_count > 0:
        raise ValueError(
            f"Cannot delete: There is a Question Bank linked to this subject. "
            "Please delete the Question Bank first."
        )

def delete_subject_version_only(subject_version_id: int):
    """
    Deletes only the subject version. Fails if weightages OR papers/banks exist.
    """
    sv = SubjectVersion.query.get_or_404(subject_version_id)
    
    # 1. Check Weightage (Existing Check)
    has_weightage = SubjectWeightage.query.filter_by(subject_version_id=subject_version_id).first()
    if has_weightage:
        raise ValueError(f"Cannot delete {sv.subject.name}: Weightage data exists. Use 'Delete Subject & Weightage' instead.")

    # 2. Check External Dependencies (Papers/Banks)
    _check_dependencies(subject_version_id)

    # 3. Safe to Delete
    db.session.delete(sv)
    db.session.commit()

def delete_subject_and_weightage(subject_version_id: int):
    """
    Deletes both the subject version and all associated weightages.
    Fails if papers/banks exist.
    """
    sv = SubjectVersion.query.get_or_404(subject_version_id)
    
    # 1. Check External Dependencies (Papers/Banks)
    # Even if we want to delete weightage, we MUST NOT delete if papers exist.
    _check_dependencies(subject_version_id)
    
    # 2. Delete Weightage
    SubjectWeightage.query.filter_by(subject_version_id=subject_version_id).delete()
    
    # 3. Delete Subject
    db.session.delete(sv)
    db.session.commit()