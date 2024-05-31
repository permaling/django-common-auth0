from __future__ import unicode_literals

from lj_common_shared_service.utils.enums import LJOrganizationApplicationEnum, LJOrganizationStatusEnum, \
    OrganizationTeamMemberStatusEnum
from rest_framework import permissions


class IsAuthenticatedStaffUser(permissions.BasePermission):

    def has_permission(self, request, view):
        return request.user.is_staff


class IsAuthenticatedSuperUser(permissions.BasePermission):

    def has_permission(self, request, view):
        return request.user.is_superuser


class IsReadyOnlyRequest(permissions.BasePermission):
    """
    'GET', 'HEAD', 'OPTIONS' requests
    """

    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS


class IsPostRequest(permissions.BasePermission):

    def has_permission(self, request, view):
        return request.method == "POST"


class IsPatchRequest(permissions.BasePermission):

    def has_permission(self, request, view):
        return request.method == "PATCH"


class IsDeleteRequest(permissions.BasePermission):

    def has_permission(self, request, view):
        return request.method == "DELETE"


class IsPutRequest(permissions.BasePermission):

    def has_permission(self, request, view):
        return request.method == "PUT"


class IsOrganizationActive(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.user and request.user.is_authenticated:
            organization_member = getattr(request, 'organization_member', None)
            if (
                    organization_member and
                    organization_member.organization and
                    organization_member.organization.status == LJOrganizationStatusEnum.ACTIVE.value.key
            ):
                return True
        return False


class IsOrganizationTeamMemberActive(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.user and request.user.is_authenticated:
            organization_member = getattr(request, 'organization_member', None)
            if organization_member.status == OrganizationTeamMemberStatusEnum.ACTIVE.value.key:
                return True
        return False


class HasOrganizationAuthenticated(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.user and request.user.is_authenticated:
            organization_member = getattr(request, 'organization_member', None)
            if organization_member:
                return True
        return False


class HasOrganizationSIDApplicationPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.user and request.user.is_authenticated:
            organization_member = getattr(request, 'organization_member', None)
            if organization_member:
                application_name = LJOrganizationApplicationEnum.SID.value.key
                application_permission = organization_member.organization.organization_application_permission.filter(
                    application=application_name
                ).first()
                return True if application_permission else False
        return False


class HasOrganizationEZTApplicationPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.user and request.user.is_authenticated:
            organization_member = getattr(request, 'organization_member', None)
            if organization_member:
                application_name = LJOrganizationApplicationEnum.EZT.value.key
                application_permission = organization_member.organization.organization_application_permission.filter(
                    application=application_name
                ).first()
                return True if application_permission else False
        return False


class HasOrganizationAIDApplicationPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.user and request.user.is_authenticated:
            organization_member = getattr(request, 'organization_member', None)
            if organization_member:
                application_name = LJOrganizationApplicationEnum.AID.value.key
                application_permission = organization_member.organization.organization_application_permission.filter(
                    application=application_name
                ).first()
                return True if application_permission else False
        return False


class IsOrganizationAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        current_user = request.user
        if current_user and current_user.is_authenticated:
            organization_member = getattr(request, 'organization_member', None)
            return organization_member and organization_member.is_organization_admin
        return False


class IsOrganizationEditorUser(permissions.BasePermission):
    def has_permission(self, request, view):
        current_user = request.user
        if current_user and current_user.is_authenticated:
            organization_member = getattr(request, 'organization_member', None)
            return organization_member and organization_member.is_organization_editor
        return False


class IsOrganizationCreatorUser(permissions.BasePermission):
    def has_permission(self, request, view):
        current_user = request.user
        if current_user and current_user.is_authenticated:
            organization_member = getattr(request, 'organization_member', None)
            return organization_member and organization_member.is_organization_creator
        return False
