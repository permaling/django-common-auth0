from __future__ import unicode_literals

__author__ = 'David Baum'

from django.conf import settings
from django.urls import path

from . import *

API_VERSION = settings.SWAGGER_SETTINGS.get('api_version', '1.0')
app_name = 'Organization'

urlpatterns = [
    # LJOrganization
    path(
        'api/{0}/organization/'.format(API_VERSION),
        LJOrganizationViewSet.as_view(
            {
                'post': 'post',
                'get': 'get',
                'delete': 'delete',
                'put': 'put'
            }
        ),
        name="organization_api"
    ),

    path(
        'api/{0}/organization/<str:organization_uuid>/'.format(API_VERSION),
        LJSimpleOrganizationViewSet.as_view(),
        name="user_organization_api",
    ),

    # LJOrganization admin
    path(
        'api/{0}/admin/organization/'.format(API_VERSION),
        LJOrganizationAdminViewSet.as_view(
            {
                'get': 'list',
                'post': 'post'
            }
        ),
        name="admin_organization_create_list_api"
    ),
    path(
        'api/{0}/admin/organization/<int:organization_id>/'.format(API_VERSION),
        LJOrganizationAdminViewSet.as_view(
            {
                'delete': 'delete',
                'put': 'put',
                'get': 'get'
            }
        ),
        name="admin_organization_api"
    ),
]
