from __future__ import unicode_literals

__author__ = 'David Baum'

from django.utils.translation import ugettext_lazy as _
from enum import Enum


class LJApiResponseErrors(str, Enum):
    WRONG_UUID_FORMAT = _('The provided UUID is not of the UUID format.')
    FAILED = 'FAILED'

    def __str__(self) -> str:
        return self.value
