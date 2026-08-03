from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

@app.route('/')
def home():
    try:
        db.session.execute(db.text('SELECT 1'))
        return 'Flask is running AND successfully connected to the database!'
    except Exception as e:
        return f'Flask is running, but database connection FAILED: {e}'

if __name__ == '__main__':
    app.run(debug=True)