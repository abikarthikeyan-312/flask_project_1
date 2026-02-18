import pandas as pd
from io import StringIO
from sqlalchemy.sql import exists

from app.extensions import db
from app.models.department import Department
from app.models.school import School
from app.models.subject_version import SubjectVersion


# ----------------------------
# READ
# ----------------------------

def get_departments_by_school(school_id: int):
    return (
        Department.query
        .filter_by(school_id=school_id)
        .order_by(Department.name)
        .all()
    )


def get_departments():
    return (
        Department.query
        .join(School)
        .order_by(School.name, Department.name)
        .all()
    )


# ----------------------------
# CREATE
# ----------------------------

def add_department(code: str, name: str, level: str, school_id: int):
    if not name or not level or not school_id:
        raise ValueError("All fields are required")

    dept = Department(
        code=code.strip(),
        name=name.strip(),
        level=level,
        school_id=school_id
    )
    db.session.add(dept)
    db.session.commit()


# ----------------------------
# DELETE (SAFE)
# ----------------------------

def can_delete_department(dept_id: int) -> bool:
    """
    A department can be deleted ONLY if no subject_version references it.
    """
    return not db.session.query(
        exists().where(SubjectVersion.department_id == dept_id)
    ).scalar()


def delete_department(dept_id: int):
    dept = Department.query.get_or_404(dept_id)

    if not can_delete_department(dept_id):
        raise ValueError(
            "Department has dependent subjects. Please delete them first."
        )

    db.session.delete(dept)
    db.session.commit()


# ----------------------------
# CSV EXPORT
# ----------------------------

def get_departments_as_csv():
    depts = get_departments()

    data = [
        {
            "ID": d.id,
            "Department": d.name,
            "Level": d.level,
            "School": d.school.name
        }
        for d in depts
    ]

    df = pd.DataFrame(data)
    buffer = StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    return buffer
