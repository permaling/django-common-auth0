from __future__ import unicode_literals

__author__ = 'Soren Harner'

import json

from django.utils.translation import gettext_lazy as gettext
from rest_framework import serializers, status
from lj_common_shared_service.core.models import LJPhotoReport
from lj_common_shared_service.rest.exceptions.api import LJAPIValidationException
from lj_common_shared_service.rest.validators import validate_required_fields, validate_json_fields, uuid_validate
from lj_common_shared_service.utils.enums import LJDeviceTypeEnum
from lj_common_shared_service.utils.utils import value_to_bool


class LJPhotoReportModelSerializer(serializers.ModelSerializer):
    output = serializers.JSONField(required=False)

    class Meta:
        model = LJPhotoReport
        fields = (
            'id', 'name', 'created_at', 'user', 'device_type',
            'is_result_correct', 'status', 'message', 'output', 'uuid',
            'camera_angle_to_surface', 'camera_distance_to_surface',
        )
        read_only_fields = (
            'id', 'created_at', 'uuid',
        )

    def run_validation(self, data):
        name = data.get('name')
        device_type = data.get('device_type')
        output = data.get('output', "{}")
        uuid = data.pop('uuid', None)
        is_result_correct = data.pop('is_result_correct', None)

        try:
            required_fields = dict()
            errors = dict()
            if uuid:
                uuid_validate.validate(uuid=uuid)
                errors = uuid_validate.errors
                required_fields.update(is_result_correct=is_result_correct)
            else:
                required_fields.update(
                    device_type=device_type,
                    name=name,
                )
            errors = {
                **errors,
                **validate_json_fields(**dict(output=output)),
                **validate_required_fields(
                    **required_fields
                )
            }
            if device_type and not LJDeviceTypeEnum.get_type(str(device_type)):
                errors.update(
                    status=gettext(
                        f'Invalid parameter, allowed values: {LJDeviceTypeEnum.drf_description()}'
                    )
                )
            if len(errors.keys()) > 0:
                raise serializers.ValidationError(errors)
            if uuid:
                self.Meta.model.objects.select_related().get(
                    uuid=uuid,
                )
            if is_result_correct is not None:
                data.update(
                    is_result_correct=value_to_bool(is_result_correct)
                )
            data.update(
                output=json.loads(output) if isinstance(output, str) else output
            )
        except  self.Meta.model.DoesNotExist:
            raise LJAPIValidationException(gettext('The photo report is not found'), 'uuid',
                                           status_code=status.HTTP_404_NOT_FOUND)
        return data

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        return instance
