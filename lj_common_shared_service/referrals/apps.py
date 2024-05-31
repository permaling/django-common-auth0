from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class ReferralConfig(AppConfig):
    """ Default configuration for referrals."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'lj_common_shared_service.referrals'
    label = 'referral'
    verbose_name = _("Referrals")
