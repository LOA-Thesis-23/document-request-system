from flask import redirect, render_template, url_for
from app import create_app

app = create_app()


@app.route('/')
def index():
    return render_template('modals/container.html')

if __name__ == '__main__':
    app.run(debug=True)