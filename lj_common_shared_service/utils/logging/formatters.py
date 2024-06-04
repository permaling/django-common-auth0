from __future__ import unicode_literals

__author__ = 'David Baum'

from pythonjsonlogger import jsonlogger


class StackdriverJsonFormatter(jsonlogger.JsonFormatter, object):
    def __init__(self, fmt="%(levelname) [%(name)s.%(funcName)s(): %(lineno)s]: %(message)s", style='%', *args,
                 **kwargs):
        jsonlogger.JsonFormatter.__init__(self, fmt=fmt, *args, **kwargs)

    def process_log_record(self, log_record):
        log_record['severity'] = log_record['levelname']
        del log_record['levelname']

        if log_record.get('name') and log_record.get('funcName') and log_record.get('lineno'):
            message = log_record.get('message', '')
            log_record.update(
                message=f"[{log_record.get('name')}.{log_record.get('funcName')}:{log_record.get('lineno')}]: {message}"
            )
        if log_record.get('ljLogKind'):
            log_record.update(
                labels=dict(ljLogKind=log_record.pop('ljLogKind', None))
            )
        return super(StackdriverJsonFormatter, self).process_log_record(log_record)
