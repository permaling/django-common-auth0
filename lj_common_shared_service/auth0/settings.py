import os

from django.conf import settings

AUTH0_AUDIENCE = os.environ.get('AUTH0_AUDIENCE', '')
AUTH0_DOMAIN = os.environ.get('AUTH0_DOMAIN', '')
AUTH0_KEY = os.environ.get('AUTH0_KEY')
AUTH0_SECRET = os.environ.get('AUTH0_SECRET')

AUTH0_SETTINGS = getattr(settings, 'AUTH0_SETTINGS', {})
AUTH0_SETTINGS = {
    **{
        'AUTH0_AUDIENCE': AUTH0_AUDIENCE,
        'AUTH0_DOMAIN': AUTH0_DOMAIN,
        'AUTH0_KEY': AUTH0_KEY,
        'AUTH0_SECRET': AUTH0_SECRET
    },
    **AUTH0_SETTINGS
}
AUTH0_USER_META_ENV = getattr(settings, 'AUTH0_USER_META_ENV', os.environ.get('AUTH0_USER_META_ENV', 'local'))
