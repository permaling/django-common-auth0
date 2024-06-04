from __future__ import unicode_literals

__author__ = 'David Baum'

from django.utils.translation import ugettext_lazy as _

from lj_common_shared_service.utils.utils import is_valid_uuid


class UUIDRequestParameterValidator(object):

    def __init__(self):
        self.errors = dict()

    def validate(self, **kwargs):
        self.errors = dict()
        for key, value in kwargs.items():
            if not is_valid_uuid(value):
                self.errors[key] = [_("The provided UUID is not of the UUID format.")]

    def has_errors(self) -> bool:
        return len(self.errors.items()) > 0


uuid_validate = UUIDRequestParameterValidator()
