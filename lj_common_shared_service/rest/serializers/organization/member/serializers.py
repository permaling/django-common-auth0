from __future__ import unicode_literals

__author__ = 'David Baum'

from lj_common_shared_service.rest.serializers.user.user import LJShortUserModelSerializer
from lj_common_shared_service.authentication.models import LJOrganizationTeamMember

from rest_framework import serializers


class LJOrganizationTeamMemberModelSerializer(serializers.ModelSerializer):
    user_data = LJShortUserModelSerializer(source='user', many=False, read_only=True)

    class Meta:
        model = LJOrganizationTeamMember
        fields = (
            'id', 'uuid', 'user', 'organization', 'user_data', 'is_organization_admin',
            'is_organization_editor', 'is_organization_editor', 'status',
        )
        read_only_fields = (
            'id', 'uuid', 'user_data', 'is_organization_admin',
            'is_organization_editor', 'is_organization_editor',
        )
