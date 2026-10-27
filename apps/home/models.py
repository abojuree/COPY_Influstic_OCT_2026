from functools import wraps
from flask import flash, request
from flask_login import current_user
from apps import db

from icecream import ic
from sqlalchemy import event


class Log(db.Model):
    __tablename__ = "log"
    id = db.Column(db.Integer, primary_key=True)
    log_text = db.Column(db.String(255))
    creation_date = db.Column(db.Date, nullable=True, default=db.func.current_date())
    creation_time = db.Column(db.Time, nullable=True, default=db.func.current_time())
    created_by = db.Column(
        db.Integer,
        db.ForeignKey("Users.id"),
        nullable=True
    )
    # user = db.relationship(
    #     "Users", backref="log", lazy=True, cascade="all, delete-orphan"
    # )
    user_ip = db.Column(db.String(255), nullable=True)

    def add_log(log_text:str):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                result = func(*args, **kwargs)
                if request.method == 'POST':
                    try:
                        user_ip = request.remote_addr
                        if log_text:
                            new_log = Log(log_text=log_text, user_ip=user_ip)
                            db.session.add(new_log)
                            db.session.commit()
                    except Exception as e:
                        flash("فشل في تسجيل الحدث", "danger")
                        ic("Error in <add_log>: ", e)
                    finally:
                        return result
                else:
                    return result
            return wrapper
        return decorator
    
    def add_log_early(log_text: str):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    user_ip = request.remote_addr
                    if log_text:
                        new_log = Log(log_text=log_text)
                        db.session.add(new_log, user_ip=user_ip)
                        db.session.commit()
                except Exception as e:
                    ic("Error in <add_log_early>: ", e)
                    flash("فشل في تسجيل الحدث", "danger")
                finally:
                    return func(*args, **kwargs)
            return wrapper
        return decorator


@event.listens_for(Log, "before_insert")
def before_insert_listener(mapper, connection, target):
    """
    Listens for the "before_insert" event on the Log model and sets the "created_by" attribute of the target
    object to the id of the currently authenticated user.

    Parameters:
        mapper (Mapper): The mapper object that is used to map the data between the database and the object.
        connection (Connection): The database connection object.
        target (Log): The target object that is being inserted into the database.

    Returns:
        None
    """
    if current_user.is_authenticated:
        target.created_by = current_user.id
