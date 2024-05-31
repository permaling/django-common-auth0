from __future__ import unicode_literals

__author__ = 'David Baum'

from django.urls import path

from . import *

API_VERSION = settings.SWAGGER_SETTINGS.get('api_version', '1.0')
app_name = 'Auth0 User'

urlpatterns = [
    path(
        f'api/{API_VERSION}/user/auth0/organization/', LJAuth0UserOrganizationInvitation.as_view(),
        name='auth0_user_organization_invitation'
    ),
    path(
        f'api/{API_VERSION}/user/auth0/', LJAuth0UserManagementAPIView.as_view(
            {
                'get': 'list'
            }
        ),
        name='auth0_user_management'
    )
]
