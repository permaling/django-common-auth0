from __future__ import unicode_literals

__author__ = 'David Baum'

from django.utils.encoding import force_text

from rest_framework import status
from rest_framework.exceptions import APIException


class LJAPIValidationException(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'A server error occurred.'

    def __init__(self, detail, field, status_code):
        if status_code is not None: self.status_code = status_code
        if detail is not None:
            self.detail = {field: [force_text(detail)]}
        else:
            self.detail = {'detail': [force_text(self.default_detail)]}
