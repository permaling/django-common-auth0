# Django Common Auth0 Service

## Get Started

1. Install the library:

    ```bash
    pip install git+https://github.com/permaling/django-common-auth0.git
    ```

1. Add "lj_common_shared_service" to your INSTALLED_APPS setting like this:

    ```py
    INSTALLED_APPS = [
        ...
        'lj_common_shared_service',
    ]
    ```

1. To use the Auth0 service put the following into::

    ```py
    REST_FRAMEWORK = {
        ....
        'DEFAULT_AUTHENTICATION_CLASSES': (
            'rest_framework.authentication.TokenAuthentication',
            'rest_framework.authentication.SessionAuthentication',
            'rest_framework.authentication.BasicAuthentication',
            'lj_common_shared_service.auth0.authentication.LJJSONWebTokenAuthentication',
        )
        ....
    ]
    ```

1. Set the Auth0 credentials in the settings.py:

    ```py
    AUTH0_AUDIENCE = ''
    AUTH0_DOMAIN = ''
    AUTH0_KEY = ''
    AUTH0_SECRET = ''
    ```

1. Set the following entries::

    ```py
    AUTHENTICATION_BACKENDS = (
        "django.contrib.auth.backends.ModelBackend",
        "django.contrib.auth.backends.RemoteUserBackend",
        ...
    )
    ```

    ```py
    JWT_AUTH = {
        'JWT_PAYLOAD_GET_USERNAME_HANDLER':
            'lj_common_shared_service.auth0.helper.jwt_get_username_from_payload_handler',
        'JWT_DECODE_HANDLER':
            'lj_common_shared_service.auth0.helper.jwt_decode_token',
        'JWT_ALGORITHM': 'RS256',
        'JWT_AUTH_HEADER_PREFIX': 'Bearer',
        'JWT_ALLOW_REFRESH': True
    }
    ```

1. Run `python manage.py migrate` to create the models.
