from app.extensions import db
from app.models.user import User

def authenticate_user(username: str, password: str):
    """
    Authenticate user using username & password.
    Returns User object if valid, else None.
    """
    if not username or not password:
        return None

    user = User.query.filter_by(username=username).first()
    if not user:
        return None

    if not user.check_password(password):
        return None

    return user
