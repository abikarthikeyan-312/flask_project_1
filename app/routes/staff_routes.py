# app/routes/staff_routes.py
from flask import (Blueprint, render_template, request, session, redirect, url_for, jsonify,flash, send_file)
from sqlalchemy import distinct,func

from app.utils.decorators import login_required, role_required
from app.extensions import db
from app.models.user import User
from app.models.department import Department
from app.models.question_bank import QuestionBank, QuestionBankItem
from app.models.subject_version import SubjectVersion
from app.models.pattern import Pattern
from app.models.question_paper import QuestionPaper
from app.models.question_paper_item import QuestionPaperItem

from app.services.subject_service import get_subject_versions
from app.services.weightage_service import get_weightage_by_subject_version
from app.services.school_service import get_all_schools
from app.services.department_service import get_departments_by_school
from app.services.question_paper_service import generate_question_paper_skeleton
from app.services.question_bank_excel_validation_service import validate_question_bank_excel
from app.services.question_paper_docx_service import generate_official_docx, generate_question_paper_docx
from app.services.question_paper_selection_service import auto_select_questions_for_paper
from app.services.question_paper_edit_service import swap_question_with_bank
from app.services.question_paper_edit_service import apply_manual_edit
from app.services.question_paper_activation_service import activate_question_paper
from app.services.question_paper_edit_service import mark_duplicate



staff_bp = Blueprint("staff", __name__)

# =========================================================
# STAFF DASHBOARD
# =========================================================

@staff_bp.route("/")
@login_required
@role_required("staff")
def staff_home():
    """
    Advanced Dashboard with Filters and Unified Analytics.
    """
    user_id = session["user_id"]
    
    # 1. Get Filter Parameters
    school_id = request.args.get("school_id", type=int)
    dept_id = request.args.get("department_id", type=int)
    subject_id = request.args.get("subject_version_id", type=int)

    # 3. Base Queries (User Isolated)
    banks_query = QuestionBank.query.filter_by(uploaded_by=user_id)
    papers_query = QuestionPaper.query.filter_by(created_by=user_id)

    # 4. Apply Filters dynamically
    if subject_id:
        banks_query = banks_query.filter_by(subject_version_id=subject_id)
        papers_query = papers_query.filter_by(subject_version_id=subject_id)
    elif dept_id:
        # Join SubjectVersion to filter by Dept
        banks_query = banks_query.join(SubjectVersion).filter(SubjectVersion.department_id == dept_id)
        papers_query = papers_query.join(SubjectVersion).filter(SubjectVersion.department_id == dept_id)
    elif school_id:
        # Join SubjectVersion -> Department to filter by School
        banks_query = banks_query.join(SubjectVersion).join(SubjectVersion.department).filter(Department.school_id == school_id)
        papers_query = papers_query.join(SubjectVersion).join(SubjectVersion.department).filter(Department.school_id == school_id)

    # 5. Execute Stats
    total_banks = banks_query.count()
    total_papers = papers_query.count()

    # Status Breakdown
    # Get IDs first to avoid ambiguous join issues in the group_by query
    paper_ids_for_status = [p.id for p in papers_query.with_entities(QuestionPaper.id).all()]
    
    status_counts = []
    if paper_ids_for_status:
        status_counts = (
            db.session.query(QuestionPaper.status, func.count(QuestionPaper.id))
            .filter(QuestionPaper.id.in_(paper_ids_for_status))
            .group_by(QuestionPaper.status)
            .all()
        )
    stats = {status: count for status, count in status_counts}

    # Total Questions
    bank_ids = [b.id for b in banks_query.with_entities(QuestionBank.id).all()]
    total_bank_questions = QuestionBankItem.query.filter(QuestionBankItem.question_bank_id.in_(bank_ids)).count() if bank_ids else 0

    paper_ids = [p.id for p in papers_query.with_entities(QuestionPaper.id).all()]
    total_paper_questions = QuestionPaperItem.query.filter(QuestionPaperItem.question_paper_id.in_(paper_ids)).count() if paper_ids else 0

    # 6. Fetch Active Papers (Filtered)
    # ✅ FIX: Use explicit QuestionPaper.status instead of filter_by to avoid ambiguity
    active_papers = (
        papers_query.filter(QuestionPaper.status == "ACTIVE") 
        .order_by(QuestionPaper.last_modified_at.desc())
        .limit(5)
        .all()
    )

    # 7. Fetch Filter Options for Dropdowns
    allowed_schools = session.get("school_access_ids", [])
    schools = [s for s in get_all_schools() if s.id in allowed_schools]
    departments = get_departments_by_school(school_id) if school_id else []
    
    # Fetch subjects dynamically based on selection
    subjects_query = SubjectVersion.query
    if dept_id: subjects_query = subjects_query.filter_by(department_id=dept_id)
    subjects = subjects_query.all() if dept_id else []

    return render_template(
        "staff/dashboard.html",
        # Data
        total_banks=total_banks,
        total_bank_questions=total_bank_questions,
        total_papers=total_papers,
        total_paper_questions=total_paper_questions,
        stats=stats,
        active_papers=active_papers,
        # Filter Options
        schools=schools,
        departments=departments,
        subjects=subjects,
        sel_school=school_id,
        sel_dept=dept_id,
        sel_subject=subject_id
    )


@staff_bp.route("/my-subjects")
@login_required
@role_required("staff")
def my_subjects():
    """
    View Assigned Subjects with Dynamic Filters and Grid Layout.
    """
    # 1. Get Filter Parameters
    school_id = request.args.get("school_id", type=int)
    dept_id = request.args.get("department_id", type=int)
    subject_id = request.args.get("subject_version_id", type=int)
    batch = request.args.get("batch", type=int)
    semester = request.args.get("semester", type=int)

    # 2. Build Query
    query = SubjectVersion.query.join(Department)
    
    # Filter by user access (Optional: if staff are restricted to specific schools)
    allowed_school_ids = session.get("school_access_ids", [])
    if allowed_school_ids:
        query = query.filter(Department.school_id.in_(allowed_school_ids))

    if school_id: query = query.filter(Department.school_id == school_id)
    if dept_id: query = query.filter(SubjectVersion.department_id == dept_id)
    if batch: query = query.filter(SubjectVersion.batch == batch)
    if semester: query = query.filter(SubjectVersion.semester == semester)
    if subject_id: query = query.filter(SubjectVersion.id == subject_id)

    subjects = query.order_by(SubjectVersion.semester, SubjectVersion.subject_id).all()

    # 3. Fetch Dynamic Filter Options (Distinct Values from DB)
    schools = [s for s in get_all_schools() if s.id in allowed_school_ids]
    departments = get_departments_by_school(school_id) if school_id else []
    
    # Distinct Batches
    batches_data = db.session.query(SubjectVersion.batch).distinct().order_by(SubjectVersion.batch.desc()).all()
    batches = [b[0] for b in batches_data]

    # Distinct Semesters
    semesters_data = db.session.query(SubjectVersion.semester).distinct().order_by(SubjectVersion.semester).all()
    semesters = [s[0] for s in semesters_data]

    # Subjects List for Dropdown
    all_subjects = SubjectVersion.query.filter(SubjectVersion.department_id == dept_id).all() if dept_id else []

    return render_template(
        "staff/subjects.html",
        subjects=subjects,
        schools=schools,
        departments=departments,
        batches=batches,
        semesters=semesters,
        all_subjects=all_subjects,
        # Selected Values
        sel_school=school_id,
        sel_dept=dept_id,
        sel_batch=batch,
        sel_sem=semester,
        sel_subject=subject_id
    )


# =========================================================
# PHASE 5A — WEIGHTAGE + PATTERN PREVIEW
# =========================================================
@staff_bp.route("/view-weightage", methods=["GET"])
@login_required
@role_required("staff")
def view_weightage():
    allowed_school_ids = session.get('school_access_ids', [])
    
    school_id = request.args.get("school_id", type=int)
    dept_id = request.args.get("department_id", type=int)
    semester = request.args.get("semester", type=int)
    batch = request.args.get("batch", type=int)
    subject_version_id = request.args.get("subject_version_id", type=int)

    # ✅ Initialize variables at the top to avoid UnboundLocalError
    selected_subject_version = None
    weightages = []

    # Security: Restrict to assigned schools
    if school_id and school_id not in allowed_school_ids:
        school_id = allowed_school_ids[0] if allowed_school_ids else None

    # Fetch dynamic semesters
    available_semesters = []
    if dept_id:
        sem_query = db.session.query(distinct(SubjectVersion.semester))\
            .filter(SubjectVersion.department_id == dept_id)\
            .order_by(SubjectVersion.semester).all()
        available_semesters = [s[0] for s in sem_query]

    # Handle Subject and Weightage retrieval
    if subject_version_id:
        selected_subject_version = SubjectVersion.query.get_or_404(subject_version_id)
        # Security check: Does this subject belong to staff's school?
        if selected_subject_version.department.school_id in allowed_school_ids:
            weightages = get_weightage_by_subject_version(subject_version_id)
        else:
            selected_subject_version = None # Reset if unauthorized access attempted

    # Fetch dropdown data
    subjects = get_subject_versions(school_id=school_id, department_id=dept_id, semester=semester, batch=batch)
    my_schools = [s for s in get_all_schools() if s.id in allowed_school_ids]
    current_depts = get_departments_by_school(school_id) if school_id else []

    return render_template(
        "staff/view_weightage.html",
        schools=my_schools,
        departments=current_depts,
        available_semesters=available_semesters,
        subjects=subjects,
        weightages=weightages,
        selected_school=school_id,
        selected_dept=dept_id,
        selected_semester=semester,
        selected_batch=batch,
        selected_subject_id=subject_version_id,
        subject_version=selected_subject_version  # ✅ Now safely defined
    )


# =========================================================
# PATTERNS (READ-ONLY)
# =========================================================

@staff_bp.route("/patterns", methods=["GET"])
@login_required
@role_required("staff")
def view_patterns():
    from app.models.pattern import Pattern
    patterns = Pattern.query.all()
    
    pattern_views = []
    for p in patterns:
        sections = []
        struct = p.structure_json or {}
        sec_data = struct.get("sections", {})
        
        # We sort alphabetically (A, B, C)
        for s_name in sorted(sec_data.keys()):
            cfg = sec_data[s_name]
            
            # Use the exact keys from your admin function: count, marks, total
            count = cfg.get('count', 0)
            marks = cfg.get('marks', 0)
            total = cfg.get('total', count) # Fallback to count if total isn't specified
            
            sections.append({
                "section": f"Sec {s_name}",
                "expression": f"{count} × {marks} = {count * marks}",
                "details": f"{marks} marks, answer {count} out of {total}",
                "note": "Answer All Questions" if count == total else f"Answer Any {count} Questions"
            })
            
        pattern_views.append({
            "name": p.name,
            "total_marks": p.total_marks,
            "sections": sections
        })

    return render_template("staff/view_patterns.html", pattern_views=pattern_views)

# entry point for paper generation flow

@staff_bp.route("/generate-paper")
@login_required
@role_required("staff")
def generate_paper_entry():
    """
    Phase 5B:
    Entry UI for generating TEMP question papers.
    """
    return render_template("staff/generate_paper.html")

# =========================================================
# AJAX — FILTERS
# =========================================================

@staff_bp.route("/ajax/departments")
def ajax_departments():
    from app.models.department import Department
    return jsonify([
        {"id": d.id, "name": d.name}
        for d in Department.query.all()
    ])

@staff_bp.route("/ajax/batches")
def ajax_batches():
    department_id = request.args.get("department_id", type=int)
    rows = (
        db.session.query(distinct(SubjectVersion.batch))
        .filter_by(department_id=department_id)
        .all()
    )
    return jsonify([r[0] for r in rows])

@staff_bp.route("/ajax/semesters")
def ajax_semesters():
    department_id = request.args.get("department_id", type=int)
    batch = request.args.get("batch", type=int)

    rows = (
        db.session.query(distinct(SubjectVersion.semester))
        .filter_by(department_id=department_id, batch=batch)
        .all()
    )
    return jsonify([r[0] for r in rows])

@staff_bp.route("/ajax/subjects")
def ajax_subjects():
    department_id = request.args.get("department_id", type=int)
    batch = request.args.get("batch", type=int)
    semester = request.args.get("semester", type=int)

    versions = SubjectVersion.query.filter_by(
        department_id=department_id,
        batch=batch,
        semester=semester,
        is_active=True
    ).all()

    return jsonify([
        {
            "id": v.id,
            "name": v.subject.name,
            "code": v.subject.code
        }
        for v in versions
    ])


@staff_bp.route("/ajax/check-default-bank")
@login_required
@role_required("staff")
def check_default_bank():
    subject_version_id = request.args.get("subject_version_id", type=int)
    if not subject_version_id:
        return jsonify({"exists": False})

    from app.models.question_bank import QuestionBank
    
    # Check for an active default bank
    bank = QuestionBank.query.filter_by(
        subject_version_id=subject_version_id,
        is_default=True,
        status="ACTIVE"
    ).first()

    return jsonify({
        "exists": bool(bank),
        "bank_id": bank.id if bank else None
    })
    
# =========================================================
# AJAX — WEIGHTAGE + PATTERN PREVIEW (Generate Flow ONLY)
# =========================================================

@staff_bp.route("/ajax/subject-weightage-preview")
@login_required
@role_required("staff")
def subject_weightage_preview():
    subject_version_id = request.args.get("subject_version_id", type=int)
    if not subject_version_id:
        return jsonify({"error": "subject_version_id required"}), 400

    sv = SubjectVersion.query.get_or_404(subject_version_id)

    weightages = get_weightage_by_subject_version(subject_version_id)
    if not weightages:
        return jsonify({"error": "Weightage not defined for this subject"}), 400

    pattern = sv.pattern
    if not pattern:
        return jsonify({"error": "Pattern not assigned"}), 400

    # Build response
    sections = pattern.structure_json.get("sections", {})

    return jsonify({
        "subject_version_id": sv.id,
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
    })


@staff_bp.route("/ajax/validate-question-bank", methods=["POST"])
@login_required
@role_required("staff")
def validate_question_bank():
    file = request.files.get("file")
    subject_version_id = request.form.get("subject_version_id", type=int)

    if not subject_version_id:
        return jsonify({
            "valid": False,
            "errors": [{"message": "Subject not selected"}]
        }), 400

    if not file:
        return jsonify({
            "valid": False,
            "errors": [{"message": "Excel file not uploaded"}]
        }), 400

    result = validate_question_bank_excel(
        file_bytes=file.read(),
        subject_version_id=subject_version_id
    )

    return jsonify(result)

@staff_bp.route("/papers/<int:paper_id>/review")
@login_required
@role_required("staff")
def review_generated_paper(paper_id):
    from app.models.question_paper import QuestionPaper

    paper = QuestionPaper.query.get_or_404(paper_id)

    # ✅ FIX: Allow BOTH Generated and Scrutiny statuses
    if paper.status not in ["GENERATED", "UNDER_SCRUTINY"]:
        flash("This paper cannot be reviewed at this stage.", "danger")
        return redirect(url_for("staff.staff_home"))

    return render_template(
        "staff/paper_review.html",
        paper=paper,
        items=paper.items
    )

@staff_bp.route("/ajax/swap-candidates")
@login_required
@role_required("staff")
def get_swap_candidates():
    item_id = request.args.get("paper_item_id", type=int)

    item = QuestionPaperItem.query.get_or_404(item_id)

    candidates = (
        QuestionBankItem.query
        .filter_by(
            question_bank_id=item.question_paper.source_question_bank_id,
            unit=item.unit,
            marks=item.marks
        )
        .all()
    )

    return jsonify([
        {"id": q.id, "text": q.question.question_text}
        for q in candidates
    ])

# =========================================================
# PHASE 5B.1 — LIST QUESTION PAPERS
# =========================================================

@staff_bp.route("/papers")
@login_required
@role_required("staff")
def list_question_papers():
    subject_version_id = request.args.get("subject_version_id", type=int)
    if not subject_version_id:
        return redirect(url_for("staff.staff_home"))

    subject_version = SubjectVersion.query.get_or_404(subject_version_id)
    papers = (
        QuestionPaper.query
        .filter_by(subject_version_id=subject_version_id)
        .order_by(QuestionPaper.created_at.desc())
        .all()
    )

    return render_template(
        "staff/paper_list.html",
        subject_version=subject_version,
        papers=papers
    )

# =========================================================
# PHASE 5B.2 — GENERATE QUESTION PAPER
# =========================================================


@staff_bp.route("/papers/generate", methods=["POST"])
@login_required
@role_required("staff")
def generate_question_paper():
    subject_version_id = request.form.get("subject_version_id", type=int)
    source_mode = request.form.get("source_mode") # 'default' or 'upload'
    
    bank_id = None

    # =====================================================
    # SCENARIO A: USE DEFAULT QUESTION BANK
    # =====================================================
    if source_mode == "default":
        from app.models.question_bank import QuestionBank
        
        # 1. Find the default bank
        bank = QuestionBank.query.filter_by(
            subject_version_id=subject_version_id,
            is_default=True,
            status="ACTIVE"
        ).first()

        if not bank:
            return jsonify({
                "valid": False,
                "errors": [{"message": "No Default Question Bank found for this subject. Please choose 'Upload New'."}]
            }), 400
            
        bank_id = bank.id

    # =====================================================
    # SCENARIO B: UPLOAD NEW QUESTION BANK
    # =====================================================
    else:
        # 1. Check File
        file = request.files.get("file")
        if not file:
            return jsonify({
                "valid": False,
                "errors": [{"message": "Question Bank Excel not uploaded"}]
            }), 400

        file_bytes = file.read() 

        # 2. Validate Excel (Existing Logic)
        from app.services.question_bank_excel_validation_service import validate_question_bank_excel
        validation = validate_question_bank_excel(
            file_bytes=file_bytes,
            subject_version_id=subject_version_id
        )

        if not validation["valid"]:
            return jsonify(validation), 400

        # 3. Ingest Question Bank (Existing Logic)
        from app.services.question_bank_ingestion_service import ingest_question_bank_excel
        try:
            bank = ingest_question_bank_excel(
                file_bytes=file_bytes,
                subject_version_id=subject_version_id,
                uploaded_by=session["user_id"]
            )
            bank_id = bank.id
        except Exception as e:
            return jsonify({
                "valid": False,
                "errors": [{"message": f"Ingestion failed: {str(e)}"}]
            }), 500

    # =====================================================
    # COMMON FLOW: GENERATE PAPER SKELETON & SELECT
    # =====================================================
    
    # 1. Create Skeleton
    paper = generate_question_paper_skeleton(
        subject_version_id=subject_version_id,
        created_by=session["user_id"],
        paper_code=request.form["paper_code"],
        paper_type=request.form["paper_type"],
        question_bank_id=bank_id 
    )

    # 2. Auto-Select Questions
    try:
        auto_select_questions_for_paper(paper.id)
    except Exception as e:
        return jsonify({
            "valid": False,
            "errors": [{"message": f"Auto-selection failed: {str(e)}"}]
        }), 400

    return redirect(url_for("staff.review_generated_paper", paper_id=paper.id))
@staff_bp.route("/papers/<int:paper_id>/download-official")
@login_required
@role_required("staff")
def download_official_question_paper(paper_id):
    """
    Phase 8: Generate OFFICIAL Table-Based DOCX
    """
    paper = QuestionPaper.query.get_or_404(paper_id)

    # 1. Generate the OFFICIAL DOCX file
    docx_buffer = generate_official_docx(paper)

    # 2. Update Status (Trigger Scrutiny if not already)
    if paper.status == "GENERATED":
        paper.status = "UNDER_SCRUTINY"
        db.session.commit()

    # 3. Send file to user
    return send_file(
        docx_buffer,
        as_attachment=True,
        download_name=f"{paper.paper_code}_OFFICIAL.docx",
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
# =========================================================
# PHASE 5D & 6 — REVIEW, SWAP & EDIT
# =========================================================

@staff_bp.route("/ajax/swap-question", methods=["POST"])
@login_required
@role_required("staff")
def ajax_swap_question():
    """
    Phase 5D: Swaps a question and returns the new details for AJAX update.
    """
    data = request.get_json()
    paper_item_id = data.get("paper_item_id")
    new_bank_item_id = data.get("new_bank_item_id")

    if not paper_item_id or not new_bank_item_id:
        return jsonify({"error": "Missing IDs"}), 400

    
    
    try:
        # 1. Perform the swap
        swap_question_with_bank(
            paper_item_id=paper_item_id,
            new_bank_item_id=int(new_bank_item_id)
        )

        # 2. Fetch the updated item to send back to frontend
        updated_item = QuestionPaperItem.query.get(paper_item_id)

        return jsonify({
            "success": True,
            "new_text": updated_item.display_text,
            "new_k_level": updated_item.k_level if updated_item.k_level else "-"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@staff_bp.route("/papers/<int:paper_id>/download")
@login_required
@role_required("staff")
def download_question_paper(paper_id):
    """
    Phase 8: Generate DOCX
    Phase 6 Trigger: Updates status to UNDER_SCRUTINY
    """
    paper = QuestionPaper.query.get_or_404(paper_id)

    # 1. Generate the DOCX file
    docx_buffer = generate_question_paper_docx(paper)

    # 2. Update Status (Phase 6 Trigger)
    if paper.status == "GENERATED":
        paper.status = "UNDER_SCRUTINY"
        db.session.commit()

    # 3. Send file to user
    
    return send_file(
        docx_buffer,
        as_attachment=True,
        download_name=f"{paper.paper_code}_DRAFT.docx",
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

# =========================================================
# PHASE 7 — ACTIVATION
# =========================================================

@staff_bp.route("/papers/<int:paper_id>/activate", methods=["POST"])
@login_required
@role_required("staff")
def activate_paper_route(paper_id):
    """
    Phase 7: Finalize and Activate the paper.
    """
    
    try:
        activate_question_paper(
            paper_id=paper_id,
            activated_by=session["user_id"]
        )
        flash("Paper activated successfully! Previous active papers are now archived.", "success")
    except Exception as e:
        flash(f"Error activating paper: {str(e)}", "danger")

    return redirect(url_for("staff.review_generated_paper", paper_id=paper_id))


# app/routes/staff_routes.py (Add to the bottom)

@staff_bp.route("/ajax/edit-question", methods=["POST"])
@login_required
@role_required("staff")
def ajax_edit_question():
    """Phase 6: Manually override question text during scrutiny"""
    data = request.get_json()
    paper_item_id = data.get("paper_item_id")
    new_text = data.get("new_text")

    if not paper_item_id or not new_text:
        return jsonify({"error": "Missing data"}), 400

    
    try:
        apply_manual_edit(paper_item_id=paper_item_id, new_text=new_text)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@staff_bp.route("/ajax/mark-duplicate", methods=["POST"])
@login_required
@role_required("staff")
def ajax_mark_duplicate():
    """Phase 6: Flag a question as duplicate"""
    data = request.get_json()
    paper_item_id = data.get("paper_item_id")
    is_duplicate = data.get("is_duplicate", True)

    if not paper_item_id:
        return jsonify({"error": "Missing ID"}), 400

    
    try:
        mark_duplicate(paper_item_id=paper_item_id, is_duplicate=is_duplicate)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # =========================================================
# PHASE 6 — SCRUTINY DASHBOARD
# =========================================================

@staff_bp.route("/scrutiny")
@login_required
@role_required("staff")
def scrutiny_list():
    """
    Shows papers currently UNDER_SCRUTINY.
    Fix: Only shows papers created by the logged-in user.
    """
    user_id = session["user_id"]

    # Base Query
    query = (
        QuestionPaper.query
        .join(SubjectVersion)
        .join(SubjectVersion.department)
        .filter(QuestionPaper.status == "UNDER_SCRUTINY")
    )

    # 🔒 SECURITY FIX: Enforce User Isolation
    # Only show papers created by THIS user.
    query = query.filter(QuestionPaper.created_by == user_id)

    # Apply Optional Filters (School/Dept)
    school_id = request.args.get("school_id", type=int)
    dept_id = request.args.get("department_id", type=int)

    if school_id:
        query = query.filter(Department.school_id == school_id)
    if dept_id:
        query = query.filter(SubjectVersion.department_id == dept_id)

    papers = query.order_by(QuestionPaper.last_modified_at.desc()).all()

    # Fetch filters for dropdowns
    from app.services.school_service import get_all_schools
    from app.services.department_service import get_departments_by_school
    
    allowed_schools = session.get("school_access_ids", [])
    schools = [s for s in get_all_schools() if s.id in allowed_schools]
    departments = get_departments_by_school(school_id) if school_id else []

    return render_template(
        "staff/scrutiny_list.html",
        papers=papers,
        schools=schools,
        departments=departments,
        sel_school=school_id,
        sel_dept=dept_id
    )

@staff_bp.route("/question-bank/items")
@login_required
@role_required("staff")
def view_question_items():
    """
    Phase 9: Master Repository View
    Shows UNIQUE questions from QuestionMaster with their default metadata.
    Fixes 'InvalidRequestError' by joining through SubjectVersion.
    """
    from app.models.question_master import QuestionMaster
    from app.models.subject import Subject
    from app.models.subject_version import SubjectVersion
    from app.models.department import Department
    from app.models.school import School
    from app.services.school_service import get_all_schools
    from app.services.department_service import get_departments_by_school

    user_id = session["user_id"]
    
    # 1. Get Filters
    school_id = request.args.get("school_id", type=int)
    dept_id = request.args.get("department_id", type=int)
    subject_version_id = request.args.get("subject_version_id", type=int)

    f_unit = request.args.get("unit", type=int)
    f_section = request.args.get("section")
    f_marks = request.args.get("marks", type=int)
    f_klevel = request.args.get("k_level")

    # 2. Build Query
    # Start with QuestionMaster
    query = db.session.query(QuestionMaster)

    # JOIN CHAIN: Master -> Subject -> Version -> Dept -> School
    query = query.join(Subject, QuestionMaster.subject_id == Subject.id)
    query = query.join(SubjectVersion, Subject.id == SubjectVersion.subject_id)
    query = query.join(Department, SubjectVersion.department_id == Department.id)
    query = query.join(School, Department.school_id == School.id)

    # 3. Apply Context Filters
    if subject_version_id:
        # If a specific version is selected, filter by the generic subject ID
        sv = SubjectVersion.query.get(subject_version_id)
        if sv:
            query = query.filter(QuestionMaster.subject_id == sv.subject_id)
    elif dept_id:
        query = query.filter(SubjectVersion.department_id == dept_id)
    elif school_id:
        query = query.filter(Department.school_id == school_id)

    # 4. Apply Granular Filters (Using the new Default columns on QuestionMaster)
    if f_unit:
        query = query.filter(QuestionMaster.default_unit == f_unit)
    if f_section:
        query = query.filter(QuestionMaster.default_section == f_section)
    if f_marks:
        query = query.filter(QuestionMaster.default_marks == f_marks)
    if f_klevel:
        query = query.filter(QuestionMaster.k_level == f_klevel)

    # 5. Distinct & Execute
    # We MUST use distinct() because joining SubjectVersion (1-to-Many) will create duplicates
    # if a Subject has multiple versions (e.g. Batch 2024, Batch 2025).
    items = query.distinct(QuestionMaster.id).order_by(QuestionMaster.id.desc()).all()
    
    total_count = len(items)

    # 6. Dropdowns
    allowed_schools = session.get("school_access_ids", [])
    schools = [s for s in get_all_schools() if s.id in allowed_schools]
    departments = get_departments_by_school(school_id) if school_id else []
    
    subjects_query = SubjectVersion.query
    if dept_id: subjects_query = subjects_query.filter_by(department_id=dept_id)
    subjects = subjects_query.all() if dept_id else []

    return render_template(
        "staff/question_bank_items.html",
        items=items,
        total_count=total_count,
        schools=schools,
        departments=departments,
        subjects=subjects,
        # Selected Values
        sel_school=school_id,
        sel_dept=dept_id,
        sel_subject=subject_version_id,
        sel_unit=f_unit,
        sel_section=f_section,
        sel_marks=f_marks,
        sel_klevel=f_klevel
    )


# app/routes/staff_routes.py

@staff_bp.route("/all-papers")
@login_required
@role_required("staff")
def all_generated_papers():
    """
    Master Archive: View ALL generated papers (Draft, Active, Archived, Scrutiny).
    Features: Grid Layout, Comprehensive Filters, Dual Downloads.
    """
    from app.models.question_paper import QuestionPaper
    from app.models.subject_version import SubjectVersion
    from app.models.department import Department
    from app.models.user import User
    from app.services.school_service import get_all_schools
    from app.services.department_service import get_departments_by_school

    user_id = session["user_id"]

    # 1. Get Filters
    school_id = request.args.get("school_id", type=int)
    dept_id = request.args.get("department_id", type=int)
    subject_id = request.args.get("subject_version_id", type=int)
    batch = request.args.get("batch", type=int)

    f_status = request.args.get("status")
    f_type = request.args.get("paper_type")

    # 2. Build Query
    # Join User to get the Creator's Name
    query = (
        db.session.query(QuestionPaper)
        .join(SubjectVersion)
        .join(SubjectVersion.department)
        .join(User, QuestionPaper.created_by == User.id)
    )

    # 🔒 ISOLATION: Show only papers created by this logged-in staff
    query = query.filter(QuestionPaper.created_by == user_id)

    # 3. Apply Context Filters
    if school_id:
        query = query.filter(Department.school_id == school_id)
    if dept_id:
        query = query.filter(SubjectVersion.department_id == dept_id)
    if subject_id:
        query = query.filter(QuestionPaper.subject_version_id == subject_id)
    if batch:
        query = query.filter(SubjectVersion.batch == batch)

    # 4. Apply Grid Filters
    if f_status:
        query = query.filter(QuestionPaper.status == f_status)
    if f_type:
        query = query.filter(QuestionPaper.paper_type == f_type)

    # 5. Execute (Sort by newest first)
    papers = query.order_by(QuestionPaper.last_modified_at.desc()).all()
    total_count = len(papers)

    # 6. Fetch Dropdown Options
    allowed_schools = session.get("school_access_ids", [])
    schools = [s for s in get_all_schools() if s.id in allowed_schools]
    departments = get_departments_by_school(school_id) if school_id else []
    
    subjects_query = SubjectVersion.query
    if dept_id: subjects_query = subjects_query.filter_by(department_id=dept_id)
    subjects = subjects_query.all() if dept_id else []

    batches = db.session.query(SubjectVersion.batch).distinct().order_by(SubjectVersion.batch.desc()).all()
    batches = [b[0] for b in batches]

    return render_template(
        "staff/all_papers.html",
        papers=papers,
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
        sel_type=f_type
    )