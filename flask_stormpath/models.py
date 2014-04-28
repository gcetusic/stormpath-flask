from flask import current_app
from stormpath.resources.account import Account


class User(Account):
    """
    The base User object.

    This can be used as described in the Stormpath Python SDK documentation:
    https://github.com/stormpath/stormpath-sdk-python
    """
    def __repr__(self):
        return u'User <"%s" ("%s")>' % (self.username or self.email, self.href)

    def get_id(self):
        """
        Return the unique user identifier (in our case, the Stormpath resource
        href).
        """
        return unicode(self.href)

    def is_active(self):
        """
        A user account is active if, and only if, their account status is
        'ENABLED'.
        """
        return self.status == 'ENABLED'

    def is_anonymous(self):
        """
        We don't support anonymous users, so this is always False.
        """
        return False

    def is_authenticated(self):
        """
        All users will always be authenticated, so this will always return
        True.
        """
        return True

    @classmethod
    def create(self, email, password, given_name, surname, username=None, middle_name=None, custom_data=None):
        """
        Create a new User.

        Required Params
        ---------------

        :param str email: This user's unique email address.
        :param str password: This user's password, in plain text.
        :param str given_name: This user's first name (Randall).
        :param str surname: This user's last name (Degges).

        Optional Params
        ---------------

        :param str username: If no username is supplied, it will default to the
            user's email address.  Stormpath users can log in with either an
            email or username (both are interchangable).

        :param str middle_name: This user's middle name (Clark).

        :param dict custom_data: Any custom JSON data you'd like stored with
            this user.  Must be 10MB or less.

        If something goes wrong we'll raise an exception -- most likely -- a
        StormpathError (flask.ext.stormpath.StormpathError).
        """
        _user = current_app.stormpath_manager.application.accounts.create({
            'email': email,
            'password': password,
            'given_name': given_name,
            'surname': surname,
            'username': username,
            'middle_name': middle_name,
            'custom_data': custom_data,
        })
        _user.__class__ = User

        return _user

    @classmethod
    def from_login(self, login, password):
        """
        Create a new User class given a login (email address or username), and
        password.

        If something goes wrong, this will raise an exception -- most likely --
        a StormpathError (flask.ext.stormpath.StormpathError).
        """
        _user = current_app.stormpath_manager.application.authenticate_account(
            login,
            password,
        ).account
        _user.__class__ = User

        return _user