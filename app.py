from flask import redirect, url_for
from app import create_app

app = create_app()


@app.route('/')
def index():
    return redirect(url_for('auth.login'))


if __name__ == '__main__':
    app.run(debug=True)