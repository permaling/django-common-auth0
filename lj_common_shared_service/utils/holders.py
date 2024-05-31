from __future__ import unicode_literals

__author__ = 'David Baum'

from django.conf import settings

DRAW_DETAILS = {
    "text_col": (255, 255, 51),
    "font": getattr(settings, 'FONT_LOCATION', None)
}


class LJKeyValueEntry(object):
    def __init__(self, key: str or int, raw_value: str):
        self.key = key
        self.raw_value = raw_value
