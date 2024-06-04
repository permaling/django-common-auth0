from __future__ import unicode_literals

__author__ = 'David Baum'

import uuid

from django.conf import settings
from django.contrib.auth import get_user_model

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from lj_common_shared_service.utils.enums import LJOrganizationStatusEnum

from rest_condition import And, Or
from rest_framework import parsers, renderers, status, mixins, viewsets
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from lj_common_shared_service.rest.mixins import LJRequestUserMixin
from lj_common_shared_service.rest.permissions import HasOrganizationAuthenticated, IsPutRequest, IsPostRequest, \
    IsDeleteRequest, IsReadyOnlyRequest
from lj_common_shared_service.rest.serializers import LJOrganizationModelSerializer
from lj_common_shared_service.authentication.models import LJOrganization, LJOrganizationTeamMember
from lj_common_shared_service.utils.utils import is_valid_uuid

from lj_common_shared_service.utils.logging.mixins import LoggingMixin

User = get_user_model()


class LJOrganizationViewSet(
    LoggingMixin,
    LJRequestUserMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet
):
    permission_classes = [
        Or(
            And(IsPutRequest, IsAuthenticated, HasOrganizationAuthenticated, ),
            And(IsPostRequest, IsAuthenticated, ),
            And(IsDeleteRequest, IsAuthenticated, HasOrganizationAuthenticated, ),
            And(IsReadyOnlyRequest, IsAuthenticated, HasOrganizationAuthenticated, )
        )
    ]
    parser_classes = (parsers.FormParser, parsers.MultiPartParser,)
    renderer_classes = (renderers.JSONRenderer,)
    serializer_class = LJOrganizationModelSerializer
    model = LJOrganization

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        kwargs['context'] = self.get_serializer_context()
        return serializer_class(*args, **kwargs)

    @swagger_auto_schema(
        responses={
            200: LJOrganizationModelSerializer(many=False),
            401: openapi.Response("The user is not authenticated"),
            404: openapi.Response("The user does not belong to any of the organization"),
        },
        operation_description="Get organization of the user",
        operation_summary="Get user organization",
        tags=['Organization'],
        manual_parameters=[
            openapi.Parameter(settings.REST_FRAMEWORK_USER_ORGANIZATION_HEADER, openapi.IN_HEADER,
                              description="The user organization UUID",
                              type=openapi.TYPE_STRING, required=True),
        ]
    )
    def get(self, request) -> Response:
        organization = self.get_user_organization()
        if organization:
            serializer = self.get_serializer(organization)

            response_data = serializer.data
            return Response(response_data, status=status.HTTP_200_OK)
        return Response(status=status.HTTP_404_NOT_FOUND)

    @swagger_auto_schema(
        responses={
            204: openapi.Response("The organization was successfully deleted"),
            401: openapi.Response("The user is not authenticated"),
            404: openapi.Response("The user does not belong to any of the organization"),
            403: openapi.Response(
                "The user cannot delete the organization, "
                "because he is not an admin of the organization"
            )
        },
        operation_description="Delete user organization",
        operation_summary="Delete user organization",
        tags=['Organization'],
        manual_parameters=[
            openapi.Parameter(settings.REST_FRAMEWORK_USER_ORGANIZATION_HEADER, openapi.IN_HEADER,
                              description="The user organization UUID",
                              type=openapi.TYPE_STRING, required=True),
        ]
    )
    def delete(self, request) -> Response:
        organization = self.get_user_organization()

        if self.has_admin_organization_permissions():
            self.perform_destroy(organization)
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(status=status.HTTP_403_FORBIDDEN)

    @swagger_auto_schema(
        responses={
            201: openapi.Response(
                "Returns status when the organization was successfully created",
                LJOrganizationModelSerializer(many=False)
            ),
            400: openapi.Response(
                "Not all the body parameters were satisfied"
            ),
            401: openapi.Response("The user is not authenticated"),
            403: openapi.Response(
                "The user cannot create the organization, because he is not an admin of the organization"
            ),
        },
        operation_description="Create organization",
        operation_summary="Create user organization",
        tags=['Organization'],
        manual_parameters=[
            openapi.Parameter('name', openapi.IN_FORM, description="Name of the organization",
                              type=openapi.TYPE_STRING, required=True),
            openapi.Parameter('invitation_code', openapi.IN_FORM, description="Invitation code to the organization",
                              type=openapi.TYPE_STRING, required=False),
            openapi.Parameter('address', openapi.IN_FORM, description="Address of the organization",
                              type=openapi.TYPE_STRING, required=False),
            openapi.Parameter('team_name', openapi.IN_FORM, description="Team name of the organization",
                              type=openapi.TYPE_STRING, required=False),
            openapi.Parameter('company', openapi.IN_FORM,
                              description="Company/Hospital/Facility name of the organization",
                              type=openapi.TYPE_STRING, required=False),
            openapi.Parameter('photo', openapi.IN_FORM, description="Logo of the organization",
                              type=openapi.TYPE_FILE, required=False),
            openapi.Parameter(settings.REST_FRAMEWORK_USER_ORGANIZATION_HEADER, openapi.IN_HEADER,
                              description="The user organization UUID",
                              type=openapi.TYPE_STRING, required=False),
        ]
    )
    def post(self, request, *args, **kwargs) -> Response:
        organization = self.get_user_organization()
        if (organization and self.has_admin_organization_permissions()) or not organization:
            current_user = request.user

            data = dict((key, value) for (key, value) in request.data.items())
            invitation_code = data.get('invitation_code', str(uuid.uuid4()))
            data.update(user=current_user.pk, invitation_code=invitation_code)

            if not organization:
                data.update(status=LJOrganizationStatusEnum.ACTIVE.value.key)
            serializer = self.get_serializer(data=data)
            if serializer.is_valid():
                instance = serializer.save()
                LJOrganizationTeamMember(
                    user=current_user,
                    organization=instance,
                    is_organization_admin=True,
                    is_organization_editor=True
                ).save()
                response_data = serializer.data

                headers = self.get_success_headers(response_data)
                return Response(response_data, status=status.HTTP_201_CREATED,
                                headers=headers)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_403_FORBIDDEN)

    @swagger_auto_schema(
        responses={
            200: openapi.Response(
                "The organization was successfully updated",
                LJOrganizationModelSerializer(many=False)
            ),
            400: openapi.Response(
                "Not all the body parameters were satisfied"
            ),
            401: openapi.Response("The user is not authenticated"),
            403: openapi.Response(
                "The user cannot update the organization, because he is not an admin of the organization"
            ),
            404: openapi.Response(
                "The organization is not found"
            ),
        },
        operation_description="Update the organization details",
        operation_summary="Update user organization",
        tags=['Organization'],
        manual_parameters=[
            openapi.Parameter('name', openapi.IN_FORM, description="Name of the organization",
                              type=openapi.TYPE_STRING, required=True),
            openapi.Parameter('invitation_code', openapi.IN_FORM, description="Invitation code to the organization",
                              type=openapi.TYPE_STRING, required=False),
            openapi.Parameter('address', openapi.IN_FORM, description="Address of the organization",
                              type=openapi.TYPE_STRING, required=False),
            openapi.Parameter('company', openapi.IN_FORM,
                              description="Company/Hospital/Facility name of the organization",
                              type=openapi.TYPE_STRING, required=False),
            openapi.Parameter('team_name', openapi.IN_FORM, description="Team name of the organization",
                              type=openapi.TYPE_STRING, required=False),
            openapi.Parameter('photo', openapi.IN_FORM, description="Logo of the organization",
                              type=openapi.TYPE_FILE, required=False),
            openapi.Parameter(settings.REST_FRAMEWORK_USER_ORGANIZATION_HEADER, openapi.IN_HEADER,
                              description="The user organization UUID",
                              type=openapi.TYPE_STRING, required=True),
        ]
    )
    def put(self, request) -> Response:
        organization = self.get_user_organization()
        data = dict((key, value) for (key, value) in request.data.items())

        if self.has_admin_organization_permissions():
            serializer = self.get_serializer(organization, data=data)
            if serializer.is_valid():
                serializer.save()
                headers = self.get_success_headers(serializer.data)

                response_data = serializer.data
                return Response(response_data, status=status.HTTP_200_OK,
                                headers=headers)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_403_FORBIDDEN)


class LJSimpleOrganizationViewSet(LoggingMixin, APIView):
    throttle_classes = ()
    permission_classes = (AllowAny,)
    parser_classes = ()
    renderer_classes = (renderers.JSONRenderer,)
    serializer_class = LJOrganizationModelSerializer
    model = LJOrganization

    @swagger_auto_schema(
        responses={
            200: LJOrganizationModelSerializer(many=False),
            400: openapi.Response("Returns the JSON of the relevant errors"),
            404: openapi.Response("Organization is not found")
        },
        operation_id="user_organization_api",
        operation_description="Get organization of the user by UUID",
        operation_summary="Get user organization",
        tags=['Organization'],
        manual_parameters=[
            openapi.Parameter('organization_uuid', openapi.IN_PATH, description="The uuid of the organization",
                              type=openapi.TYPE_STRING, required=True),
        ]
    )
    def get(self, request, organization_uuid: str) -> Response:
        if not is_valid_uuid(organization_uuid):
            return Response(
                data={"organization_uuid": "The provided UUID is not of the UUID format"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            organization = self.model.objects.get(uuid=organization_uuid)
        except self.model.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = self.serializer_class(organization)

        return Response(serializer.data, status=status.HTTP_200_OK)
