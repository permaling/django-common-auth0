from __future__ import unicode_literals

__author__ = 'David Baum'

import sys
import traceback
import logging

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import exceptions
from rest_framework import status

logger = logging.getLogger(__name__)


class BaseView(APIView):
    def handle_exception(self, exc):
        status_code = status.HTTP_400_BAD_REQUEST
        if isinstance(exc, exceptions.APIException):
            status_code = exc.status_code
        exception_info = sys.exc_info()
        tb = exception_info[2]

        logger.error(repr(exception_info))
        logger.error("".join(traceback.format_tb(tb)))

        return Response(dict(), status=status_code, exception=exc)
