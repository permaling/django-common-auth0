from __future__ import unicode_literals

__author__ = 'David Baum'

import json, logging
from requests.structures import CaseInsensitiveDict

from django.conf import settings
from django.contrib.auth import get_user
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.utils.encoding import force_text
from django.utils.deprecation import MiddlewareMixin
from django.utils.functional import SimpleLazyObject
from django.utils.module_loading import import_string
from django.utils.translation import ugettext_lazy as _

from lj_common_shared_service.authentication.models import LJOrganizationTeamMember
from lj_common_shared_service.utils.enums import OrganizationTeamMemberStatusEnum
from lj_common_shared_service.utils.utils import is_valid_uuid

logger = logging.getLogger(__name__)

REST_FRAMEWORK_USER_ORGANIZATION_HEADER = getattr(
    settings,
    'REST_FRAMEWORK_USER_ORGANIZATION_HEADER',
    'LJ-User-Organization'
)
DEFAULT_AUTHENTICATION_CLASSES = getattr(
    settings,
    'REST_FRAMEWORK',
).get('DEFAULT_AUTHENTICATION_CLASSES', [])


class LJAuthUserOrganizationMiddleware(MiddlewareMixin):
    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def get_user(request):
        user = get_user(request)
        if user.is_authenticated:
            return user
        failed_authentication_backends = []
        for default_authentication_class in DEFAULT_AUTHENTICATION_CLASSES:
            authentication_class = import_string(default_authentication_class)
            try:
                user, token = authentication_class().authenticate(request)
                if user.is_authenticated:
                    return user
            except Exception:
                failed_authentication_backends.append(default_authentication_class)
                continue
        if failed_authentication_backends:
            logger.debug(f"Non matched authentication backends for the user {failed_authentication_backends}")
        return user

    def _activate_invited_team_member(self, team_member: LJOrganizationTeamMember) -> LJOrganizationTeamMember:
        if team_member and team_member.status == OrganizationTeamMemberStatusEnum.INVITED.value.key:
            team_member.status = OrganizationTeamMemberStatusEnum.ACTIVE.value.key
            team_member.save()
        return team_member

    def __call__(self, request):
        request.user = SimpleLazyObject(lambda: self.__class__.get_user(request))
        request_headers = CaseInsensitiveDict(request.headers)
        if request_headers.get(REST_FRAMEWORK_USER_ORGANIZATION_HEADER):
            if request.user and request.user.is_authenticated:
                organization_uuid = request_headers.get(REST_FRAMEWORK_USER_ORGANIZATION_HEADER)
                if is_valid_uuid(organization_uuid):
                    try:
                        organization_member = LJOrganizationTeamMember.objects.prefetch_related(
                            'user',
                            'organization',
                            'organization__organization_application_permission',
                        ).get(
                            user=request.user,
                            organization__uuid=organization_uuid
                        )
                        request.organization_member = self._activate_invited_team_member(organization_member)
                    except LJOrganizationTeamMember.DoesNotExist:
                        errors = dict()
                        errors[REST_FRAMEWORK_USER_ORGANIZATION_HEADER] = [
                            force_text(_("The user is not part of the team for the provided organization header."))
                        ]
                        return HttpResponseForbidden(
                            json.dumps(errors),
                            content_type='application/json'
                        )
                else:
                    errors = dict()
                    errors[REST_FRAMEWORK_USER_ORGANIZATION_HEADER] = [
                        force_text(_("The provided header UUID is not of the UUID format."))
                    ]
                    return HttpResponseBadRequest(
                        json.dumps(errors),
                        content_type='application/json'
                    )
        response = self.get_response(request)
        return response
