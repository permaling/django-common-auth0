from __future__ import unicode_literals

__author__ = 'David Baum'

from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class LJCoreConfig(AppConfig):
    """ Default configuration for custom_user."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'lj_common_shared_service.core'
    label = 'core'
    verbose_name = _("Core")

