# -*- coding: utf-8 -*-
"""
    flask-stormpath
    ---------------

    This module provides secure user authentication and authorization for Flask
    via Stormpath (https://stormpath.com/).  It lets you log users in and out
    of your application in a database-independent fashion, along with allowing
    you to store variable user information in a JSON data store.

    No user table required! :)

    :copyright: (c) 2012 - 2015 Stormpath, Inc.
    :license: Apache, see LICENSE for more details.
"""


__version__ = '0.4.4'
__version_info__ = __version__.split('.')
__author__ = 'Stormpath, Inc.'
__license__ = 'Apache'
__copyright__ = '(c) 2012 - 2015 Stormpath, Inc.'

import os

from flask import (
    Blueprint,
    __version__ as flask_version,
    _app_ctx_stack as stack,
    current_app,
)

from flask.ext.login import (
    LoginManager,
    current_user,
    _get_user,
    login_required,
    login_user,
    logout_user,
)

from stormpath.client import Client
from stormpath.error import Error as StormpathError
from stormpath_config.loader import ConfigLoader
from stormpath_config.strategies import (
    LoadEnvConfigStrategy, LoadFileConfigStrategy, LoadAPIKeyConfigStrategy,
    LoadAPIKeyFromConfigStrategy, ValidateClientConfigStrategy,
    MoveAPIKeyToClientAPIKeyStrategy, EnrichClientFromRemoteConfigStrategy,
    EnrichIntegrationFromRemoteConfigStrategy)

from werkzeug.local import LocalProxy

from .context_processors import user_context_processor
from .models import User
from .settings import StormpathSettings
from .views import (
    google_login,
    facebook_login,
    forgot,
    forgot_change,
    login,
    logout,
    register,
)


# A proxy for the current user.
user = LocalProxy(lambda: _get_user())


class StormpathManager(object):
    """
    This object is used to hold the settings used to communicate with
    Stormpath.  Instances of :class:`StormpathManager` are not bound to
    specific apps, so you can create one in the main body of your code and
    then bind it to your app in a factory function.
    """
    def __init__(self, app=None):
        """
        Initialize this extension.

        :param obj app: (optional) The Flask app.
        """
        self.app = app

        # If the user specifies an app, let's configure go ahead and handle all
        # configuration stuff for the user's app.
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """
        Initialize this application.

        This method will handle:

            - Configuring application settings.
            - Configuring Flask-Stormpath.
            - Adding ourself to the user's app (so the user can reference this
              extension later on, if they want).

        :param obj app: The Flask app.
        """
        # Initialize all of the Flask-Stormpath configuration variables and
        # settings.
        self.init_settings(app.config)

        # Check our user defined settings to ensure Flask-Stormpath is properly
        # configured.
        self.check_settings(app.config)

        # Initialize the Flask-Login extension.
        self.init_login(app)

        # Initialize all URL routes / views.
        self.init_routes(app)

        # Initialize our blueprint.  This lets us do cool template stuff.
        blueprint = Blueprint(
            'flask_stormpath', 'flask_stormpath', template_folder='templates')
        app.register_blueprint(blueprint)

        # Ensure the `user` context is available in templates.  This makes it
        # really easy for developers to grab user data for display purposes in
        # templates.
        app.context_processor(user_context_processor)

        # Store a reference to the Flask app so we can use it later if
        # necessary!
        self.app = app

    def init_settings(self, config):
        """
        Initialize the Flask-Stormpath settings.

        This function sets all default configuration values.

        :param dict config: The Flask app config.
        """
        # Basic Stormpath credentials and configuration.
        web_config_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'config/default-config.yml')
        config_loader = ConfigLoader(
            load_strategies=[
                LoadFileConfigStrategy(web_config_file),
                LoadAPIKeyConfigStrategy("~/.stormpath/apiKey.properties"),
                LoadFileConfigStrategy("~/.stormpath/stormpath.json"),
                LoadFileConfigStrategy("~/.stormpath/stormpath.yaml"),
                LoadAPIKeyConfigStrategy("./apiKey.properties"),
                LoadFileConfigStrategy("./stormpath.yaml"),
                LoadFileConfigStrategy("./stormpath.json"),
                LoadEnvConfigStrategy(prefix='STORMPATH')
            ],
            post_processing_strategies=[
                LoadAPIKeyFromConfigStrategy(), MoveAPIKeyToClientAPIKeyStrategy()
            ],
            validation_strategies=[ValidateClientConfigStrategy()])
        config['stormpath'] = StormpathSettings(config_loader.load())

        # Most of the settings are used for backwards compatibility.
        config.setdefault('STORMPATH_API_KEY_ID', None)
        config.setdefault('STORMPATH_API_KEY_SECRET', None)
        # FIXME: this breaks the code because it's not in the spec
        # config.setdefault('STORMPATH_API_KEY_FILE', None)
        config.setdefault('STORMPATH_APPLICATION', None)

        # Which fields should be displayed when registering new users?
        # FIXME: this breaks the code because it's not in the spec
        # config.setdefault('STORMPATH_ENABLE_FACEBOOK', False)
        # config.setdefault('STORMPATH_ENABLE_GOOGLE', False)
        # config.setdefault('STORMPATH_ENABLE_EMAIL', True)  # If this is diabled,
                                                           # only social login can
                                                           # be used.

        # Will new users be required to verify new accounts via email before
        # they're made active?
        # FIXME: this breaks the code because it's not in the spec
        # config.setdefault('STORMPATH_VERIFY_EMAIL', False)

        # Configure URL mappings.  These URL mappings control which URLs will be
        # used by Flask-Stormpath views.
        # FIXME: this breaks the code because it's not in the spec
        # config.setdefault('STORMPATH_GOOGLE_LOGIN_URL', '/google')
        # config.setdefault('STORMPATH_FACEBOOK_LOGIN_URL', '/facebook')

        # After a successful login, where should users be redirected?
        config.setdefault('STORMPATH_REDIRECT_URL', '/')

        # Cache configuration.
        # FIXME: this breaks the code because it's not in the spec
        # config.setdefault('STORMPATH_CACHE', None)

        # Configure templates.  These template settings control which templates are
        # used to render the Flask-Stormpath views.
        # FIXME: some of the settings break the code because they're not in the spec
        # config.setdefault('STORMPATH_BASE_TEMPLATE', 'flask_stormpath/base.html')
        config.setdefault('STORMPATH_REGISTRATION_TEMPLATE', 'flask_stormpath/register.html')
        config.setdefault('STORMPATH_LOGIN_TEMPLATE', 'flask_stormpath/login.html')
        config.setdefault('STORMPATH_FORGOT_PASSWORD_TEMPLATE', 'flask_stormpath/forgot.html')
        # config.setdefault('STORMPATH_FORGOT_PASSWORD_EMAIL_SENT_TEMPLATE', 'flask_stormpath/forgot_email_sent.html')
        config.setdefault('STORMPATH_FORGOT_PASSWORD_CHANGE_TEMPLATE', 'flask_stormpath/forgot_change.html')
        # config.setdefault('STORMPATH_FORGOT_PASSWORD_COMPLETE_TEMPLATE', 'flask_stormpath/forgot_complete.html')

        # Social login configuration.
        # FIXME: this breaks the code because it's not in the spec
        # config.setdefault('STORMPATH_SOCIAL', {})

        # Cookie configuration.
        # FIXME: this breaks the code because it's not in the spec
        # config.setdefault('STORMPATH_COOKIE_DOMAIN', None)
        # config.setdefault('STORMPATH_COOKIE_DURATION', timedelta(days=365))

        # Cookie name (this is not overridable by users, at least not explicitly).
        config.setdefault('REMEMBER_COOKIE_NAME', 'stormpath_token')

        for key, value in config.items():
            if key.startswith(config['stormpath'].STORMPATH_PREFIX):
                config['stormpath'][key] = value

        # If the user is specifying their credentials via a file path,
        # we'll use this.
        if self.app.config['stormpath']['client']['apiKey']['file']:
            stormpath_client = Client(
                api_key_file_location=self.app.config['stormpath']['client']['apiKey']['file'],
            )

        # If the user isn't specifying their credentials via a file
        # path, it means they're using environment variables, so we'll
        # try to grab those values.
        else:
            stormpath_client = Client(
                id=self.app.config['stormpath']['client']['apiKey']['id'],
                secret=self.app.config['stormpath']['client']['apiKey']['secret'],
            )

        ecfrcs = EnrichClientFromRemoteConfigStrategy(
            client_factory=lambda client: stormpath_client)
        ecfrcs.process(self.app.config['stormpath'])
        eifrcs = EnrichIntegrationFromRemoteConfigStrategy(
            client_factory=lambda client: stormpath_client)
        eifrcs.process(self.app.config['stormpath'])

    def check_settings(self, config):
        """
        Ensure the user-specified settings are valid.

        This will raise a ConfigurationError if anything mandatory is not
        specified.

        :param dict config: The Flask app config.
        """
        # FIXME: this needs to be uncommented based on settings in init_settings
        # if config['STORMPATH_ENABLE_GOOGLE']:
        #     google_config = config['STORMPATH_SOCIAL'].get('GOOGLE')

        #     if not google_config or not all([
        #         google_config.get('client_id'),
        #         google_config.get('client_secret'),
        #     ]):
        #         raise ConfigurationError('You must define your Google app settings.')

        # if config['STORMPATH_ENABLE_FACEBOOK']:
        #     facebook_config = config['STORMPATH_SOCIAL'].get('FACEBOOK')

        #     if not facebook_config or not all([
        #         facebook_config,
        #         facebook_config.get('app_id'),
        #         facebook_config.get('app_secret'),
        #     ]):
        #         raise ConfigurationError('You must define your Facebook app settings.')

        # if config['STORMPATH_COOKIE_DOMAIN'] and not isinstance(config['STORMPATH_COOKIE_DOMAIN'], str):
        #     raise ConfigurationError('STORMPATH_COOKIE_DOMAIN must be a string.')

        # if config['STORMPATH_COOKIE_DURATION'] and not isinstance(config['STORMPATH_COOKIE_DURATION'], timedelta):
        #     raise ConfigurationError('STORMPATH_COOKIE_DURATION must be a timedelta object.')

    def init_login(self, app):
        """
        Initialize the Flask-Login extension.

        We use Flask-Login for managing sessions (primarily), so setting it up
        is necessary.

        :param obj app: The Flask app.
        """
        # FIXME: not currently set in stormpath config init
        # app.config['REMEMBER_COOKIE_DURATION'] = app.config['STORMPATH_COOKIE_DURATION']
        # app.config['REMEMBER_COOKIE_DOMAIN'] = app.config['STORMPATH_COOKIE_DOMAIN']

        app.login_manager = LoginManager(app)
        app.login_manager.user_callback = self.load_user
        app.stormpath_manager = self

        if app.config['stormpath']['web']['login']['enabled']:
            app.login_manager.login_view = 'stormpath.login'

        # Make this Flask session expire automatically.
        # FIXME: not currently set in stormpath config init
        # app.config['PERMANENT_SESSION_LIFETIME'] = app.config['STORMPATH_COOKIE_DURATION']

    def init_routes(self, app):
        """
        Initialize our built-in routes.

        If the user has enabled the built-in views / routes, they will be
        enabled here.

        This behavior is fully customizable in the user's settings.

        :param obj app: The Flask app.
        """
        if app.config['stormpath']['web']['register']['enabled']:
            app.add_url_rule(
                app.config['stormpath']['web']['register']['uri'],
                'stormpath.register',
                register,
                methods=['GET', 'POST'],
            )

        if app.config['stormpath']['web']['login']['enabled']:
            app.add_url_rule(
                app.config['stormpath']['web']['login']['uri'],
                'stormpath.login',
                login,
                methods=['GET', 'POST'],
            )

        if app.config['stormpath']['web']['forgotPassword']['enabled']:
            app.add_url_rule(
                app.config['stormpath']['web']['forgotPassword']['uri'],
                'stormpath.forgot',
                forgot,
                methods=['GET', 'POST'],
            )
            app.add_url_rule(
                app.config['stormpath']['web']['changePassword']['uri'],
                'stormpath.forgot_change',
                forgot_change,
                methods=['GET', 'POST'],
            )

        if app.config['stormpath']['web']['logout']['enabled']:
            app.add_url_rule(
                app.config['stormpath']['web']['logout']['uri'],
                'stormpath.logout',
                logout,
            )

        # FIXME: enable this in init_settings
        # if app.config['STORMPATH_ENABLE_GOOGLE']:
        #     app.add_url_rule(
        #         app.config['STORMPATH_GOOGLE_LOGIN_URL'],
        #         'stormpath.google_login',
        #         google_login,
        #     )

        # if app.config['STORMPATH_ENABLE_FACEBOOK']:
        #     app.add_url_rule(
        #         app.config['STORMPATH_FACEBOOK_LOGIN_URL'],
        #         'stormpath.facebook_login',
        #         facebook_login,
        #     )

    @property
    def client(self):
        """
        Lazily load the Stormpath Client object we need to access the raw
        Stormpath SDK.
        """
        ctx = stack.top.app
        if ctx is not None:
            if not hasattr(ctx, 'stormpath_client'):

                # Create our custom user agent.  This allows us to see which
                # version of this SDK are out in the wild!
                user_agent = 'stormpath-flask/%s flask/%s' % (
                    __version__, flask_version)

                # If the user is specifying their credentials via a file path,
                # we'll use this.
                if self.app.config['stormpath']['apiKey']['file']:
                    ctx.stormpath_client = Client(
                        api_key_file_location=self.app.config['stormpath']['apiKey']['file'],
                        user_agent=user_agent,
                        # FIXME: read cache from config
                        # cache_options=self.app.config['STORMPATH_CACHE'],
                    )

                # If the user isn't specifying their credentials via a file
                # path, it means they're using environment variables, so we'll
                # try to grab those values.
                else:
                    ctx.stormpath_client = Client(
                        id=self.app.config['stormpath']['apiKey']['id'],
                        secret=self.app.config['stormpath']['apiKey']['secret'],
                        user_agent=user_agent,
                        # FIXME: read cache from config
                        # cache_options=self.app.config['STORMPATH_CACHE'],
                    )

            return ctx.stormpath_client

    @property
    def login_view(self):
        """
        Return the user's Flask-Login login view, behind the scenes.
        """
        return current_app.login_manager.login_view

    @login_view.setter
    def login_view(self, value):
        """
        Proxy any changes to the user's login view to Flask-Login, behind the
        scenes.
        """
        self.app.login_manager.login_view = value

    @property
    def application(self):
        """
        Lazily load the Stormpath Application object we need to handle user
        authentication, etc.
        """
        ctx = stack.top.app
        if ctx is not None:
            if not hasattr(ctx, 'stormpath_application'):
                ctx.stormpath_application = self.client.applications.search(
                    self.app.config['stormpath']['application']['name']
                )[0]

            return ctx.stormpath_application

    @staticmethod
    def load_user(account_href):
        """
        Given an Account href (a valid Stormpath Account URL), return the
        associated User account object (or None).

        :returns: The User object or None.
        """
        user = current_app.stormpath_manager.client.accounts.get(account_href)

        try:
            user._ensure_data()
            user.__class__ = User

            return user
        except StormpathError:
            return None
