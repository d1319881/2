import os
from app import create_app
from app.models import db

app = create_app()
with app.app_context():
    # Make sure instance folder exists
    instance_dir = os.path.join(app.root_path, '..', 'instance')
    if not os.path.exists(instance_dir):
        os.makedirs(instance_dir)
        print(f"Created instance directory at: {instance_dir}")

    db.create_all()
    print("Database tables created successfully in SQLite!")
