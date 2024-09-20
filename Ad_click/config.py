from dotenv import load_dotenv
import os

load_dotenv()  # Load environment variables from .env file

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI')
    SQLALCHEMY_TRACK_MODIFICATIONS = os.getenv('SQLALCHEMY_TRACK_MODIFICATIONS') == 'True'
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'static/uploads')
    FLASK_DEBUG = os.environ.get('FLASK_DEBUG', default=False)