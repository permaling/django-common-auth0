from __future__ import unicode_literals

__author__ = 'David Baum'

import datetime
import hashlib
import logging
from datetime import timedelta

import dateutil.parser
from auth0.v3 import Auth0Error, management
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import mixins, parsers, renderers, status, views, viewsets
from rest_framework.exceptions import NotFound
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from lj_common_shared_service.auth0.helper import get_auth0_client_access_token
from lj_common_shared_service.auth0.settings import AUTH0_SETTINGS
from lj_common_shared_service.authentication.models import LJOrganization, LJOrganizationTeamMember
from lj_common_shared_service.referrals.models import ReferralCode, ReferralNode
from lj_common_shared_service.rest.mixins import LJPaginatedListMixin, LJRequestUserMixin
from lj_common_shared_service.rest.paginators import LJSmallLimitOffsetPagination
from lj_common_shared_service.rest.permissions import (
    HasOrganizationAuthenticated,
    IsAuthenticatedStaffUser,
    IsAuthenticatedSuperUser
)
from lj_common_shared_service.rest.serializers import LJUserModelSerializer, ReferralNodeSerializer
from lj_common_shared_service.rest.views.errors import LJApiResponseErrors
from lj_common_shared_service.rest.views.v2.user.swagger import LJUserAutoSchema
from lj_common_shared_service.utils.enums import LJOrganizationTeamMemberRoleEnum
from lj_common_shared_service.utils.logging.mixins import LoggingMixin
from lj_common_shared_service.utils.utils import is_valid_uuid, value_to_bool

logger = logging.getLogger(__name__)
User = get_user_model()
AUTH0_DOMAIN = AUTH0_SETTINGS.get('AUTH0_DOMAIN')

available_team_member_roles = ", ".join(
    [
        "{} {} {}".format(role.value.key, _("which designates"), role.value.raw_value, ) for
        role in LJOrganizationTeamMemberRoleEnum
    ]
)

allowed_team_member_roles = [role.value.key for role in LJOrganizationTeamMemberRoleEnum]


class LJUserViewSet(
    LoggingMixin,
    LJPaginatedListMixin,
    LJRequestUserMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet
):
    permission_classes = [IsAuthenticated,
                          HasOrganizationAuthenticated | IsAuthenticatedSuperUser | IsAuthenticatedStaffUser]
    parser_classes = (parsers.FormParser, parsers.MultiPartParser,)
    renderer_classes = (renderers.JSONRenderer,)
    serializer_class = LJUserModelSerializer
    pagination_class = LJSmallLimitOffsetPagination
    model = User
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ('full_name', 'email', 'username',)
    ordering_fields = '__all__'
    ordering = ['-pk']
    swagger_schema = LJUserAutoSchema

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        kwargs['context'] = self.get_serializer_context()
        return serializer_class(*args, **kwargs)

    @swagger_auto_schema(
        responses={
            200: LJUserModelSerializer(many=True),
            401: openapi.Response("The current user is not authorized"),
            403: openapi.Response("The current authenticated user is not an admin or "
                                  "does not belong to any of the organization or is not an editor/admin of the organization"),
            404: openapi.Response(
                "Organization does not exists in case these parameters were provided"
            ),
        },
        operation_description="Fetches all users from the database",
        operation_summary="List users",
        tags=['Hub user'],
        manual_parameters=[
            openapi.Parameter('is_pagination', openapi.IN_QUERY,
                              description="Indicates whether to show all pagination data",
                              type=openapi.TYPE_BOOLEAN, required=False),
            openapi.Parameter('organization_uuid', openapi.IN_QUERY,
                              description="Filter the users by organization UUID by the admin user",
                              type=openapi.TYPE_STRING, required=False),
            openapi.Parameter(settings.REST_FRAMEWORK_USER_ORGANIZATION_HEADER, openapi.IN_HEADER,
                              description="The user organization UUID",
                              type=openapi.TYPE_STRING, required=False),
        ]
    )
    def list(self, request) -> Response:
        organization = self.get_user_organization()
        is_user_admin = self.is_user_admin()
        has_edit_organization_permissions = self.has_edit_organization_permissions()

        data = dict((key, value) for (key, value) in self.request.query_params.items())
        organization_uuid = data.get('organization_uuid')
        is_pagination = data.get('is_pagination')
        if is_pagination:
            is_pagination = value_to_bool(is_pagination)

        errors = dict()
        if organization_uuid and not is_valid_uuid(organization_uuid):
            errors.update(
                organization_uuid=[LJApiResponseErrors.WRONG_UUID_FORMAT.__str__()]
            )
        if len(errors.items()) > 0:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        if organization_uuid and not organization and self.is_user_admin():
            try:
                organization = LJOrganization.objects.get(uuid=organization_uuid)
            except LJOrganization.DoesNotExist:
                return Response(dict(
                    organization_uuid=_('The organization does not exist')
                ), status=status.HTTP_404_NOT_FOUND)

        query = Q()
        if is_user_admin or has_edit_organization_permissions:
            if organization:
                query = Q(organization_team_member__organization=organization)
        else:
            return Response(status=status.HTTP_403_FORBIDDEN)

        queryset = self.model.objects.prefetch_related(
            'organization_team_member'
        ).filter(query)
        queryset = super(LJUserViewSet, self).filter_queryset(queryset).distinct()
        page = self.paginate_queryset(queryset)
        queryset = page if page else queryset

        try:
            auth0_query_list = []
            for user in queryset:
                if user.auth0_user_id:
                    auth0_query_list.append(
                        f'email:"<%= "{user.email}" %>"'
                    )
            if auth0_query_list:
                auth0_access_token = get_auth0_client_access_token()
                auth0_domain = AUTH0_SETTINGS.get("AUTH0_DOMAIN")
                auth0_users_manager = management.Users(domain=auth0_domain, token=auth0_access_token)
                auth0_users_data = auth0_users_manager.list(q=' OR '.join(auth0_query_list))
                auth0_users = auth0_users_data.get('users') if auth0_users_data else []

                for auth0_user in auth0_users:
                    auth0_user_id = auth0_user.get('user_id')
                    for user in queryset:
                        if user.auth0_user_id == auth0_user_id:
                            last_login = auth0_user.get('last_login')
                            user.last_login = dateutil.parser.isoparse(last_login) if last_login else user.last_login
        except Auth0Error as e:
            logger.error(f'An error occurred while fetching the users from Auth0 service: {e}')

        serializer = self.get_serializer(queryset, many=True)
        return self.get_paginated_list_response(serializer.data, is_pagination)

    @swagger_auto_schema(
        responses={
            200: LJUserModelSerializer(many=False),
            400: openapi.Response("The UUID is not of the uuid format"),
            401: openapi.Response("The current user is not authorized"),
            403: openapi.Response("The current authenticated user is not an admin or "
                                  "does not belong to any of the organization or is not an editor/admin of the organization"),
            404: openapi.Response("The user is not found"),
        },
        operation_description="Get user by UUID",
        operation_summary="Get user",
        tags=['Hub user'],
        manual_parameters=[
            openapi.Parameter('uuid', openapi.IN_PATH, description="User uuid to fetch the user by",
                              type=openapi.TYPE_STRING, required=True),
            openapi.Parameter(settings.REST_FRAMEWORK_USER_ORGANIZATION_HEADER, openapi.IN_HEADER,
                              description="The user organization UUID",
                              type=openapi.TYPE_STRING, required=False),
        ]
    )
    def get(self, request, uuid: str) -> Response:
        organization = self.get_user_organization()
        is_user_admin = self.is_user_admin()
        has_edit_organization_permissions = self.has_edit_organization_permissions()

        if not is_valid_uuid(uuid):
            return Response(
                data={"uuid": LJApiResponseErrors.WRONG_UUID_FORMAT.__str__()},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            if organization or has_edit_organization_permissions:
                queryset = self.model.objects.prefetch_related(
                    'organization_team_member'
                ).get(
                    uuid=uuid,
                    organization_team_member__organization=organization
                )
            elif is_user_admin:
                queryset = self.model.objects.get(
                    uuid=uuid
                )
            else:
                return Response(status=status.HTTP_403_FORBIDDEN)
        except self.model.DoesNotExist:
            raise NotFound()

        serializer = self.get_serializer(queryset)
        data = serializer.data
        return Response(data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        responses={
            204: openapi.Response("The team member has been successfully removed from the organization/s"),
            400: openapi.Response("The UUID is not of the uuid format"),
            401: openapi.Response("The current user is not authenticated"),
            403: openapi.Response("The current authenticated user is not an admin or "
                                  "does not belong to any of the organization or is not an editor/admin of the organization"),
            404: openapi.Response("The user is not found"),
        },
        operation_id="Removes user from the organization",
        operation_description="Delete organization user",
        tags=['Hub user'],
        manual_parameters=[
            openapi.Parameter('uuid', openapi.IN_PATH,
                              description="User UUID to remove team member from the organization by",
                              type=openapi.TYPE_STRING, required=True),
            openapi.Parameter('organization_uuid', openapi.IN_FORM,
                              description="Organization UUID to delete user from, if not provided, the user will be deleted from all his organizations",
                              type=openapi.TYPE_STRING, required=True),
            openapi.Parameter(settings.REST_FRAMEWORK_USER_ORGANIZATION_HEADER, openapi.IN_HEADER,
                              description="The user organization UUID",
                              type=openapi.TYPE_STRING, required=False),
        ]
    )
    def delete(self, request, uuid: str) -> Response:
        data = dict((key, value) for (key, value) in request.data.items())
        organization_uuid = data.get('organization_uuid')

        organization = self.get_user_organization()
        is_user_admin = self.is_user_admin()
        has_edit_organization_permissions = self.has_edit_organization_permissions()

        if not is_valid_uuid(uuid):
            return Response(
                data={"uuid": LJApiResponseErrors.WRONG_UUID_FORMAT.__str__()},
                status=status.HTTP_400_BAD_REQUEST
            )
        if organization_uuid and not is_valid_uuid(organization_uuid):
            return Response(
                data={"organization_uuid": LJApiResponseErrors.WRONG_UUID_FORMAT.__str__()},
                status=status.HTTP_400_BAD_REQUEST
            )

        query = Q(uuid=uuid)
        if is_user_admin or has_edit_organization_permissions:
            if organization:
                query &= Q(organization_team_member__organization=organization)
            elif organization_uuid:
                query &= Q(organization_team_member__organization__uuid=organization_uuid)
        else:
            return Response(status=status.HTTP_403_FORBIDDEN)

        user = self.model.objects.prefetch_related(
            'organization_team_member'
        ).filter(query).first()

        if user:
            if organization_uuid and is_user_admin:
                team_member = LJOrganizationTeamMember.objects.get(
                    user=user,
                    organization__uuid=organization_uuid
                )
                self.perform_destroy(team_member)
            elif organization:
                team_member = LJOrganizationTeamMember.objects.get(
                    user=user,
                    organization=organization
                )
                self.perform_destroy(team_member)
            user.validate_auth0_metadata(is_merge=True)
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(status=status.HTTP_404_NOT_FOUND)

    @swagger_auto_schema(
        responses={
            200: openapi.Response("The user was successfully updated",
                                  LJUserModelSerializer(many=False)),
            400: openapi.Response(
                "Not all the body parameters were satisfied"),
            403: openapi.Response("The current authenticated user is not an admin"),
            404: openapi.Response(
                "The user is not found"),
            409: openapi.Response(
                "The email address already belongs to the other user, please choose another one")
        },
        operation_description="Update the user details",
        operation_summary="Update user",
        tags=['Hub user'],
        manual_parameters=[
            openapi.Parameter('uuid', openapi.IN_PATH, description="The ID of the user to be updated",
                              type=openapi.TYPE_STRING, required=True),
            openapi.Parameter('email', openapi.IN_FORM, description="The email of the user",
                              type=openapi.TYPE_STRING, required=False),
            openapi.Parameter('name', openapi.IN_FORM, description="The full name of the user",
                              type=openapi.TYPE_STRING, required=False),
            openapi.Parameter('username', openapi.IN_FORM, description="The username",
                              type=openapi.TYPE_STRING, required=False),
            openapi.Parameter('picture', openapi.IN_FORM, description="The user avatar",
                              type=openapi.TYPE_FILE, required=False),
            openapi.Parameter('is_public', openapi.IN_FORM,
                              description="Indicates whether the user profile is public",
                              type=openapi.TYPE_BOOLEAN, required=False),
            openapi.Parameter('is_superuser', openapi.IN_FORM,
                              description="Indicates whether the user should become super user, only super user can change this permission",
                              type=openapi.TYPE_BOOLEAN, required=False),
            openapi.Parameter('description', openapi.IN_FORM,
                              description="Auth0 user profile description",
                              type=openapi.TYPE_STRING, required=False),
            openapi.Parameter('is_public_contribution', openapi.IN_FORM,
                              description="Indicates whether the user contribution is public and visible for everybody",
                              type=openapi.TYPE_BOOLEAN, required=False),
            openapi.Parameter('company', openapi.IN_FORM,
                              description="Auth0 user hospital/facility/company",
                              type=openapi.TYPE_STRING, required=False),
            openapi.Parameter('organization_uuid', openapi.IN_FORM,
                              description="Updated the user by organization UUID by the admin user",
                              type=openapi.TYPE_STRING, required=False),
            openapi.Parameter(
                'role',
                openapi.IN_FORM,
                description=f"Team member organization roles - {available_team_member_roles}, "
                            f"only the organization admin, editor can change the role",
                type=openapi.TYPE_STRING,
                required=False,
                default=LJOrganizationTeamMemberRoleEnum.MEMBER.value.key,
                enum=allowed_team_member_roles
            ),
            openapi.Parameter(settings.REST_FRAMEWORK_USER_ORGANIZATION_HEADER, openapi.IN_HEADER,
                              description="The user organization UUID",
                              type=openapi.TYPE_STRING, required=False),
        ]
    )
    def put(self, request, uuid: str) -> Response:
        data = dict((key, value) for (key, value) in request.data.items())
        current_user = request.user
        email = data.get('email')
        name = data.get('name')
        username = data.get('username')
        picture = data.get('picture')
        description = data.get('description')
        company = data.get('company')
        role = data.get('role')
        organization_uuid = data.get('organization_uuid')
        is_public = data.get('is_public')
        is_public_contribution = data.get('is_public_contribution')
        is_superuser = data.get('is_superuser')
        is_public = value_to_bool(is_public)
        is_user_admin = self.is_user_admin()
        organization = self.get_user_organization()
        is_current_user_profile = str(current_user.uuid) == uuid

        if not is_current_user_profile and not is_user_admin and not self.has_edit_organization_permissions():
            return Response(status=status.HTTP_403_FORBIDDEN)

        errors = dict()
        if not is_valid_uuid(uuid):
            errors.update(uuid=LJApiResponseErrors.WRONG_UUID_FORMAT.__str__())
        if organization_uuid and not is_valid_uuid(organization_uuid):
            errors.update(organization_uuid=LJApiResponseErrors.WRONG_UUID_FORMAT.__str__())
        if role and (self.has_edit_organization_permissions() or is_user_admin):
            if not LJOrganizationTeamMemberRoleEnum.get_type(str(role)):
                errors.update(status=_(f'Invalid parameter, allowed values: {allowed_team_member_roles}'))
            else:
                role = LJOrganizationTeamMemberRoleEnum.get_type(str(role))
        if len(errors.items()) > 0:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        if organization_uuid and not organization:
            try:
                organization = LJOrganization.objects.get(uuid=organization_uuid)
            except LJOrganization.DoesNotExist:
                return Response(dict(
                    organization_uuid=[
                        _('The organization does not exist')
                    ]
                ), status=status.HTTP_404_NOT_FOUND)

        try:
            user = self.model.objects.get(uuid=uuid)

            if is_user_admin and is_superuser is not None:
                user.is_superuser = value_to_bool(is_superuser)
            if is_user_admin or is_current_user_profile:
                user.full_name = name or user.full_name
                user.company = company
                if data.get('is_public_contribution'):
                    user.is_public_contribution = value_to_bool(is_public_contribution)
                if picture:
                    user.picture = picture
                user.description = description or user.description
                user.username = username or user.username
            if (self.has_edit_organization_permissions() or is_user_admin) and role:
                organization_team_member = LJOrganizationTeamMember.objects.get(
                    organization=organization,
                    user=user
                )

                if role == LJOrganizationTeamMemberRoleEnum.MEMBER:
                    organization_team_member.is_organization_admin = False
                    organization_team_member.is_organization_editor = False
                elif role == LJOrganizationTeamMemberRoleEnum.EDITOR:
                    organization_team_member.is_organization_admin = False
                    organization_team_member.is_organization_editor = True
                elif role == LJOrganizationTeamMemberRoleEnum.ADMIN:
                    organization_team_member.is_organization_admin = True
                    organization_team_member.is_organization_editor = True
                organization_team_member.save()
            user.save()

            if (
                    self.has_edit_organization_permissions() or is_current_user_profile or is_user_admin) and user.auth0_user_id:
                user.validate_auth0_metadata(is_merge=True)
        except self.model.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        except LJOrganizationTeamMember.DoesNotExist:
            logger.error(
                f'The team member does not exist for organization {organization.uuid} and user email {user.email}')

        if user.auth0_user_id and (is_user_admin or is_current_user_profile):
            try:
                access_token = get_auth0_client_access_token()
                if access_token:
                    auth0_user = dict()
                    auth0_users_manager = management.Users(domain=AUTH0_DOMAIN, token=access_token)
                    try:
                        auth0_user_id = user.auth0_user_id
                        if auth0_user_id and email and user.email != email:
                            # Check if the other user exist with such email address in the Auth0 service
                            auth0_users = auth0_users_manager.list(q=f'email:"{email}"')
                            if auth0_users and auth0_users.get('users', []):
                                auth0_user = auth0_users.get('users')[0]
                                user_id = auth0_user.get('user_id')
                                if auth0_user_id != user_id:
                                    return Response(status=status.HTTP_409_CONFLICT)
                                user.email = email
                        elif auth0_user_id:
                            auth0_user = auth0_users_manager.get(auth0_user_id)
                    except self.model.DoesNotExist:
                        return Response(status=status.HTTP_404_NOT_FOUND)

                    user_metadata = auth0_user.get('user_metadata') or dict()
                    user_metadata.update(
                        is_public=is_public,
                        description=description or user_metadata.get('description'),
                        company=company,
                        is_public_contribution=value_to_bool(is_public_contribution)
                    )
                    user_data_update = dict(
                        email=email,
                        nickname=username,
                        name=name,
                        picture=user.picture.url if user.picture else None,
                        user_metadata=user_metadata
                    )

                    user_data_update = {k: v for k, v in user_data_update.items() if v is not None}
                    if len(user_data_update.items()) > 0:
                        auth0_user = auth0_users_manager.update(auth0_user_id, user_data_update)
                    return Response(auth0_user, status=status.HTTP_200_OK)
                return Response(
                    dict(
                        error=[_("An Auth0 error occurred while getting the Auth0 client access token")]
                    ),
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Auth0Error as ex:
                return Response(dict(error=ex.message), status=ex.status_code)

        serializer = self.get_serializer(user, many=False, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)


class DisableUserAPIView(LoggingMixin, views.APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        responses={
            200: openapi.Response("The user was successfully disabled", LJUserModelSerializer()),
            401: openapi.Response("The user is not authenticated"),
            404: openapi.Response("0Auth user not found"),
        },
        operation_description="Disable the user",
        operation_summary="Disable user",
        tags=['Hub user']
    )
    def post(self, request) -> Response:
        user = request.user

        token = get_auth0_client_access_token()
        auth0_domain = AUTH0_SETTINGS.get("AUTH0_DOMAIN")
        auth0_users_manager = management.Users(domain=auth0_domain, token=token)
        auth0_data = {"blocked": True}

        hash_key = settings.PSEUDONYMIZATION_HASH
        email_hash = hashlib.sha256((user.email + hash_key).encode("utf-8")).hexdigest()
        psedonimized_email = f"{email_hash}@email.pseudo"
        user.email = psedonimized_email

        if user.username:
            psedonimized_username = hashlib.sha256((user.username + hash_key).encode("utf-8")).hexdigest()
            user.username = psedonimized_username

        if user.full_name:
            psedonimized_full_name = hashlib.sha256((user.full_name + hash_key).encode("utf-8")).hexdigest()
            user.full_name = psedonimized_full_name
            auth0_data["name"] = psedonimized_full_name

        try:
            auth0_users_manager.update(user.auth0_user_id, auth0_data)
        except Auth0Error:
            return Response(dict(error=[_("0Auth user not found")]), status=status.HTTP_404_NOT_FOUND)

        user.is_active = False
        user.save()

        user_serializer = LJUserModelSerializer(user)
        return Response(user_serializer.data, status=status.HTTP_200_OK)


class ReferralCodeView(LoggingMixin, LJRequestUserMixin, views.APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (parsers.FormParser, parsers.MultiPartParser,)

    @swagger_auto_schema(
        responses={
            200: openapi.Response("The referral code found"),
            401: openapi.Response("The user is not authorized"),
            403: openapi.Response("The user is not admin or does not belong to any of the organization")
        },
        operation_description="Sends referral code to the user",
        operation_summary="Users referral code sending",
        manual_parameters=[
            openapi.Parameter(settings.REST_FRAMEWORK_USER_ORGANIZATION_HEADER, openapi.IN_HEADER,
                              description="The user organization UUID",
                              type=openapi.TYPE_STRING, required=True),
        ],
        tags=['Referral']
    )
    def get(self, request) -> Response:
        user = request.user

        referral_code = ReferralCode.objects.get_or_create(owner=user)[0]
        referral_count = referral_code.referralnode_set.all().count()
        today_utc_date = datetime.datetime.utcnow().date()
        referral_count_weekly = referral_code.referralnode_set.filter(
            date_created__gte=today_utc_date - timedelta(days=7)).count()

        return Response(
            data={"referral_code": referral_code.code, "joined_overall": referral_count,
                  "joined_weekly": referral_count_weekly},
            status=status.HTTP_200_OK
        )

    @swagger_auto_schema(
        responses={
            201: openapi.Response("Referral node created successfully"),
            400: openapi.Response("Not all the parameters were satisfied"),
            401: openapi.Response("The user is not authorized"),
            404: openapi.Response("Referral code not found"),
            409: openapi.Response("Referral node creation not allowed for existing users or duplicate referral node"),
        },
        operation_description="Creates a referral node for the user",
        manual_parameters=[
            openapi.Parameter('referral_code', openapi.IN_FORM, description="Referral code",
                              type=openapi.TYPE_STRING, required=True),
        ],
        operation_summary="Create referral node",
        tags=['Referral']
    )
    def post(self, request: Request) -> Response:
        user = request.user
        referral_code = request.data.get('referral_code')
        if not referral_code:
            return Response({"error": "Referral code is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            referral_code_obj = ReferralCode.objects.get(code=referral_code)
        except ReferralCode.DoesNotExist:
            logger.error("Referral code does not exist: %s", referral_code)
            return Response({"error": "Referral code does not exist"}, status=status.HTTP_404_NOT_FOUND)

        referral_node, created = ReferralNode.objects.get_or_create(referral_code=referral_code_obj, referred=user)
        if not created:
            return Response(
                dict(
                    error=_(
                        f"The user {user.email} has been already already invited using the referral code '{referral_code}'"
                    )
                ),
                status=status.HTTP_409_CONFLICT
            )

        serializer = ReferralNodeSerializer(referral_node)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
