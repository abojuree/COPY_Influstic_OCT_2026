from flask_wtf import FlaskForm
from wtforms import HiddenField, StringField, SelectField, SelectMultipleField, ValidationError
from wtforms.validators import DataRequired

from apps.content_types.models import Content

class SocialAccountForm(FlaskForm):
    platform = SelectField("المنصة",validators=[DataRequired()])
    username = StringField("إسم المستخدم", validators=[DataRequired()])
    # content_type = SelectField("نوع المحتوى",validators=[DataRequired()])
    bio_text = StringField("البايو")
    profile_picture = HiddenField("صورة الحساب")
    # contents = QuerySelectMultipleField(query_factory=lambda: Content.query.all())
    contents = SelectMultipleField(
        "المحتوى", 
        validators=[DataRequired(message="يجب إختيار نوع محتوى واحد على الأقل")],
        coerce=int
    )
    external_url = StringField("الرابط الخارجي", render_kw={"type": "url"})
    public_profile_name = StringField("الإسم على المنصة", render_kw={"readonly": True})
    # set_as_default_profile_picture = BooleanField("إستخدم صورة الحساب كصورة رئيسية للملف")

    def validate_contents(self, field):
        # Additional custom validation if needed
        if not field.data:
            raise ValidationError("يجب إختيار نوع محتوى واحد على الأقل")
