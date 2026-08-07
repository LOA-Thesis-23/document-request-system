from functools import wraps
from flask import abort
from flask_login import current_user
from app.models import Staff

def staff_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not isinstance(current_user, Staff):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not isinstance(current_user, Staff) or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function