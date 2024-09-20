from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(40), unique=True, nullable=False)
    passhash = db.Column(db.String(512), nullable=False)
    name = db.Column(db.String(40), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    role = db.Column(db.String(20), nullable=False)
    niche = db.Column(db.String(20))
    socialnet = db.Column(db.String(20))
    flag = db.Column(db.Boolean, default=False)

    profile = db.relationship('Profile', back_populates='user', uselist=False)
    campaigns = db.relationship('Campaign', back_populates='sponsor')
    ad_requests_sent = db.relationship('AdRequest', foreign_keys='AdRequest.sender_id', back_populates='sender')
    ad_requests_received = db.relationship('AdRequest', foreign_keys='AdRequest.receiver_id', back_populates='receiver')
    ratings_given = db.relationship('Rating', foreign_keys='Rating.rater_id', back_populates='rater')
    ratings_received = db.relationship('Rating', foreign_keys='Rating.ratee_id', back_populates='ratee')

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.passhash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.passhash, password)

class Profile(db.Model):
    __tablename__ = 'profile'
    id = db.Column(db.Integer, primary_key=True)
    bio = db.Column(db.Text)
    reach = db.Column(db.Integer)
    rating = db.Column(db.Float)
    photo_path = db.Column(db.String(255))
    mobile = db.Column(db.String(20))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    user = db.relationship('User', back_populates='profile')


class Campaign(db.Model):
    __tablename__ = 'campaign'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(30))
    description = db.Column(db.Text)
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    budget = db.Column(db.Float)
    visibility = db.Column(db.String(20), default='Public')
    flag = db.Column(db.Boolean, default=False)
    goals = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    sponsor = db.relationship('User', back_populates='campaigns')
    ad_requests = db.relationship('AdRequest', back_populates='campaign')

class AdRequest(db.Model):
    __tablename__ = 'ad_request'
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'))
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    message = db.Column(db.Text)
    requirements = db.Column(db.Text)
    payment = db.Column(db.Float)
    status = db.Column(db.String(20))

    campaign = db.relationship('Campaign', back_populates='ad_requests')
    sender = db.relationship('User', foreign_keys=[sender_id], back_populates='ad_requests_sent')
    receiver = db.relationship('User', foreign_keys=[receiver_id], back_populates='ad_requests_received')

class Rating(db.Model):
    __tablename__ = 'rating'
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('ad_request.id'))
    rater_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    ratee_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    rating = db.Column(db.Float)
    review = db.Column(db.Text)
    date = db.Column(db.DateTime)

    ad_request = db.relationship('AdRequest')
    rater = db.relationship('User', foreign_keys=[rater_id], back_populates='ratings_given')
    ratee = db.relationship('User', foreign_keys=[ratee_id], back_populates='ratings_received')


import routes  # Ensure routes are imported after db initialization

with app.app_context():
    db.create_all()  # Create tables if they don't exist

    # Check if the admin user already exists
    admin = User.query.filter_by(role='admin').first()
    if not admin:
        admin = User(username='utkarsh', passhash=generate_password_hash('12345678'), name='Utkarsh', email='admin@gmail.com', role='admin')
        db.session.add(admin)
        db.session.commit()
        print('Admin user created.')

if __name__ == '__main__':
    app.run(debug=Config.FLASK_DEBUG)
