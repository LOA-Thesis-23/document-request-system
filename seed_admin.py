import os
from app import create_app, db, bcrypt
from app.models import Staff

app = create_app()

with app.app_context():
    email = os.environ.get('ADMIN_EMAIL')
    password = os.environ.get('ADMIN_PASSWORD')

    if not email or not password:
        print('Set ADMIN_EMAIL and ADMIN_PASSWORD in your .env file first.')
    else:
        existing = Staff.query.filter_by(email=email).first()
        if existing:
            print('Temp admin already exists — skipping.')
        else:
            hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
            temp_admin = Staff(
                full_name='Temporary Admin',
                email=email,
                password=hashed_pw,
                role='admin'
            )
            db.session.add(temp_admin)
            db.session.commit()
            print(f'Temp admin created: {email}')