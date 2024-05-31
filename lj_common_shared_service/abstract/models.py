from __future__ import unicode_literals

__author__ = 'David Baum'

import uuid

from django.db import models
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

from lj_common_shared_service.utils.file import LJRandomFileName


class LJAbstractDateHistoryModel(models.Model):
    date_created = models.DateTimeField(verbose_name=_("Date created"), auto_now_add=True, editable=False)
    date_modified = models.DateTimeField(verbose_name=_("Date modified"), auto_now=True, editable=False)

    class Meta:
        abstract = True

class LJFile(LJAbstractDateHistoryModel):
    file = models.FileField(
        default=None,
        blank=True,
        null=True,
        max_length=2048,
        verbose_name=_('File'),
        upload_to=LJRandomFileName('')
    )
    url = models.URLField(
        default=None,
        blank=True,
        null=True,
        max_length=2048,
        verbose_name=_('Reference file URL')
    )
    video_id = models.CharField(
        max_length=1024,
        default=None,
        blank=True,
        null=True,
        verbose_name=_("The video ID from the different service")
    )
    is_image = models.BooleanField(verbose_name=_('Image'), default=False)

    class Meta:
        abstract = True


class LJTag(models.Model):
    name = models.CharField(
        max_length=1024,
        verbose_name=_('Tag name')
    )
    uuid = models.UUIDField(
        unique=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_('Unique UUID hash')
    )

    class Meta:
        abstract = True


class LJAbstractBaseContribution(models.Model):
    points = models.PositiveIntegerField(default=0, verbose_name=_('Earned points'))
    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False, verbose_name=_('Unique UUID hash'))
    date_created = models.DateTimeField(verbose_name=_("Date created"), default=now, editable=False)

    class Meta:
        abstract = True
