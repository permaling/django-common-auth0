from __future__ import unicode_literals

__author__ = 'David Baum'

from django.conf import settings
from django.urls import path, include

from .organization import urls as organization_urls
from .report import urls as report_urls
from .user import urls as user_urls
from .user.auth0 import urls as auth0_user_urls

API_VERSION = settings.SWAGGER_SETTINGS.get('api_version', '1.0')

urlpatterns = [
    path(r'', include((organization_urls, API_VERSION), namespace=organization_urls.app_name)),
    path(r'', include((report_urls, API_VERSION), namespace=report_urls.app_name)),
    path(r'', include((user_urls, API_VERSION), namespace=user_urls.app_name)),
    path(r'', include((auth0_user_urls, API_VERSION), namespace=auth0_user_urls.app_name)),
]
