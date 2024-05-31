from __future__ import unicode_literals

__author__ = 'David Baum'

from django.conf import settings
from django.urls import path

from .views import *

API_VERSION = settings.SWAGGER_SETTINGS.get('api_new_version', 'v2')
app_name = 'Hub User'


urlpatterns = [
    path('api/{0}/user/referral/'.format(API_VERSION), ReferralCodeView.as_view(), name="v2_referral_user_api"),
    path('api/{0}/user/disable/'.format(API_VERSION), DisableUserAPIView.as_view(), name="v2_disable_user_api"),
    path(
        'api/{0}/user/'.format(API_VERSION),
        LJUserViewSet.as_view(
            {
                'get': 'list',
            }
        ),
        name="v2_user_create_list_api"
    ),
    path(
        'api/{0}/user/<str:uuid>/'.format(API_VERSION),
        LJUserViewSet.as_view(
            {
                'delete': 'delete',
                'put': 'put',
                'get': 'get'
            }
        ),
        name="v2_users_api"
    )
]
