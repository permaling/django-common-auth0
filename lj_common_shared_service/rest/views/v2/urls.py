from __future__ import unicode_literals

__author__ = 'David Baum'

from django.conf import settings
from django.urls import path, include

from .user import urls as user_urls

API_VERSION = settings.SWAGGER_SETTINGS.get('api_new_version', 'v2')


urlpatterns = [
    path(r'', include((user_urls, API_VERSION), namespace=user_urls.app_name)),
]
