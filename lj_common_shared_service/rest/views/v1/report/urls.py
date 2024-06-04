from __future__ import unicode_literals

__author__ = 'David Baum'

from django.conf import settings
from django.urls import path

from . import *

API_VERSION = settings.SWAGGER_SETTINGS.get('api_version', '1.0')
app_name = 'Report'

urlpatterns = [
    path(
        'api/{0}/photo/report/text/'.format(API_VERSION),
        LJPhotoReportTextDetectionViewSet.as_view(),
        name="photo_report_text_detect"
    ),

    # LJPhotoReport
    path(
        'api/{0}/photo/report/<str:uuid>/'.format(API_VERSION),
        LJPhotoReportViewSet.as_view(
            {
                'put': 'put',
            }
        ),
        name="photo_report_update_api"
    ),
    path(
        'api/{0}/photo/report/'.format(API_VERSION),
        LJPhotoReportViewSet.as_view(
            {
                'post': 'post',
            }
        ),
        name="photo_report_create_api"
    ),
]
