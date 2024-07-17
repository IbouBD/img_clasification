from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, FileField, IntegerField, validators, BooleanField, Form
from wtforms.validators import DataRequired, Email, EqualTo

class UploadForm(FlaskForm):
    files = FileField('Upload Images', validators=[DataRequired()])
    nb_cluster = IntegerField('Number of Clusters', validators=[DataRequired()])
    submit = SubmitField('Submit')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')