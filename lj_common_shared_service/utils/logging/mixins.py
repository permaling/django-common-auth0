from __future__ import unicode_literals

__author__ = 'David Baum'

import logging

from rest_framework_tracking.base_mixins import BaseLoggingMixin
from rest_framework_tracking.models import APIRequestLog

logger = logging.getLogger(__name__)


class LoggingMixin(BaseLoggingMixin):
    def handle_log(self):
        request_log = APIRequestLog(**self.log)
        log_record = self.log
        log_record.update(ljLogKind="apiRequest")
        message = f"API request - {request_log.remote_addr} {request_log.method} {request_log.path} {request_log.response_ms}ms "
        if request_log.status_code:
            message = f"{message} {request_log.status_code}"
        logger.info(message, extra=log_record)
