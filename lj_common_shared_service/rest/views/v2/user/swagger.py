from __future__ import unicode_literals

__author__ = 'David Baum'

from drf_yasg.app_settings import swagger_settings
from drf_yasg.inspectors import SwaggerAutoSchema

from lj_common_shared_service.rest.views.swagger import LJBaseOpenApiFieldInspector


class LJUserFieldInspector(LJBaseOpenApiFieldInspector):
    OMIT_PARAMETERS = ['full_name', 'last_login', 'pin_code']


class LJUserAutoSchema(SwaggerAutoSchema):
    field_inspectors = [
                           LJUserFieldInspector
                       ] + swagger_settings.DEFAULT_FIELD_INSPECTORS
