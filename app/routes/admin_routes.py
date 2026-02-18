# app/routes/admin_routes.py
from app.extensions import db
from app.models.pattern import Pattern
from app.models.question_paper import QuestionPaper
from app.models.question_bank import QuestionBank
from app.models.question_master import QuestionMaster
import os
from flask import (Response, jsonify, Blueprint,
                   render_template, request,
                   redirect, url_for, flash, session, send_file)
from app.models.subject_version import SubjectVersion
from app.models.user import User
from app.utils.decorators import login_required, role_required
# Update the import source and function names
from app.services.question_paper_docx_service import (
    generate_question_paper_docx, 
    generate_official_docx
)
from app.services.user_service import (
    get_all_users,
    create_user,
    delete_user,
    reset_user_password,
    reset_user_school_access,
    update_user_schools
)
from app.services.school_service import (
    get_all_schools,
    add_school,
    delete_school,
    get_schools_as_csv
)
from app.services.department_service import (
     get_departments,
    add_department,
    delete_department,
    can_delete_department,
    get_departments_as_csv,
    get_departments_by_school,
)
from app.services.subject_service import (
    get_batches_by_department_and_semester,
    get_semesters_by_department,
    get_subject_versions,
    get_subjects,
    add_subject_version,
    get_subjects_as_csv,
    get_grid_types,
    delete_subject_version_only,
    delete_subject_and_weightage,
    get_subject_version_by_id,
)


from app.services.weightage_service import (
    add_or_update_multiple_weightages,
    delete_weightage_by_subject_version,
    get_weightage_by_subject_version
)

from app.services.pattern_service import (
    get_patterns,
    create_pattern_from_form,
    delete_pattern,
    format_pattern_sections
)


admin_bp = Blueprint("admin", __name__)

@admin_bp.route('/')
@login_required
@role_required('admin')
def dashboard():  # Ensure this function name matches your template's url_for('admin.dashboard')
    from app.models.school import School
    from app.models.department import Department
    from app.models.user import User
    from app.models.subject_version import SubjectVersion
    from app.models.question_paper import QuestionPaper

    # Gather System Statistics
    stats = {
        'total_schools': School.query.count(),
        'total_departments': Department.query.count(),
        'total_users': User.query.count(),
        'total_subjects': SubjectVersion.query.filter_by(is_active=True).count(),
        'total_papers': QuestionPaper.query.count(),
        'DRAFT': QuestionPaper.query.filter_by(status='DRAFT').count(),
        'UNDER_SCRUTINY': QuestionPaper.query.filter_by(status='UNDER_SCRUTINY').count(),
        'ACTIVE': QuestionPaper.query.filter_by(status='ACTIVE').count()
    }

    # ---------------------------------------------------------
    # ✅ ADD THIS: Fetch Recently Activated Papers
    # ---------------------------------------------------------
    recent_papers = (
        QuestionPaper.query
        .filter_by(status='ACTIVE')
        .order_by(QuestionPaper.last_modified_at.desc())  # Or activated_at if you have that column
        .limit(5)
        .all()
    )

    return render_template(
        'admin/dashboard.html', 
        stats=stats,
        total_papers=stats['total_papers'],
        recent_papers=recent_papers  # 👈 Pass this variable to the template
    )

@admin_bp.route("/users", methods=["GET", "POST"])
@login_required
@role_required("admin")
def manage_users():
    error_msg = None
    success_msg = None

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        role = request.form.get("role")
        school_ids = request.form.getlist("school_ids") # Multi-select for production

        try:
            create_user(username, password, role, school_ids)
            success_msg = f"User: {username}\nRole: {role}\nPermission schools: {', '.join(school_ids) if school_ids else 'None'} created successfully."
        except ValueError as e:
            error_msg = str(e)
        except Exception as e:
            error_msg = "An unexpected error occurred during user creation."

    
    return render_template(
        "admin/users.html",
        users=get_all_users(),
        schools=get_all_schools(), # Reusing school service
        error=error_msg,
        success=success_msg
    )

# app/routes/admin_routes.py

@admin_bp.route("/users/<int:user_id>/access")
@login_required
@role_required("admin")
def get_user_access(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify({
        "school_ids": [s.id for s in user.schools]
    })


@admin_bp.route("/users/update-access", methods=["POST"])
@login_required
@role_required("admin")
def update_access():
    user_id = request.form.get("user_id", type=int)
    school_ids = request.form.getlist("school_ids")
    try:
        update_user_schools(user_id, school_ids)
        return jsonify({"success": True, "message": "Access updated successfully."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@admin_bp.route("/users/delete", methods=["POST"])
@login_required
@role_required("admin")
def remove_user():
    user_id = request.form.get("user_id", type=int)
    # ✅ Get the logged-in admin's ID from the session
    current_admin_id = session.get('user_id')
    
    try:
        # ✅ Pass both required arguments to the service
        delete_user(user_id, current_admin_id)
        return jsonify({"success": True})
    except ValueError as e:
        # This catches the "cannot delete your own account" error
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": "System error"}), 500

@admin_bp.route("/users/reset-schools", methods=["POST"])
@login_required
@role_required("admin")
def reset_schools():
    user_id = request.form.get("user_id", type=int)
    try:
        reset_user_school_access(user_id)
        return jsonify({"success": True, "message": "School access cleared."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400
@admin_bp.route("/users/reset-password", methods=["POST"])
@login_required
@role_required("admin")
def admin_reset_password():
    user_id = request.form.get("user_id", type=int)
    new_password = request.form.get("new_password")
    
    if not new_password or len(new_password) < 6:
        return redirect(url_for("admin.manage_users", msg="Password must be at least 6 characters", msg_type="error"))
        
    try:
        reset_user_password(user_id, new_password)
        return redirect(url_for("admin.manage_users", 
                                msg="Password reset successfully", 
                                msg_type="success"))
    except Exception as e:
        return redirect(url_for("admin.manage_users", 
                                msg=str(e), 
                                msg_type="error"))
        
# =========================
# SCHOOLS
# =========================

@admin_bp.route("/schools", methods=["GET", "POST"])
@login_required
@role_required("admin")
def manage_schools():
    if request.method == "POST":
        name = request.form.get("name")
        try:
            add_school(name)
            flash("School added successfully", "success")
        except Exception as e:
            flash(str(e), "danger")
        return redirect(url_for("admin.manage_schools"))

    schools = get_all_schools()
    return render_template("admin/schools.html", schools=schools)


@admin_bp.route("/schools/delete", methods=["POST"])
@login_required
@role_required("admin")
def remove_school():
    schools = get_all_schools()
    error = None

    school_id = request.form.get("school_id")

    try:
        delete_school(int(school_id))
        flash("School deleted successfully", "success")
        return redirect(url_for("admin.manage_schools"))
    except Exception as e:
        error = str(e)

    # 👇 render SAME page with inline error
    return render_template(
        "admin/schools.html",
        schools=schools,
        delete_error=error
    )


@admin_bp.route("/schools/download")
@login_required
@role_required("admin")
def download_schools_csv():
    csv_buffer = get_schools_as_csv()

    return Response(
        csv_buffer.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=schools.csv"
        }
    )

@admin_bp.route("/schools/check-delete/<int:school_id>")
@login_required
@role_required("admin")
def check_school_delete(school_id):
    try:
        # call existing logic
        delete_school(school_id)
        return jsonify({"can_delete": True})
    except Exception:
        return jsonify({
            "can_delete": False,
            "message": "School has dependent departments or subjects. Please delete them first."
        })

@admin_bp.route("/departments", methods=["GET", "POST"])
@login_required
@role_required("admin")
def manage_departments():
    if request.method == "POST":
        try:
            add_department(
                request.form.get("code"),
                request.form.get("name"),
                request.form.get("level"),
                int(request.form.get("school_id"))
            )
            flash("Department added successfully", "success")
            return redirect(url_for("admin.manage_departments"))
        except Exception as e:
            flash(str(e), "danger")

    return render_template(
        "admin/departments.html",
        departments=get_departments(),
        schools=get_all_schools()
    )


@admin_bp.route("/departments/check-delete/<int:dept_id>")
@login_required
@role_required("admin")
def check_department_delete(dept_id):
    if can_delete_department(dept_id):
        return jsonify({"can_delete": True})

    return jsonify({
        "can_delete": False,
        "message": "Department has dependent subjects. Please delete them first."
    })


@admin_bp.route("/departments/delete", methods=["POST"])
@login_required
@role_required("admin")
def remove_department():
    delete_department(int(request.form["dept_id"]))
    flash("Department deleted successfully", "success")
    return redirect(url_for("admin.manage_departments"))


@admin_bp.route("/departments/download")
@login_required
@role_required("admin")
def download_departments_csv():
    csv_buffer = get_departments_as_csv()
    return Response(
        csv_buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=departments.csv"}
    )

# =========================
# SUBJECTS
# =========================

@admin_bp.route("/subjects", methods=["GET", "POST"])
@login_required
@role_required("admin")
def manage_subjects():

    # Filters
    department_id = request.args.get("department_id", type=int)
    semester = request.args.get("semester", type=int)
    batch = request.args.get("batch", type=int)

    if request.method == "POST":
        try:
            add_subject_version(
                code=request.form["code"],
                name=request.form["name"],
                department_id=int(request.form["department_id"]),
                semester=int(request.form["semester"]),
                batch=int(request.form["batch"]),
                grid_type_id=int(request.form["grid_type_id"]),
                pattern_id=int(request.form["pattern_id"]) if request.form.get("pattern_id") else None
            )

            return redirect(
                url_for(
                    "admin.manage_subjects",
                    msg="Subject created successfully",
                    msg_type="success"
                )
            )
        except Exception as e:
            return redirect(
                url_for(
                    "admin.manage_subjects",
                    msg=str(e),
                    msg_type="error"
                )
            )

    subjects = get_subjects(
            batch=batch,
            semester=semester
        )


    return render_template(
            "admin/subjects.html",
            subjects=subjects,
            schools=get_all_schools(),   # 🔥 THIS WAS MISSING
            grid_types=get_grid_types(),
            patterns=get_patterns(),
            department_id=department_id,
            semester=semester,
            batch=batch
        )




@admin_bp.route("/subjects/download")
@login_required
@role_required("admin")
def download_subjects_csv():
    buffer = get_subjects_as_csv()
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=subjects.csv"}
    )


@admin_bp.route("/subjects/departments/<int:school_id>")
@login_required
@role_required("admin")
def get_departments_for_subject(school_id):
    depts = get_departments_by_school(school_id)
    return jsonify([
        {"id": d.id, "name": d.name}
        for d in depts
    ])


# app/routes/admin_routes.py

@admin_bp.route("/subjects/delete", methods=["POST"])
@login_required
@role_required("admin")
def remove_subject():
    subject_version_id = request.form.get("subject_version_id", type=int)
    action = request.form.get("action") 
    
    try:
        if action == "both":
            delete_subject_and_weightage(subject_version_id)
        else:
            delete_subject_version_only(subject_version_id)
            
        return jsonify({"success": True, "id": subject_version_id})
        
    except ValueError as e:
        # Expected logic errors (e.g., weightage exists)
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        # ✅ FIX: Catch unexpected server errors and return JSON
        db.session.rollback()
        return jsonify({"success": False, "message": f"System Error: {str(e)}"}), 500  

      
@admin_bp.route("/weightage", methods=["GET", "POST"])
@login_required
@role_required("admin")
def manage_weightage():

    department_id = request.args.get("department_id", type=int)
    semester = request.args.get("semester", type=int)
    batch = request.args.get("batch", type=int)
    subject_version_id = request.args.get("subject_version_id", type=int)
    subject_version = SubjectVersion.query.get(subject_version_id) if subject_version_id else None
    

    error_message = None
    success_message = None
    
    if request.method == "POST":
        rows = []
        for unit in range(1, 6):
           rows.append({
                "unit": unit,
                "a": int(request.form.get(f"sec_a_{unit}", 0)),
                "b": int(request.form.get(f"sec_b_{unit}", 0)),
                "c": int(request.form.get(f"sec_c_{unit}", 0))
            })

        try:
            add_or_update_multiple_weightages(subject_version_id, rows)
            success_message = "Weightage saved successfully."
                    
        except ValueError as e:
            # Capture the validation error directly
            error_message = str(e)

    subjects = get_subject_versions(
        department_id=department_id,
        semester=semester,
        batch=batch
    )
    semesters = (
            [s[0] for s in get_semesters_by_department(department_id)]
            if department_id else []
        )

    batches = (
            [b[0] for b in get_batches_by_department_and_semester(department_id, semester)]
            if department_id and semester else []
        )


    weightages = (get_weightage_by_subject_version(subject_version_id)
                  if subject_version_id else []
                  )

    return render_template(
        "admin/weightage.html",
        subjects=subjects,
        departments=get_departments(),
        semesters=semesters,
        batches=batches,
        selected_subject_id=subject_version_id,
        department_id=department_id,
        semester=semester,
        batch=batch,
        weightages=weightages,
        error_message=error_message,
        success_message=success_message,
        subject_version=subject_version
    )


@admin_bp.route("/weightage/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_weightage():
    subject_version_id = int(request.form["subject_version_id"])
    delete_weightage_by_subject_version(subject_version_id)
    return redirect(
        url_for(
            "admin.manage_weightage",
            subject_id=subject_version_id,
            msg="Weightage deleted",
            msg_type="success"
        )
    )
# =========================
# PATTERNS
# =========================

@admin_bp.route("/patterns", methods=["GET", "POST"])
@login_required
@role_required("admin")
def manage_patterns():

    success = None
    error = None

    if request.method == "POST":
        try:
            create_pattern_from_form(request.form)
            success = f'Pattern "{request.form["name"]}" created successfully'
        except Exception as e:
            db.session.rollback()
            error = str(e)

    patterns = get_patterns()

    pattern_views = []
    for p in patterns:
        pattern_views.append({
            "name": p.name,
            "total_marks": p.total_marks,
            "sections": format_pattern_sections(p)
        })

    return render_template(
        "admin/patterns.html",
        success=success,
        error=error,
        pattern_views=pattern_views   # ✅ correct name
    )




@admin_bp.route("/patterns/delete", methods=["POST"])
@login_required
@role_required("admin")
def remove_pattern():
    try:
        name = request.form["pattern_name"]
        pattern = Pattern.query.filter_by(name=name).first_or_404()
        db.session.delete(pattern)
        db.session.commit()
        return redirect(url_for("admin.manage_patterns", success=f'Pattern "{name}" deleted'))
    except Exception as e:
        db.session.rollback()
        return redirect(url_for("admin.manage_patterns", error=str(e)))


# =========================================================
# PAPER ARCHIVE (ADMIN)
# =========================================================

@admin_bp.route("/all-papers")
@login_required
@role_required("admin")
def all_generated_papers():
    """
    Admin View: ALL generated papers from ALL users with Delete option.
    """
    from app.models.question_paper import QuestionPaper
    from app.models.subject_version import SubjectVersion
    from app.models.department import Department
    from app.models.user import User
    
    # 1. Get Filters
    school_id = request.args.get("school_id", type=int)
    dept_id = request.args.get("department_id", type=int)
    subject_id = request.args.get("subject_version_id", type=int)
    batch = request.args.get("batch", type=int)
    f_status = request.args.get("status")
    f_type = request.args.get("paper_type")

    # 2. Build Query (No User Filter = View All)
    query = (
        db.session.query(QuestionPaper)
        .join(SubjectVersion)
        .join(SubjectVersion.department)
        .join(User, QuestionPaper.created_by == User.id)
    )

    # 3. Apply Filters
    if school_id:
        query = query.filter(Department.school_id == school_id)
    if dept_id:
        query = query.filter(SubjectVersion.department_id == dept_id)
    if subject_id:
        query = query.filter(QuestionPaper.subject_version_id == subject_id)
    if batch:
        query = query.filter(SubjectVersion.batch == batch)
    if f_status:
        query = query.filter(QuestionPaper.status == f_status)
    if f_type:
        query = query.filter(QuestionPaper.paper_type == f_type)

    # 4. Execute
    papers = query.order_by(QuestionPaper.last_modified_at.desc()).all()
    total_count = len(papers)

    # 5. Dropdown Data
    schools = get_all_schools()
    departments = get_departments_by_school(school_id) if school_id else []
    
    # Fetch subjects based on context
    subjects_query = SubjectVersion.query
    if dept_id: subjects_query = subjects_query.filter_by(department_id=dept_id)
    subjects = subjects_query.all() if dept_id else []

    batches = db.session.query(SubjectVersion.batch).distinct().order_by(SubjectVersion.batch.desc()).all()
    batches = [b[0] for b in batches]

    return render_template(
        "admin/all_papers.html",
        papers=papers,
        total_count=total_count,
        schools=schools,
        departments=departments,
        subjects=subjects,
        batches=batches,
        sel_school=school_id,
        sel_dept=dept_id,
        sel_subject=subject_id,
        sel_batch=batch,
        sel_status=f_status,
        sel_type=f_type
    )

@admin_bp.route("/all-papers/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_paper():
    """
    Permanently delete a question paper.
    """
    paper_id = request.form.get("paper_id", type=int)
    paper = QuestionPaper.query.get_or_404(paper_id)
    
    try:
        db.session.delete(paper)
        db.session.commit()
        flash(f"Paper {paper.paper_code} deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting paper: {str(e)}", "danger")
        
    return redirect(request.referrer or url_for('admin.all_generated_papers'))

# --- Admin Download Wrappers ---

@admin_bp.route("/paper/<int:paper_id>/download/student")
@login_required
@role_required("admin")
def download_student_paper(paper_id):
    paper = QuestionPaper.query.get_or_404(paper_id)
    
    # ✅ FIX: Get the BytesIO stream directly (Service does NOT accept filepath)
    docx_stream = generate_question_paper_docx(paper)
    
    return send_file(
        docx_stream,
        as_attachment=True,
        download_name=f"{paper.paper_code}_Student_Copy.docx",
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

@admin_bp.route("/paper/<int:paper_id>/download/official")
@login_required
@role_required("admin")
def download_official_paper(paper_id):
    paper = QuestionPaper.query.get_or_404(paper_id)
    
    # ✅ FIX: Get the BytesIO stream directly (Service does NOT accept filepath)
    docx_stream = generate_official_docx(paper)
    
    return send_file(
        docx_stream,
        as_attachment=True,
        download_name=f"{paper.paper_code}_Official_Copy.docx",
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


# =========================================================
# QUESTION BANK ARCHIVE (ADMIN)
# =========================================================

@admin_bp.route("/question-banks")
@login_required
@role_required("admin")
def all_question_banks():
    """
    Admin View: ALL uploaded question banks with Filters & Delete option.
    """
    from app.models.question_bank import QuestionBank
    from app.models.subject_version import SubjectVersion
    from app.models.department import Department
    from app.models.user import User
    
    # 1. Get Filters
    school_id = request.args.get("school_id", type=int)
    dept_id = request.args.get("department_id", type=int)
    subject_id = request.args.get("subject_version_id", type=int)
    batch = request.args.get("batch", type=int)
    
    f_status = request.args.get("status")
    f_default = request.args.get("is_default") # '1' for True, '0' for False

    # 2. Build Query
    query = (
        db.session.query(QuestionBank)
        .join(SubjectVersion)
        .join(SubjectVersion.department)
        .join(User, QuestionBank.uploaded_by == User.id)
    )

    # 3. Apply Context Filters
    if school_id:
        query = query.filter(Department.school_id == school_id)
    if dept_id:
        query = query.filter(SubjectVersion.department_id == dept_id)
    if subject_id:
        query = query.filter(QuestionBank.subject_version_id == subject_id)
    if batch:
        query = query.filter(SubjectVersion.batch == batch)

    # 4. Apply Grid Filters
    if f_status:
        query = query.filter(QuestionBank.status == f_status)
    if f_default:
        is_def = True if f_default == '1' else False
        query = query.filter(QuestionBank.is_default == is_def)

    # 5. Execute
    banks = query.order_by(QuestionBank.uploaded_at.desc()).all()
    total_count = len(banks)

    # 6. Dropdown Data
    schools = get_all_schools()
    departments = get_departments_by_school(school_id) if school_id else []
    
    subjects_query = SubjectVersion.query
    if dept_id: subjects_query = subjects_query.filter_by(department_id=dept_id)
    subjects = subjects_query.all() if dept_id else []

    batches = db.session.query(SubjectVersion.batch).distinct().order_by(SubjectVersion.batch.desc()).all()
    batches = [b[0] for b in batches]

    return render_template(
        "admin/all_question_banks.html",
        banks=banks,
        total_count=total_count,
        schools=schools,
        departments=departments,
        subjects=subjects,
        batches=batches,
        # Selected Values
        sel_school=school_id,
        sel_dept=dept_id,
        sel_subject=subject_id,
        sel_batch=batch,
        sel_status=f_status,
        sel_default=f_default
    )

@admin_bp.route("/question-banks/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_question_bank():
    """
    Permanently delete a question bank.
    """
    bank_id = request.form.get("bank_id", type=int)
    bank = QuestionBank.query.get_or_404(bank_id)
    
    try:
        # Note: 'items' cascade delete is handled by model relationship
        db.session.delete(bank)
        db.session.commit()
        flash(f"Question Bank #{bank.id} deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting bank: {str(e)}", "danger")
        
    return redirect(url_for('admin.all_question_banks'))

# =========================================================
# MASTER QUESTION ARCHIVE (ADMIN)
# =========================================================

@admin_bp.route("/question-master")
@login_required
@role_required("admin")
def all_questions():
    """
    Admin View: ALL Unique Questions (QuestionMaster) with Filters & Delete.
    """
    from app.models.question_master import QuestionMaster
    from app.models.subject import Subject
    from app.models.subject_version import SubjectVersion
    from app.models.department import Department
    from app.models.school import School
    
    # 1. Get Filters
    school_id = request.args.get("school_id", type=int)
    dept_id = request.args.get("department_id", type=int)
    subject_version_id = request.args.get("subject_version_id", type=int)
    batch = request.args.get("batch", type=int)
    
    # Granular Filters
    f_unit = request.args.get("unit", type=int)
    f_marks = request.args.get("marks", type=int)
    f_klevel = request.args.get("k_level")

    # 2. Build Query (Start with Master)
    query = db.session.query(QuestionMaster)

    # 3. Join for Context (Subject -> Version -> Dept -> School)
    query = query.join(Subject, QuestionMaster.subject_id == Subject.id)
    query = query.join(SubjectVersion, Subject.id == SubjectVersion.subject_id)
    query = query.join(Department, SubjectVersion.department_id == Department.id)
    query = query.join(School, Department.school_id == School.id)

    # 4. Apply Context Filters
    if school_id:
        query = query.filter(Department.school_id == school_id)
    if dept_id:
        query = query.filter(SubjectVersion.department_id == dept_id)
    if subject_version_id:
        # Filter by the generic Subject ID of the selected version
        sv = SubjectVersion.query.get(subject_version_id)
        if sv:
            query = query.filter(QuestionMaster.subject_id == sv.subject_id)
    if batch:
        query = query.filter(SubjectVersion.batch == batch)

    # 5. Apply Content Filters
    if f_unit:
        query = query.filter(QuestionMaster.default_unit == f_unit)
    if f_marks:
        query = query.filter(QuestionMaster.default_marks == f_marks)
    if f_klevel:
        query = query.filter(QuestionMaster.k_level == f_klevel)

    # 6. Execute (Distinct is crucial here due to joins)
    questions = query.distinct(QuestionMaster.id).order_by(QuestionMaster.id.desc()).all()
    total_count = len(questions)

    # 7. Dropdown Data
    schools = get_all_schools()
    departments = get_departments_by_school(school_id) if school_id else []
    
    subjects_query = SubjectVersion.query
    if dept_id: subjects_query = subjects_query.filter_by(department_id=dept_id)
    subjects = subjects_query.all() if dept_id else []

    batches = db.session.query(SubjectVersion.batch).distinct().order_by(SubjectVersion.batch.desc()).all()
    batches = [b[0] for b in batches]

    return render_template(
        "admin/all_questions.html",
        questions=questions,
        total_count=total_count,
        schools=schools,
        departments=departments,
        subjects=subjects,
        batches=batches,
        # Selected Values
        sel_school=school_id,
        sel_dept=dept_id,
        sel_subject=subject_version_id,
        sel_batch=batch,
        sel_unit=f_unit,
        sel_marks=f_marks,
        sel_klevel=f_klevel
    )

@admin_bp.route("/question-master/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_question():
    """
    Permanently delete a Master Question.
    """
    question_id = request.form.get("question_id", type=int)
    q = QuestionMaster.query.get_or_404(question_id)
    
    try:
        # This will fail if QuestionBankItems exist and cascade isn't set up on that side.
        # Assuming you want to force delete or have cascades:
        db.session.delete(q)
        db.session.commit()
        flash(f"Question #{question_id} deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        # Friendly error message for Foreign Key constraints
        if "foreign key constraint" in str(e).lower():
            flash("Cannot delete: This question is used in active Question Banks or Papers.", "danger")
        else:
            flash(f"Error deleting question: {str(e)}", "danger")
        
    return redirect(url_for('admin.all_questions'))