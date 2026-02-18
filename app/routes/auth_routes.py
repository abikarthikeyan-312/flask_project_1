from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g
from app.services.auth_service import authenticate_user
from app.models.user import User  # Import User model for the DB check

auth_bp = Blueprint("auth", __name__)

@auth_bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        # Fetch the user from the DB to ensure they still exist
        user = User.query.get(user_id)
        
        # ✅ SECURITY: If user was deleted/disabled, invalidate session immediately
        if user is None:
            session.clear()
            g.user = None
            # Only redirect if they aren't already going to the login page
            if request.endpoint != 'auth.login':
                return redirect(url_for('auth.login'))
        else:
            g.user = user

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = authenticate_user(username, password)

        if not user:
            flash("Invalid username or password", "danger")
            return redirect(url_for("auth.login"))

        # --- SESSION SETUP ---
        session.clear()
        session["user_id"] = user.id
        session["username"] = user.username
        session["role"] = user.role
        # Pre-load school IDs for quick access checks in templates/routes
        session["school_access_ids"] = [s.id for s in user.schools]

        if user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        else:
            return redirect(url_for("staff.staff_home"))

    return render_template("login.html")

@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for("auth.login"))