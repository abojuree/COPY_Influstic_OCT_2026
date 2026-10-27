from flask_login import current_user
from apps import db
from icecream import ic
from sqlalchemy import event


# Define Influencers Model
class Content(db.Model):
    __tablename__ = "contents"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False, unique=True)
    description = db.Column(db.String)
    creation_date = db.Column(db.Date, nullable=True, default=db.func.current_date())
    creation_time = db.Column(db.Time, nullable=True, default=db.func.current_time())
    created_by = db.Column(
        db.Integer,
        db.ForeignKey("Users.id"),
        nullable=True,
    )
    # socialaccounts = db.relationship("SocialAccount", secondary="socialaccount_content", backref="contents", lazy=True)


@event.listens_for(Content, "before_insert")
def before_insert_listener(mapper, connection, target):
    """
    Listens for the "before_insert" event on the Content model and sets the "created_by" attribute of the target
    object to the id of the currently authenticated user.

    Parameters:
        mapper (Mapper): The mapper object that is used to map the data between the database and the object.
        connection (Connection): The database connection object.
        target (Content): The target object that is being inserted into the database.

    Returns:
        None
    """
    if current_user.is_authenticated:
        target.created_by = current_user.id
