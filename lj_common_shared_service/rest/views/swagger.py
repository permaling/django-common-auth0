from __future__ import unicode_literals

__author__ = 'David Baum'

from collections import OrderedDict

from drf_yasg import openapi
from drf_yasg.inspectors import FieldInspector


class LJBaseOpenApiFieldInspector(FieldInspector):
    OMIT_PARAMETERS = []

    def process_result(self, result, method_name, obj, **kwargs):
        if isinstance(result, openapi.Parameter):
            if result.name in self.OMIT_PARAMETERS:
                return None
        if isinstance(result, openapi.Schema.OR_REF):
            schema = openapi.resolve_ref(result, self.components)
            self._check_schema_properties(schema)
            self._check_schema_required(schema)
        return result

    def _check_schema_properties(self, schema):
        if getattr(schema, 'properties', {}):
            properties = OrderedDict()
            for key, val in schema.properties.items():
                if key not in self.OMIT_PARAMETERS:
                    properties[key] = openapi.resolve_ref(val, self.components) or val
            schema.properties = properties

    def _check_schema_required(self, schema):
        if getattr(schema, 'required', []):
            required = []
            for req in schema.required:
                if req not in self.OMIT_PARAMETERS:
                    required.append(req)
            schema.required = required
