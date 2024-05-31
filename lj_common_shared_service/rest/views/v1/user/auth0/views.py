from __future__ import unicode_literals

__author__ = 'David Baum'

import json
import logging, requests

from auth0.v3 import Auth0Error
from auth0.v3 import management

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import ugettext_lazy as _

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from lj_common_shared_service.auth0.helper import get_auth0_client_access_token
from lj_common_shared_service.rest.mixins import LJRequestUserMixin
from lj_common_shared_service.utils.enums import LJOrganizationTeamMemberRoleEnum, OrganizationTeamMemberStatusEnum
from lj_common_shared_service.utils.utils import value_to_bool

from rest_framework import mixins, parsers, renderers, serializers, status, viewsets
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from lj_common_shared_service.authentication.models import LJOrganization, LJOrganizationTeamMember
from lj_common_shared_service.auth0.settings import AUTH0_SETTINGS, AUTH0_USER_META_ENV
from lj_common_shared_service.rest.permissions import IsAuthenticatedSuperUser, \
    IsAuthenticatedStaffUser, IsOrganizationAdminUser, HasOrganizationAuthenticated
from lj_common_shared_service.rest.serializers import LJUserModelSerializer, LJAuth0UserModelSerializer
from lj_common_shared_service.utils.logging.mixins import LoggingMixin

User = get_user_model()
logger = logging.getLogger(__name__)

AUTH0_DOMAIN = AUTH0_SETTINGS.get('AUTH0_DOMAIN')
AUTH0_KEY = AUTH0_SETTINGS.get('AUTH0_KEY')
AUTH0_SECRET = AUTH0_SETTINGS.get('AUTH0_SECRET')
AUTH0_AUDIENCE = AUTH0_SETTINGS.get('AUTH0_AUDIENCE')

available_team_member_roles = ", ".join(
    [
        "{} {} {}".format(role.value.key, _("which designates"), role.value.raw_value, ) for
        role in LJOrganizationTeamMemberRoleEnum
    ]
)

allowed_team_member_roles = [role.value.key for role in LJOrganizationTeamMemberRoleEnum]


class LJAuth0UserProfileViewSet(
    LoggingMixin,
    LJRequestUserMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    GenericAPIView
):
    permission_classes = [IsAuthenticated,
                          HasOrganizationAuthenticated | IsAuthenticatedSuperUser | IsAuthenticatedStaffUser]
    parser_classes = (parsers.FormParser, parsers.MultiPartParser,)
    renderer_classes = (renderers.JSONRenderer,)
    serializer_class = serializers.Serializer
    model = User

    def dispatch(self, *args, **kwargs):
        return super(LJAuth0UserProfileViewSet, self).dispatch(*args, **kwargs)

    @swagger_auto_schema(
        responses={
            204: openapi.Response("The team member has been successfully removed from the organization"),
            401: openapi.Response("The current authenticated user is not authenticated"),
            403: openapi.Response(
                "The current authenticated user is not an editor of the organization"
            ),
            404: openapi.Response("The user does not exist")
        },
        operation_id="Removes user from the organization",
        operation_description="Delete team member",
        operation_summary="Update Auth0 user",
        tags=['Auth0 user'],
        manual_parameters=[
            openapi.Parameter('auth0_user_id', openapi.IN_PATH,
                              description="The auth0 user ID of the user to remove from the organization",
                              type=openapi.TYPE_STRING, required=True),
            openapi.Parameter(settings.REST_FRAMEWORK_USER_ORGANIZATION_HEADER, openapi.IN_HEADER,
                              description="The user organization UUID",
                              type=openapi.TYPE_STRING, required=True),
        ]
    )
    def delete(self, request, auth0_user_id: str, *args, **kwargs) -> Response:
        organization = self.get_user_organization()

        if not self.has_edit_organization_permissions():
            return Response(status=status.HTTP_403_FORBIDDEN)

        try:
            user = self.model.objects.get(auth0_user_id=auth0_user_id)
            instance = LJOrganizationTeamMember.objects.get(
                user=user,
                organization=organization
            )
            self.perform_destroy(instance)
            user.validate_auth0_metadata(is_merge=True)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except (LJOrganizationTeamMember.DoesNotExist, self.model.DoesNotExist):
            return Response(status=status.HTTP_404_NOT_FOUND)
        except Auth0Error as ex:
            return Response(dict(error=ex.message), status=ex.status_code)

    @swagger_auto_schema(
        responses={
            200: openapi.Response("The Auth0 user has been successfully updated"),
            401: openapi.Response("The current authenticated user is not authenticated"),
            403: openapi.Response(
                "The current authenticated user is not admin or the provided user id does not belong to him"
            ),
            404: openapi.Response("The user does not exist"),
            409: openapi.Response("The user with such email address already exists")
        },
        operation_id="Update Auth0 user profile",
        operation_description="Updates Auth0 user profile",
        operation_summary="Update Auth0 user",
        tags=['Auth0 user'],
        manual_parameters=[
            openapi.Parameter('auth0_user_id', openapi.IN_PATH, description="The auth0 user ID of the user to update",
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
            openapi.Parameter('description', openapi.IN_FORM,
                              description="Auth0 user profile description",
                              type=openapi.TYPE_STRING, required=False),
            openapi.Parameter('is_public_contribution', openapi.IN_FORM,
                              description="Indicates whether the user contribution is public and visible for everybody",
                              type=openapi.TYPE_BOOLEAN, required=False),
            openapi.Parameter('company', openapi.IN_FORM,
                              description="Auth0 user hospital/facility/company",
                              type=openapi.TYPE_STRING, required=False),
            openapi.Parameter('pin_code', openapi.IN_FORM,
                              description="The user pin code",
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
    def put(self, request, auth0_user_id: str, *args, **kwargs) -> Response:
        data = dict((key, value) for (key, value) in request.data.items())
        current_user = request.user
        email = data.get('email')
        name = data.get('name')
        username = data.get('username')
        picture = data.get('picture')
        description = data.get('description')
        company = data.get('company')
        role = data.get('role')
        is_public = data.get('is_public')
        is_public_contribution = data.get('is_public_contribution')
        is_public = value_to_bool(is_public)
        is_public_contribution = value_to_bool(is_public_contribution)
        is_user_admin = self.is_user_admin()
        organization = self.get_user_organization()
        is_current_user_profile = current_user.auth0_user_id == auth0_user_id

        if not is_current_user_profile and not is_user_admin and not self.has_edit_organization_permissions():
            return Response(status=status.HTTP_403_FORBIDDEN)
        if role and self.has_edit_organization_permissions():
            if not LJOrganizationTeamMemberRoleEnum.get_type(str(role)):
                return Response(
                    dict(
                        status=[
                            _(f'Invalid parameter, allowed values: {allowed_team_member_roles}')
                        ]
                    ),
                    status=status.HTTP_400_BAD_REQUEST
                )

        try:
            access_token = get_auth0_client_access_token()
            if access_token:
                auth0_user = dict()
                auth0_users_manager = management.Users(domain=AUTH0_DOMAIN, token=access_token)
                try:
                    # Check if the user exists in the database
                    user = self.model.objects.get(auth0_user_id=auth0_user_id)
                    if email and user.email != email:
                        # Check if the other user exist with such email address in the Auth0 service
                        auth0_users = auth0_users_manager.list(q=f'email:"{email}"')
                        if auth0_users and auth0_users.get('users', []):
                            auth0_user = auth0_users.get('users')[0]
                            user_id = auth0_user.get('user_id')
                            if auth0_user_id != user_id:
                                return Response(status=status.HTTP_409_CONFLICT)
                            user.email = email
                    else:
                        auth0_user = auth0_users_manager.get(auth0_user_id)
                    user.username = username or user.username
                except self.model.DoesNotExist:
                    # Extracts the user from the Auth0 service
                    auth0_user = auth0_users_manager.get(auth0_user_id)
                    email = email or auth0_user.get('email')
                    username = username or auth0_user.get('username')

                    try:
                        # Check whether the user exists in the DB with such email address
                        user = self.model.objects.get(email=email)
                        user.auth0_user_id = auth0_user_id
                    except User.DoesNotExist:
                        raw_password = self.model.objects.make_random_password()
                        user = self.model.objects.create_user(email, raw_password)
                    user.username = username
                    user.email = email

                if is_user_admin or is_current_user_profile:
                    user.full_name = name or user.full_name
                    user.company = company
                    if data.get('is_public_contribution'):
                        user.is_public_contribution = is_public_contribution
                    if picture:
                        user.picture = picture
                    user.description = description or user.description
                if self.has_edit_organization_permissions():
                    if role and is_user_admin:
                        user.role = role
                user.save()

                user_metadata = auth0_user.get('user_metadata') or dict()
                if self.has_edit_organization_permissions():
                    if user_metadata.get(AUTH0_USER_META_ENV) and user_metadata.get(AUTH0_USER_META_ENV).get(
                            'organizations'):
                        organizations = user_metadata.get(AUTH0_USER_META_ENV).get('organizations')
                        user_role = LJOrganizationTeamMemberRoleEnum.get_type(str(role))
                        for item in organizations:
                            if item.get('organization_uuid') == str(organization.uuid):
                                if user_role == LJOrganizationTeamMemberRoleEnum.MEMBER:
                                    item.update(
                                        is_organization_editor=False,
                                        is_organization_admin=False
                                    )
                                elif user_role == LJOrganizationTeamMemberRoleEnum.EDITOR:
                                    item.update(
                                        is_organization_editor=True,
                                        is_organization_admin=False
                                    )
                                else:
                                    item.update(
                                        is_organization_editor=True,
                                        is_organization_admin=True
                                    )

                        user_metadata.get(AUTH0_USER_META_ENV).update(
                            organizations=organizations
                        )
                        if is_current_user_profile:
                            user_metadata.update(
                                is_public=is_public,
                                description=description or user_metadata.get('description'),
                                company=company,
                                is_public_contribution=is_public_contribution
                            )
                        user_data_update = dict(
                            user_metadata=user_metadata
                        )

                        auth0_user = auth0_users_manager.update(auth0_user_id, user_data_update)
                else:
                    user_metadata.update(
                        is_public=is_public,
                        description=description or user_metadata.get('description'),
                        company=company,
                        is_public_contribution=is_public_contribution
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
                    error=[_(f"An Auth0 error occurred while getting the Auth0 client access token")]
                ),
                status=status.HTTP_400_BAD_REQUEST
            )
        except Auth0Error as ex:
            return Response(dict(error=ex.message), status=ex.status_code)

        return Response(serializer.data, status=status.HTTP_200_OK)


class LJAuth0UserOrganizationInvitation(LoggingMixin, mixins.CreateModelMixin, GenericAPIView):
    serializer_class = serializers.Serializer
    parser_classes = (parsers.FormParser, parsers.MultiPartParser,)
    permission_classes = (IsAuthenticated,)

    def dispatch(self, *args, **kwargs):
        return super(LJAuth0UserOrganizationInvitation, self).dispatch(*args, **kwargs)

    @swagger_auto_schema(
        responses={
            201: openapi.Response("The user has been successfully invited to organization"),
            400: openapi.Response("The invitation was not provided or the user is not of Auth0 service"),
            401: openapi.Response("The user is unauthorized"),
            404: openapi.Response("The organization is not found"),
            409: openapi.Response("The user is already a team member of the organization")
        },
        operation_description="Auth0 user organization invite",
        operation_id="Invite Auth0 user",
        operation_summary="Invite Auth0 user",
        tags=['Auth0 user'],
        manual_parameters=[
            openapi.Parameter('invitation_code', openapi.IN_FORM,
                              description="The invitation code",
                              type=openapi.TYPE_STRING, required=True),
        ]
    )
    def post(self, request, *args, **kwargs) -> Response:
        current_user = request.user
        request_data = request.data.copy()

        if hasattr(current_user, 'auth0_user_id') and current_user.auth0_user_id:
            invitation_code = request_data.get('invitation_code')
            invitation_code = invitation_code.strip()
            try:
                authorization = request.headers.get('Authorization')

                if not authorization:
                    return Response(status=status.HTTP_401_UNAUTHORIZED)

                organization = LJOrganization.objects.get(invitation_code=invitation_code)

                user = User.objects.get(auth0_user_id=current_user.auth0_user_id)

                team_member, created_team_member = LJOrganizationTeamMember.objects.get_or_create(
                    user=user,
                    organization=organization
                )

                if not team_member and team_member.status == OrganizationTeamMemberStatusEnum.ACTIVE.value.key:
                    return Response(
                        data=dict(user_id=['User is already a team member of the organization']),
                        status=status.HTTP_409_CONFLICT
                    )
                team_member.status = OrganizationTeamMemberStatusEnum.ACTIVE.value.key
                team_member.save()

                team_members = LJOrganizationTeamMember.objects.select_related(
                    'organization'
                ).filter(user=user)

                organizations = [
                    dict(
                        organization=team_member.organization.name,
                        organization_uuid=str(team_member.organization.uuid),
                        is_organization_editor=team_member.is_organization_editor,
                        is_organization_admin=team_member.is_organization_admin,
                        is_organization_creator=team_member.is_organization_creator,
                        status=team_member.status
                    ) for team_member in team_members
                ]

                organization_data = dict(
                    organization=organization.name,
                    organization_uuid=str(organization.uuid),
                    organizations=organizations
                )
                payload = json.dumps(
                    dict(
                        user_metadata={AUTH0_USER_META_ENV: organization_data}
                    )
                )

                headers = {
                    'Authorization': authorization,
                    'Content-Type': "application/json"
                }

                auth0_user_patch_request = requests.patch(
                    f"https://{AUTH0_DOMAIN}/api/v2/users/{current_user.auth0_user_id}",
                    data=payload,
                    headers=headers,
                    timeout=10000
                )
                auth0_response_code = auth0_user_patch_request.status_code
                if auth0_response_code == status.HTTP_200_OK:
                    json_data = json.loads(auth0_user_patch_request.content)
                    return Response(json_data, status=auth0_user_patch_request.status_code)

                return Response(
                    data=dict(error=auth0_user_patch_request.content),
                    status=auth0_user_patch_request.status_code
                )
            except LJOrganization.DoesNotExist:
                return Response(
                    data=dict(invitation_code=['Enter valid invitation code']),
                    status=status.HTTP_404_NOT_FOUND
                )
        return Response(
            data=dict(user_id=['User is not an Auth0 user']),
            status=status.HTTP_400_BAD_REQUEST
        )


class LJAuth0UserManagementAPIView(
    LoggingMixin,
    LJRequestUserMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet
):
    permission_classes = [IsAuthenticated,
                          IsOrganizationAdminUser | IsAuthenticatedSuperUser | IsAuthenticatedStaffUser]
    parser_classes = (parsers.FormParser, parsers.MultiPartParser,)
    renderer_classes = (renderers.JSONRenderer,)
    serializer_class = LJAuth0UserModelSerializer
    model = User

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        kwargs['context'] = self.get_serializer_context()
        return serializer_class(*args, **kwargs)

    @swagger_auto_schema(
        responses={
            200: LJUserModelSerializer(many=True),
            400: openapi.Response(
                "Only user admin search in app_metadata and user_metadata."),
            403: openapi.Response(
                "The current authenticated user is not an organization admin, staff user or super admin"),
        },
        operation_description="Fetches all users from the Auth0 service",
        operation_summary="List Auth0 users",
        operation_id="List Auth0 users",
        tags=['Auth0 user'],
        manual_parameters=[
            openapi.Parameter(
                'q',
                openapi.IN_QUERY,
                description="Query in Lucene query string syntax. "
                            "Only fields in app_metadata, user_metadata or "
                            "the normalized user profile are searchable. "
                            "Available parameters are described in the Auth0 "
                            "documentation https://auth0.com/docs/manage-users/user-search/user-search-query-syntax",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'sort',
                openapi.IN_QUERY,
                description="The field to use for sorting. "
                            "1 == ascending and -1 == descending. (e.g: email:1) "
                            "When not set, the default value is up to the server.",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(settings.REST_FRAMEWORK_USER_ORGANIZATION_HEADER, openapi.IN_HEADER,
                              description="The user organization UUID",
                              type=openapi.TYPE_STRING, required=False),
        ]
    )
    def list(self, request) -> Response:
        query_params = request.query_params
        limit = query_params.get('limit', 25)
        offset = query_params.get('offset', 0)
        query = query_params.get('q', None)
        sort = query_params.get('sort', None)

        organization = self.get_user_organization()
        is_user_admin = self.is_user_admin()

        if not self.has_edit_organization_permissions() and not is_user_admin:
            return Response(status=status.HTTP_403_FORBIDDEN)

        try:
            if not is_user_admin and query and ('app_metadata' in query or 'user_metadata' in query):
                return Response(
                    data={"query": "Only user admin search in app_metadata and user_metadata."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            access_token = get_auth0_client_access_token()

            if access_token:
                auth0_users_manager = management.Users(domain=AUTH0_DOMAIN, token=access_token)
                if self.has_admin_organization_permissions():
                    if query:
                        query = f'{query} AND user_metadata.{AUTH0_USER_META_ENV}.organizations.organization_uuid:"{organization.uuid}"'
                    elif organization:
                        query = f'user_metadata.{AUTH0_USER_META_ENV}.organizations.organization_uuid:"{organization.uuid}"'

                users = auth0_users_manager.list(
                    page=offset,
                    per_page=limit,
                    q=query,
                    sort=sort
                )
                return Response(users, status=status.HTTP_200_OK)
            return Response(
                dict(
                    error=[_(f"An Auth0 error occurred while getting the Auth0 client access token")]
                ),
                status=status.HTTP_400_BAD_REQUEST
            )
        except Auth0Error as ex:
            return Response(dict(error=ex.message), status=ex.status_code)

    @swagger_auto_schema(
        responses={
            201: openapi.Response("Returns status when the user was successfully created",
                                  LJUserModelSerializer(many=False)),
            400: openapi.Response(
                "Not all the body parameters were satisfied"),
            403: openapi.Response("The current authenticated user is not an admin"),
            409: openapi.Response(
                "The email address already belongs to the other user, please choose another one")
        },
        operation_description="Creates a user, if not an admin then will create the user in the current logged in user organization",
        operation_summary="Create user",
        operation_id="Create user",
        tags=['Auth0 user'],
        manual_parameters=[
            openapi.Parameter('email', openapi.IN_FORM, description="Email of the user",
                              type=openapi.TYPE_STRING, required=True),
            openapi.Parameter('is_active', openapi.IN_FORM, description="If the user is active",
                              type=openapi.TYPE_BOOLEAN, required=False),
            openapi.Parameter('is_staff', openapi.IN_FORM, description="If the user is part of the staff",
                              type=openapi.TYPE_BOOLEAN, required=False),
            openapi.Parameter('is_superuser', openapi.IN_FORM, description="If the user is superuser",
                              type=openapi.TYPE_BOOLEAN, required=False),
            openapi.Parameter('password', openapi.IN_FORM, description="The password of the user",
                              type=openapi.TYPE_STRING, required=True),
            openapi.Parameter('full_name', openapi.IN_FORM,
                              description="The full name of the user",
                              type=openapi.TYPE_STRING, required=True),
            openapi.Parameter('organization', openapi.IN_FORM,
                              description="The organization ID",
                              type=openapi.TYPE_INTEGER, required=False),
            openapi.Parameter('name', openapi.IN_FORM, description="The full name of the user",
                              type=openapi.TYPE_STRING, required=False),
            openapi.Parameter('username', openapi.IN_FORM, description="The username",
                              type=openapi.TYPE_STRING, required=False),
            openapi.Parameter('picture', openapi.IN_FORM, description="The user avatar",
                              type=openapi.TYPE_FILE, required=False),
            openapi.Parameter('is_public', openapi.IN_FORM,
                              description="Indicates whether the user profile is public",
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
            openapi.Parameter('is_organization_admin', openapi.IN_FORM,
                              description="Indicates whether the user is organization admin",
                              type=openapi.TYPE_BOOLEAN, required=False),
            openapi.Parameter('is_organization_editor', openapi.IN_FORM,
                              description="Indicates whether the user is organization editor",
                              type=openapi.TYPE_BOOLEAN, required=False),
            openapi.Parameter(settings.REST_FRAMEWORK_USER_ORGANIZATION_HEADER, openapi.IN_HEADER,
                              description="The user organization UUID",
                              type=openapi.TYPE_STRING, required=False),
        ]
    )
    def post(self, request, *args, **kwargs) -> Response:
        data = dict((key, value) for (key, value) in request.data.items())
        password = data.get('password')
        is_organization_admin = data.get('is_organization_admin')
        is_organization_editor = data.get('is_organization_editor')
        organization = self.get_user_organization()
        is_user_admin = self.is_user_admin()

        if not organization and not is_user_admin:
            return Response(status=status.HTTP_403_FORBIDDEN)

        if not is_user_admin:
            data.update(organization=organization.id)
            data.pop('is_staff', None)
            data.pop('is_superuser', None)
            data.pop('organization', None)
            data.pop('is_active', None)

        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            instance = serializer.save()
            instance.set_password(password)
            instance.save()

            team_member, team_member_created = LJOrganizationTeamMember.objects.get_or_create(
                organization=instance.organization,
                user=instance
            )
            if is_organization_admin:
                team_member.is_organization_admin = value_to_bool(is_organization_admin)
            if is_organization_editor:
                team_member.is_organization_editor = value_to_bool(is_organization_editor)
            team_member.save()

            auth0_client_access_token = get_auth0_client_access_token()
            auth0_domain = AUTH0_SETTINGS.get("AUTH0_DOMAIN")
            auth0_users_manager = management.Users(domain=auth0_domain, token=auth0_client_access_token)
            auth0_users_manager.create(
                dict(
                    emai=instance.email,
                    email_verified=False,
                    name=instance.full_name,
                    password=password,
                    nickname=''
                )
            )
            data = serializer.data

            headers = self.get_success_headers(data)
            return Response(data, status=status.HTTP_201_CREATED,
                            headers=headers)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
