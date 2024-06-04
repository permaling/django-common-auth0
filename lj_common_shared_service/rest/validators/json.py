from __future__ import unicode_literals

__author__ = 'David Baum'

import json

from django.utils.translation import gettext_lazy as gettext

from rest_framework.utils.serializer_helpers import ReturnDict


def validate_json_fields(**kwargs) -> ReturnDict:
    blank_error_message = gettext('This field is not a valid JSON.')

    def is_json(data):
        if isinstance(data, str):
            try:
                json.loads(data)
            except ValueError:
                return False
            return True
        return isinstance(data, list) or isinstance(data, dict)

    errors = dict()
    for key, value in kwargs.items():
        if not value or not is_json(value):
            errors[key] = [blank_error_message]
    return errors
