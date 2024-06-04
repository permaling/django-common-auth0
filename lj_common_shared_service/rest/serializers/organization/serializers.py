from __future__ import unicode_literals

__author__ = 'David Baum'

from lj_common_shared_service.authentication.models import LJOrganization

from rest_framework import serializers


class LJOrganizationModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = LJOrganization
        fields = (
            'id', 'name', 'uuid', 'invitation_code', "status", "photo",
            'is_validate_email', 'team_name', 'address', 'company',
            'phone_number', 'status',
        )
        read_only_fields = ('id', 'uuid',)
