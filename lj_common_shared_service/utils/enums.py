from __future__ import unicode_literals

__author__ = 'David Baum'

from enum import Enum
from typing import Type, Union, List

from django.utils.translation import ugettext_lazy as _

from .holders import LJKeyValueEntry


class AutoStrEnum(str, Enum):
    """
    StrEnum where auto() returns the field name.
    See https://docs.python.org/3.9/library/enum.html#using-automatic-values
    """

    @staticmethod
    def _generate_next_value_(name: str, start: int, count: int, last_values: list) -> str:
        return name


class BaseEnum(Enum):
    @classmethod
    def get_type(cls, key: Union[int, str]) -> LJKeyValueEntry or None:
        if isinstance(key, str) and key.isnumeric():
            key = int(key)
        for entry in cls:
            entry_value_key = entry.value.key
            if (isinstance(key, int) and int(entry_value_key) == key) or entry_value_key == key:
                return entry
        return None

    @classmethod
    def get_model_choices(cls) -> List:
        return [(entry.value.key, entry.value.raw_value) for entry in cls]

    @classmethod
    def drf_description(cls):
        return ", ".join(
            [
                "{} {} {}".format(entry.value.key, _("which designates"), entry.value.raw_value, ) for entry in cls
            ]
        )

    @classmethod
    def get_keys(cls):
        return [entry.value.key for entry in cls]


class OrganizationTeamMemberStatusEnum(BaseEnum):
    INVITED = LJKeyValueEntry(key="0", raw_value=_("Invited"))
    ACTIVE = LJKeyValueEntry(key="1", raw_value=_("Active"))
    INACTIVE = LJKeyValueEntry(key="2", raw_value=_("Inactive"))


class LJOrganizationStatusEnum(BaseEnum):
    HOLD = LJKeyValueEntry(key="0", raw_value=_("Hold"))
    ACTIVE = LJKeyValueEntry(key="1", raw_value=_("Active"))


class LJDeviceTypeEnum(BaseEnum):
    WEB = LJKeyValueEntry(key="0", raw_value=_("elp"))
    MOBILE = LJKeyValueEntry(key="1", raw_value=_("iphonex"))


class LJOrganizationTeamMemberRoleEnum(BaseEnum):
    MEMBER = LJKeyValueEntry(key="0", raw_value=_("Member"))
    EDITOR = LJKeyValueEntry(key="1", raw_value=_("Editor"))
    ADMIN = LJKeyValueEntry(key="2", raw_value=_("Admin"))


class LJOrganizationApplicationEnum(BaseEnum):
    SID = LJKeyValueEntry(key="0", raw_value=_("SID"))
    EZT = LJKeyValueEntry(key="1", raw_value=_("Easy Tray"))
    AID = LJKeyValueEntry(key="2", raw_value=_("AID"))
