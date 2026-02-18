import pandas as pd
from io import StringIO
from app.extensions import db
from app.models.school import School
from app.models.department import Department

def get_all_schools():
    return School.query.order_by(School.name).all()


def add_school(name: str):
    if not name:
        raise ValueError("School name is required")

    school = School(name=name.strip())
    db.session.add(school)
    db.session.commit()


def delete_school(school_id: int):
    school = School.query.get_or_404(school_id)

    # 🔒 Dependency check (same logic as Streamlit safe_delete)
    if Department.query.filter_by(school_id=school.id).count() > 0:
        raise ValueError("Cannot delete school with existing departments")

    db.session.delete(school)
    db.session.commit()


def get_schools_as_csv():
    schools = get_all_schools()

    data = [
        {
            "ID": s.id,
            "School Name": s.name
        }
        for s in schools
    ]

    df = pd.DataFrame(data)

    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)

    return csv_buffer
