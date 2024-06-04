from __future__ import unicode_literals

__author__ = 'David Baum'

import json

from django.utils.translation import gettext_lazy as gettext

from rest_framework.utils.serializer_helpers import ReturnDict


def validate_required_fields(**kwargs) -> ReturnDict:
    blank_error_message = gettext('This field may not be blank.')

    errors = dict()
    for key, value in kwargs.items():
        if not value or not value.strip():
            errors[key] = [blank_error_message]
    return errors
