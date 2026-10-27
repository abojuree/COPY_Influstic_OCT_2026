from flask_login import UserMixin
from apps import db, login_manager
from apps.authentication.util import hash_pass


class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    permissions = db.Column(db.JSON, default=dict)

    users = db.relationship('Users', backref='role_model', lazy=True)


class Users(db.Model, UserMixin):
    """
    User model for the authentication system.
    """

    __tablename__ = 'Users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True)
    email = db.Column(db.String(64), unique=True)
    password = db.Column(db.LargeBinary)
    phone = db.Column(db.String(20), nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    # User Roles: 'admin', 'user', or custom role
    role = db.Column(db.String(20), default='user')
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=True)

    # SaaS: Link the user to their tenant (Agency)
    agency_id = db.Column(db.Integer, db.ForeignKey('agencies.id'), nullable=True, index=True)

    # Custom RBAC Overrides
    custom_permissions = db.Column(db.JSON, nullable=True)

    logs = db.relationship("Log", backref="user", lazy=True, cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        """
        Initialize the user object.

        Args:
            **kwargs: Keyword arguments for the user attributes.
        """
        for property, value in kwargs.items():
            # Depending on whether value is an iterable or not, we must
            # unpack it's value (when **kwargs is request.form, some values
            # will be a 1-element list)
            if hasattr(value, '__iter__') and not isinstance(value, (str, dict)):
                # The ,= unpack of a singleton fails PEP8 (travis flake8 test)
                try:
                    value = value[0]
                except (KeyError, TypeError):
                    pass

            if property == 'password':
                value = hash_pass(value)  # We need bytes here (not plain str)

            setattr(self, property, value)

    def __repr__(self):
        """
        Return a string representation of the user.

        Returns:
            str: Username of the user.
        """
        return str(self.username)

    @property
    def is_system_employee(self):
        """
        Check if this user belongs to the main admin's agency (making them an internal system employee)
        """
        if self.role == 'admin':
            return True
        master_admin = Users.query.filter_by(username='admin').first()
        return master_admin and self.agency_id == master_admin.agency_id


@login_manager.user_loader
def user_loader(id):
    """
    Load a user from the database based on their ID.

    :param id: The ID of the user to load.
    :type id: int
    :return: The user object if found, None otherwise.
    :rtype: Users or None
    """
    return Users.query.filter_by(id=id).first()


@login_manager.request_loader
def request_loader(request):
    """
    Load a user from the database based on the request.

    :param request: The request object.
    :type request: object
    :return: The user object if found, None otherwise.
    :rtype: Users or None
    """
    username = request.form.get('username')
    user = Users.query.filter_by(username=username).first()
    return user if user else None
