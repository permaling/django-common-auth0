from __future__ import unicode_literals

__author__ = 'David Baum'

from rest_framework import status
from rest_framework.response import Response

from lj_common_shared_service.authentication.models import LJOrganization, LJOrganizationTeamMember


class LJPaginatedListMixin(object):
    def get_paginated_list_response(self, data, is_pagination: bool = False):
        if is_pagination:
            if self.paginator and hasattr(self.paginator, 'limit') and hasattr(self.paginator, 'offset'):
                return self.get_paginated_response(data)
            else:
                data = dict(
                    count=len(data),
                    results=data
                )
        return Response(data, status=status.HTTP_200_OK)


class LJRequestUserMixin(object):
    def initial(self, request, *args, **kwargs):
        super(LJRequestUserMixin, self).initial(request, *args, **kwargs)

    def is_user_admin(self) -> bool:
        user = self.request.user
        return user and user.is_authenticated and (user.is_superuser or user.is_staff)

    def is_user_organization_creator(self) -> bool:
        organization_member = self.get_organization_team_member()
        if organization_member:
            return organization_member.is_organization_creator
        return False

    def get_organization_team_member(self) -> LJOrganizationTeamMember:
        return getattr(self.request, 'organization_member', None)

    def get_user_organization(self) -> LJOrganization:
        organization_member = self.get_organization_team_member()
        return organization_member.organization if organization_member else None

    def has_edit_organization_permissions(self) -> bool:
        organization_member = self.get_organization_team_member()
        if organization_member:
            return organization_member.is_organization_editor or organization_member.is_organization_admin
        return False

    def has_admin_organization_permissions(self) -> bool:
        organization_member = self.get_organization_team_member()
        if organization_member:
            return organization_member.is_organization_admin
        return False
