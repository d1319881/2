import os
from flask import Flask
from app.models import db

def create_app(test_config=None):
    """
    Application Factory to create and configure the Flask app.
    """
    app = Flask(__name__, instance_relative_config=True)
    
    # Load configuration
    if test_config is None:
        app.config.from_object('config.Config')
    else:
        app.config.from_mapping(test_config)

    # Ensure the instance folder exists for SQLite
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Initialize extensions
    db.init_app(app)

    @app.route('/health')
    def health():
        return {'status': 'healthy'}, 200

    return app
