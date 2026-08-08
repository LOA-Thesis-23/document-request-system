from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.decorators import admin_required


admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/home')
@login_required
@admin_required
def home():
    return render_template('modals/adminside.html')