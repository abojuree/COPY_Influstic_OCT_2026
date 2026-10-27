from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import Email, DataRequired


class LoginForm(FlaskForm):
    """
    Represents a login form with fields for username and password in Arabic language.
    """
    email = StringField('البريد الإلكتروني',
                         id='email_login',
                         validators=[DataRequired(), Email()])
    password = PasswordField('كلمة المرور',
                             id='pwd_login',
                             validators=[DataRequired()])


class CreateAccountForm(FlaskForm):
    """
    Represents a form for creating a new account with fields for username, email, and password in Arabic language.
    """
    username = StringField('إسم المستخدم',
                         id='username_create',
                         validators=[DataRequired()])
    email = StringField('البريد الالكتروني',
                      id='email_create',
                      validators=[DataRequired(), Email()])
    password = PasswordField('كلمة المرور',
                             id='pwd_create',
                             validators=[DataRequired()])
