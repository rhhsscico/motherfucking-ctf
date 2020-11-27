#
# Copyright (c) 2019 Andrea Fioraldi <andreafioraldi@gmail.com>
# This code is under the BSD 2-clause license
#
# Code inspired by https://github.com/abdesslem/CTF (Copyright (c) 2015 Amri Abdesslem)
#

import datetime
import functools
import os
import time

from flask import (Flask, abort, flash, redirect, render_template, request,
                   session, url_for)
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from flask_security import Security
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy import desc
from werkzeug.security import check_password_hash, generate_password_hash
from wtforms import PasswordField, RadioField, StringField, SubmitField
from wtforms.validators import Email, EqualTo, Length, Required

import config


################################
#########   GLOBALS   ##########
################################

MAX_SCORE = 100
MIN_SCORE = 20
RATE_SCORE = 2

app = Flask(__name__)

if app.config["ENV"] == 'production':
    app.config.from_object("config.ProductionConfig")
else:
    app.config.from_object("config.DevelopmentConfig")


#app.config["PREFERRED_URL_SCHEME"] = 'https' #decomment for HTTPS
CSRFProtect(app)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)

################################
##########   MODELS   ##########
################################

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    __table_args__ = {'extend_existing': True} 
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    email = db.Column(db.String(80))
    password_hash = db.Column(db.String(120))
    solved = db.Column(db.String(400))
    lastSubmit = db.Column(db.DateTime)

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return '<User %r>' % self.username

class Challenges(db.Model):
    __tablename__ = 'challenges'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True)
    category = db.Column(db.String(60))
    info = db.Column(db.String(1000))
    score = db.Column(db.String(20))
    flag = db.Column(db.String(80))
    solves = db.Column(db.String(20), default='0')

    def __repr__(self):
        return '<Challenges %r>' % self.name


def user_score(user):
    solved = user.solved.split(",")
    score = 0
    for c in solved:
        if len(c) == 0: continue
        q = Challenges.query.get(int(c))
        if q is None: continue
        score += int(q.score)
    return score

@app.context_processor
def utility_processor():
    return dict(user_score=user_score)

################################
###########  FORMS   ###########
################################

class LoginForm(FlaskForm):
    login = StringField('Username', validators=[Required(), Length(1, 64)])
    password = PasswordField('Password', validators=[Required()])
    submit = SubmitField('Login')

class ChallengeForm(FlaskForm):
    flag = StringField('The Flag', validators=[Required(), Length(1, 64)])
    submit = SubmitField('Send')

class RegistrationForm(FlaskForm):
    login = StringField('Username', validators=[Required()])
    email = StringField('Email', validators=[Required(), Email()])
    password = PasswordField('Password', validators=[Required()])
    password_again = PasswordField('Password again',
                                   validators=[Required(), EqualTo('password')])
    submit = SubmitField('Register')

class NewChallengeForm(FlaskForm):
    name = StringField('Name', validators=[Required()])
    category = StringField('Category', validators=[Required()])
    info = StringField('Info', validators=[Required()])
    score = StringField('Score', validators=[Required()])
    flag = StringField('Flag', validators=[Required()])
    submit = SubmitField('Submit')


################################
##########  ROUTES   ###########
################################

@login_manager.user_loader
def load_user(user_id):
    """User loader callback for Flask-Login."""
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/challenges')
def challenges():
    challenges = Challenges.query.all()
    #query = db.session.query(Challenges.category.distinct().label("category"))
    #categories = [row.category for row in query.all()]
    return render_template('challenges.html', challenges=challenges)#, categories=categories)

@app.route('/scoreboard')
@login_required
def scoreboard():
    users = User.query.filter(User.username!='admin').all()
    def custom_order(x, y):
        rx = user_score(x)
        ry = user_score(y)
        if rx != ry: return rx - ry
        tx = time.mktime(x.lastSubmit.timetuple()) if x.lastSubmit else 0
        ty = time.mktime(y.lastSubmit.timetuple()) if y.lastSubmit else 0
        return int(ty - tx) 
    l = sorted(list(users), key = functools.cmp_to_key(custom_order), reverse=True)
    ranking = -1 if current_user.username == "admin" else int(l.index(current_user)) + 1
    return render_template('scoreboard.html', users=l, ranking=ranking)

@app.route('/challenge/<challenge_name>',methods=["GET","POST"])
@login_required
def challenge(challenge_name):
    form = ChallengeForm(request.form)
    challenge = Challenges.query.filter_by(name=challenge_name).first()
    
    if form.validate_on_submit() and challenge.flag == form.flag.data:
        user = User.query.filter_by(username=current_user.username).first()
        if str(challenge.id) in user.solved.split(","):
            return "Ehi! You can't submit two times the same flag!"
        user.solved = user.solved + ',' + str(challenge.id)
        user.lastSubmit = datetime.datetime.utcnow()
        challenge.solves = str(int(challenge.solves) +1)
        ns = int(MAX_SCORE) - int(challenge.solves) // RATE_SCORE
        challenge.score = str(max(MIN_SCORE, ns))
        db.session.commit()
        return "Well done, the flag is correct."
    elif form.validate_on_submit() and challenge.flag != form.flag.data :
        return 'Wrong Flag!'
    
    return render_template('challenge.html',form=form, challenge=challenge )

@app.route('/new_challenge', methods=['GET', 'POST'])
def new_challenge():
    challenge = Challenges()
    form = NewChallengeForm(obj=challenge)
    if request.method == 'POST':
        try:
            print ("hello")
            if form.validate_on_submit():
                form.populate_obj(challenge)
                db.session.add(challenge)
                db.session.commit()
                return redirect('/challenges')
        except Exception as e:
            db.session.rollback()
            flash('There is already a challenge with that name!')

    return render_template('new_challenge.html', title='Submit Challenge', form=form)


@app.route('/register', methods=['GET','POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegistrationForm(request.form)
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.login.data).first()
        if user is not None:
            return 'Username already exists.'
        user = User(username=form.login.data,
                       email=form.email.data,
                       password=form.password.data,
                       solved='')
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('index'))
    
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm(request.form)
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.login.data).first()
        if user is None or not user.verify_password(form.password.data):
            return 'Invalid username or password'
         
        login_user(user)
        return redirect(url_for('index'))
    
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)




