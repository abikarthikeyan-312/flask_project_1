from app.extensions import db
from app.models.user import User
from app.models.school import School
from werkzeug.security import generate_password_hash

def create_user(username, password, role, school_ids=None):
    # Check if user already exists
    if User.query.filter_by(username=username).first():
        raise ValueError("Username already exists")

    # 1. Create the instance with columns defined in your model
    new_user = User(
        username=username,
        role=role
    )
    
    # 2. Use your model's method to hash the password
    new_user.set_password(password)
    
    # 3. Handle School Assignments for Staff
    if school_ids and role == 'staff':
        # Convert string IDs from form to integers and fetch objects
        selected_schools = School.query.filter(School.id.in_([int(sid) for sid in school_ids])).all()
        new_user.schools = selected_schools

    db.session.add(new_user)
    db.session.commit()
    return new_user

def get_all_users():
    return User.query.all()


def update_user_schools(user_id, school_ids):
    """
    Updates a user's school assignments by synchronizing the relationship.
    """
    user = User.query.get_or_404(user_id)
    
    # Convert string IDs from form to actual School objects
    if school_ids:
        schools = School.query.filter(School.id.in_([int(sid) for sid in school_ids])).all()
        user.schools = schools
    else:
        user.schools = []
        
    db.session.commit()
    return True

def reset_user_school_access(user_id):
    user = User.query.get_or_404(user_id)
    # Clear the relationship list
    user.schools = []
    db.session.commit()
    return True

def reset_user_password(user_id, new_password):
    user = User.query.get_or_404(user_id)
    user.set_password(new_password)
    # By updating the password, the next time the user tries to authenticate
    # or if we implement a 'password_hash' check in g.user, they'll be out.
    db.session.commit()

# app/services/user_service.py

def delete_user(user_id, current_admin_id):
    """
    Deletes a user while preventing self-deletion.
    """
    # Safety check to prevent deleting the account you are currently using
    if int(user_id) == current_admin_id:
        raise ValueError("You cannot delete your own account.")
        
    user = User.query.get_or_404(user_id)
    
    # Optional: Prevent deleting the last admin
    if user.role == 'admin' and User.query.filter_by(role='admin').count() <= 1:
        raise ValueError("Cannot delete the last administrator in the system.")
    
    db.session.delete(user)
    db.session.commit()
    return True