from django.db import models
from django.contrib.auth import get_user_model

from lj_common_shared_service.abstract.models import LJAbstractDateHistoryModel

from .utils import generate_referral_code


User = get_user_model()


class ReferralCode(LJAbstractDateHistoryModel):
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=6, unique=True, default=generate_referral_code)

    def __str__(self):
        return f"{self.owner.email} {self.code}"


class ReferralNode(LJAbstractDateHistoryModel):
    referral_code = models.ForeignKey(ReferralCode, on_delete=models.CASCADE)
    referred = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('referral_code', 'referred')

    def __str__(self):
        return f"{self.referred.email} {self.referral_code.code}"
