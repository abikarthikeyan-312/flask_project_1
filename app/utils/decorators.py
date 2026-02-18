from functools import wraps
from flask import session, redirect, url_for, abort

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "role" not in session:
                return redirect(url_for("auth.login"))

            if session.get("role") not in roles:
                abort(403)

            return view(*args, **kwargs)
        return wrapped
    return decorator
