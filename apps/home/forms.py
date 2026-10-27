from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired

class SearchForm(FlaskForm):
    platform = SelectField("المنصة", validators=[DataRequired()])
    username = StringField("إسم المستخدم", validators=[DataRequired()])
    submit = SubmitField("بحث")