import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'default-dev-key-change-me')
    
    # Calculate paths
    CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
    PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
    
    # Prioritize DATABASE_URL from environment variables
    DATABASE_URL = os.environ.get('DATABASE_URL')
    
    if DATABASE_URL:
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        # Fallback to database.db in the project root directory
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(PROJECT_ROOT, 'database.db')}"
        
    SQLALCHEMY_TRACK_MODIFICATIONS = False
