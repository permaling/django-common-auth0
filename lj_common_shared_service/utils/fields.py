from __future__ import unicode_literals

__author__ = 'David Baum'

import shortuuid
import six

from django.db.models import CharField


class LJShortUUIDField(CharField):
    """
    A field which stores a Short UUID value in base57 format. This may also have
    the Boolean attribute 'auto' which will set the value on initial save to a
    new UUID value (calculated using shortuuid's default (uuid4)). Note that while all
    UUIDs are expected to be unique we enforce this with a DB constraint.
    """

    def __init__(self, auto=True, *args, **kwargs):
        self.auto = auto
        self.editable = kwargs.get('editable', False)
        # We store UUIDs in base57 format, which is fixed at 22 characters.
        kwargs['max_length'] = kwargs.get('max_length', 22)
        kwargs['editable'] = self.editable
        if auto:
            # Do not let the user edit UUIDs if they are auto-assigned.
            kwargs['blank'] = True

        super(LJShortUUIDField, self).__init__(*args, **kwargs)

    def pre_save(self, model_instance, add):
        """
        This is used to ensure that we auto-set values if required.
        See CharField.pre_save
        """
        value = super(LJShortUUIDField, self).pre_save(model_instance, add)
        if self.auto and not value:
            # Assign a new value for this attribute if required.
            value = six.text_type(shortuuid.ShortUUID().random(length=self.max_length))
            setattr(model_instance, self.attname, value.upper())
        return value

    def formfield(self, **kwargs):
        if not self.editable:
            return None
        return super(LJShortUUIDField, self).formfield(**kwargs)

try:
    from south.modelsinspector import add_introspection_rules
    add_introspection_rules([], [r"^shortuuidfield\.fields\.ShortUUIDField"])
except ImportError:
    pass