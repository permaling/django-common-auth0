from __future__ import unicode_literals

__author__ = 'David Baum'

from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class LJUtilsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'lj_common_shared_service.utils'
    label = 'lj_common_shared_service_utils'
    verbose_name = _("Utils")

    def ready(self):
        import lj_common_shared_service.utils.signals
