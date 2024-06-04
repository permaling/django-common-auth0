from __future__ import unicode_literals

__author__ = 'David Baum'

from drf_yasg.app_settings import swagger_settings
from drf_yasg.inspectors import SwaggerAutoSchema

from lj_common_shared_service.rest.views.swagger import LJBaseOpenApiFieldInspector


class LJPhotoReportViewSetFieldInspector(LJBaseOpenApiFieldInspector):
    OMIT_PARAMETERS = ['user', ]


class LJPhotoReportViewSetAutoSchema(SwaggerAutoSchema):
    field_inspectors = [
                           LJPhotoReportViewSetFieldInspector
                       ] + swagger_settings.DEFAULT_FIELD_INSPECTORS