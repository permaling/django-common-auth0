from __future__ import unicode_literals

__author__ = 'David Baum'

from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class LJRESTConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'lj_common_shared_service.rest'
    label = 'lj_common_shared_service_rest'
    verbose_name = _("Rest API")
