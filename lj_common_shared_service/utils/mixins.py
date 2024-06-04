from __future__ import unicode_literals

__author__ = 'David Baum'

from django.db import models
from django.db.models.fields.related import RelatedField


class LJProxyModelMixin(object):
    """
    Usage:
    ....from django.db import models
    ....models.options.DEFAULT_NAMES += ('proxy_class',)

    Derive the model from proxy model:
    ....class ApplicationEntity():
    ....    def __init__(self):
    ....        self.name: str = None
    ....class LJModel(models.Model, LJProxyModelMixin):
    ....    name = models.CharField(max_length=255, verbose_name="Name")
    ....    class Meta:
    ....        proxy_class = LJModelEntity

    Transform object to a proxy object:
    ....lj_device = new LJModel()
    ....proxy_object: LJModelEntity = lj_device.get_proxy_object()
    """

    def __repr__(self):
        return str(self.to_dict())

    def get_proxy_object(self) -> object:
        opts = self._meta

        if opts.proxy_class:
            proxy_instance = opts.proxy_class()

            for field in opts.concrete_fields + opts.many_to_many:
                if isinstance(field, models.ManyToManyField):
                    if self.pk is None:
                        value = []
                    else:
                        value = list(field.value_from_object(self).values_list('pk', flat=True))
                elif isinstance(field, RelatedField):
                    fk_object_pk = field.value_from_object(self)
                    fk_model = field.related_model

                    value = None

                    if fk_object_pk:
                        try:
                            fk_object = fk_model.objects.get(pk=fk_object_pk)
                            if hasattr(fk_object._meta, 'proxy_class'):
                                value = fk_object.get_proxy_object()
                            else:
                                value = fk_object_pk
                        except fk_model.DoesNotExist:
                            pass
                elif isinstance(field, models.JSONField):
                    value = getattr(self, field.name) or dict()
                else:
                    value = getattr(self, field.name)

                if value:
                    setattr(proxy_instance, field.name, value)

            return proxy_instance
        return None
