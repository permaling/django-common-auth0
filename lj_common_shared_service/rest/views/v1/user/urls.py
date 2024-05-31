from __future__ import unicode_literals

__author__ = 'David Baum'

from django.conf import settings
from django.urls import path

from . import *

API_VERSION = settings.SWAGGER_SETTINGS.get('api_version', '1.0')
app_name = 'User'

urlpatterns = [
    # Contact us
    path('api/{0}/user/contact/'.format(API_VERSION), ContactUsView.as_view()),
    # LJUser authentication
    path('api/{0}/user/'.format(API_VERSION), LJUserTokenAuthenticationAPIView.as_view()),
    path('api/{0}/user/organization/<str:organization_uuid>/'.format(API_VERSION),
         LJUserOrganizationPinCodeAuthenticationAPIView.as_view()),

    # LJUser token
    path('api/{0}/user/token/'.format(API_VERSION), LJUserTokenObtainPairView.as_view(), name='user_token_obtain_pair'),
    path('api/{0}/user/token/refresh/'.format(API_VERSION), LJUserTokenRefreshView.as_view(),
         name='user_token_refresh'),
    path('api/{0}/user/token/verify/'.format(API_VERSION), LJUserTokenVerifyView.as_view(), name='token_verify'),

    # Password reset
    path(
        'api/{0}/password/reset/'.format(API_VERSION), PasswordResetView.as_view(),
        name='rest_password_reset'
    ),

    path(
        'api/{0}/password/confirm/'.format(API_VERSION), PasswordResetConfirmView.as_view(),
        name='rest_password_reset_confirm'
    ),
]
