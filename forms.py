from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, FloatField
from wtforms.validators import InputRequired, Length, EqualTo, Email, Optional

class RectangleForm(FlaskForm):
    length = FloatField('Length', validators=[InputRequired()])
    width = FloatField('Width', validators=[InputRequired()])
    area = SubmitField('Calculate Area')
    perimeter = SubmitField('Calculate Perimeter')

class SignupForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=3, max=50)])
    email = StringField('Email', validators=[Optional(), Email()])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[
        InputRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    # Deleted the admin_code field from here
    submit = SubmitField('Sign Up')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[InputRequired(), Email()])
    password = PasswordField('Password', validators=[InputRequired()])
    submit = SubmitField('Log In')

class UpgradeToAdminForm(FlaskForm):
    admin_code = StringField('Admin Code', validators=[InputRequired()])
    submit = SubmitField('Upgrade to Admin')

class WeatherReport(FlaskForm):
    city = StringField('City', validators=[InputRequired(), Length(min=2, max=100)])
    submit = SubmitField('Get Weather Report')