from __future__ import unicode_literals

__author__ = 'David Baum'

import uuid

from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from lj_common_shared_service.utils.enums import LJDeviceTypeEnum

User = get_user_model()

models.options.DEFAULT_NAMES += ('proxy_class',)

class LJPhotoReport(models.Model):
    name = models.CharField(max_length=255, verbose_name=_("Name"), blank=True, null=True, default=None)
    created_at = models.DateTimeField(_('Date created'), default=timezone.now)
    user = models.ForeignKey(User, related_name='user_report',
                             on_delete=models.SET_NULL,
                             blank=True,
                             null=True, default=None)
    device_type = models.CharField(
        max_length=255,
        choices=[(device_type.value.key, device_type.value.raw_value) for device_type in LJDeviceTypeEnum],
        verbose_name=_('Device type'),
        default=LJDeviceTypeEnum.WEB.value.key
    )
    is_result_correct = models.BooleanField(
        verbose_name=_("The user verified the result is correct"),
        blank=True, null=True
    )
    status = models.CharField(max_length=255, verbose_name=_("Report status"), blank=True, null=True,
                              default=None)
    message = models.CharField(max_length=2048, verbose_name=_("Report message"), blank=True, null=True,
                               default=None)
    output = models.JSONField(verbose_name=_("Report output"), blank=True, null=True,
                       default=None)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name=_("UUID"))
    camera_angle_to_surface = models.FloatField(default=0.0, verbose_name=_("Camera angle to surface"))
    camera_distance_to_surface = models.FloatField(default=0.0, verbose_name=_("Camera distance to surface"))

    class Meta:
        verbose_name_plural = _("Photo Reports")
        verbose_name = _("Photo Report")

    def __str__(self):
        return u"%s" % self.name

    def __unicode__(self):
        return self.name


class LJCategoricalVariable(models.Model):
    name = models.CharField(max_length=255, verbose_name=_("Categorical variable name"), db_index=True)

    class Meta:
        verbose_name_plural = _("Categorical variable")
        verbose_name = _("Categorical variable")

    def __str__(self):
        return u"%s" % self.name


class LJCategoricalValue(models.Model):
    categorical_variable = models.ForeignKey(
        LJCategoricalVariable,
        verbose_name=_("Variable name"),
        on_delete=models.CASCADE,
        related_name="categorical_variable_value"
    )
    value = models.CharField(max_length=255, verbose_name=_("Attribute value"))
    index = models.IntegerField(
        verbose_name=_("Attribute index"),
        default=0,
        validators=[
            MaxValueValidator(100000),
            MinValueValidator(0)
        ]
    )

    class Meta:
        verbose_name_plural = _("Categorical values")
        verbose_name = _("Categorical value")

    def __str__(self):
        return u"%s %s" % (self.categorical_variable.name, self.value)

    def __unicode__(self):
        return self.value
