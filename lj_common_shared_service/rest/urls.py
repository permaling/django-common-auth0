from __future__ import unicode_literals

__author__ = 'David Baum'

from django.conf import settings
from django.urls import path, include

from .views.v1 import urls as v1_rest_api_urls
from .views.v2 import urls as v2_rest_api_urls

API_VERSION = settings.SWAGGER_SETTINGS.get('api_version', '1.0')

urlpatterns = [
    path(r'', include(v1_rest_api_urls)),
    path(r'', include(v2_rest_api_urls)),
]
