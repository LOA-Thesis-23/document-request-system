from app import create_app, db
from app.models import DocumentType

app = create_app()

with app.app_context():
    types = [
        DocumentType(name='Transcript of Records (TOR)', fee=150.00, description='Official academic record.'),
        DocumentType(name='Certificate of Registration (COR)', fee=50.00, description='Proof of current enrollment.'),
        DocumentType(name='Diploma', fee=500.00, description='Original or certified true copy.'),
        DocumentType(name='Certification', fee=100.00, description='General-purpose certification document.'),
    ]
    db.session.add_all(types)
    db.session.commit()
    print('Seeded document types.')