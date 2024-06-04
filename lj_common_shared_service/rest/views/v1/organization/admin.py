from __future__ import unicode_literals

__author__ = 'David Baum'

from django.contrib.auth import get_user_model
from django.db.models import Q

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from rest_framework import parsers, renderers, status, mixins, viewsets
from rest_framework.exceptions import NotFound
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from lj_common_shared_service.rest.mixins import LJPaginatedListMixin
from lj_common_shared_service.rest.paginators import LJSmallLimitOffsetPagination
from lj_common_shared_service.rest.serializers import LJOrganizationModelSerializer, LJUserModelSerializer
from lj_common_shared_service.rest.permissions import IsPutRequest, IsAuthenticatedSuperUser, IsAuthenticatedStaffUser
from lj_common_shared_service.authentication.models import LJOrganization
from lj_common_shared_service.utils.utils import value_to_bool

User = get_user_model()


class LJOrganizationAdminViewSet(
    LJPaginatedListMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet
):
    permission_classes = [IsAuthenticated, IsAuthenticatedSuperUser | IsAuthenticatedStaffUser]
    parser_classes = (parsers.FormParser, parsers.MultiPartParser,)
    renderer_classes = (renderers.JSONRenderer,)
    serializer_class = LJOrganizationModelSerializer
    pagination_class = LJSmallLimitOffsetPagination
    model = LJOrganization
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ('name',)
    ordering_fields = '__all__'
    ordering = ['-pk']

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        kwargs['context'] = self.get_serializer_context()
        return serializer_class(*args, **kwargs)

    def get_queryset(self):
        current_user = self.request.user
        data = dict((key, value) for (key, value) in self.request.query_params.items())
        is_pagination = data.get('is_pagination')

        if is_pagination:
            is_pagination = value_to_bool(is_pagination)

        query = Q()
        if not current_user.is_superuser and not current_user.is_staff:
            if not current_user.organization:
                return self.get_paginated_list_response([], is_pagination)
            query = Q(id=current_user.organization.id)

        queryset = self.model.objects.filter(query).order_by('-pk')
        queryset = super(LJOrganizationAdminViewSet, self).filter_queryset(queryset).distinct()
        return queryset

    @swagger_auto_schema(
        responses={
            200: LJOrganizationModelSerializer(many=True),
            401: openapi.Response("The user admin is not authenticated"),
            403: openapi.Response("The current authenticated user is not an admin")
        },
        operation_description="Fetches all organizations from the database",
        operation_summary="List organizations",
        tags=['Admin organization'],
        manual_parameters=[
            openapi.Parameter('is_pagination', openapi.IN_QUERY,
                              description="Indicates whether to show all pagination data",
                              type=openapi.TYPE_BOOLEAN, required=False)
        ]
    )
    def list(self, request) -> Response:
        data = dict((key, value) for (key, value) in request.query_params.items())
        is_pagination = data.get('is_pagination')
        if is_pagination:
            is_pagination = value_to_bool(is_pagination)

        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
        else:
            serializer = self.get_serializer(queryset, many=True)

        return self.get_paginated_list_response(serializer.data, is_pagination)

    @swagger_auto_schema(
        responses={
            200: LJOrganizationModelSerializer(many=False),
            401: openapi.Response("The user admin is not authenticated"),
            403: openapi.Response("The current authenticated user is not an admin"),
            404: openapi.Response("The organization is not found")
        },
        operation_description="Get organization by ID",
        operation_summary="Get organization",
        tags=['Admin organization'],
        manual_parameters=[
            openapi.Parameter('organization_id', openapi.IN_PATH,
                              description="Organization ID to fetch the organization by",
                              type=openapi.TYPE_INTEGER, required=True)
        ]
    )
    def get(self, request, organization_id: int) -> Response:
        current_user = request.user
        try:
            if not current_user.is_superuser and not current_user.is_staff:
                if current_user.organization and current_user.organization.id != organization_id:
                    return Response(status=status.HTTP_403_FORBIDDEN)
            queryset = self.model.objects.get(
                id=organization_id
            )

        except self.model.DoesNotExist:
            raise NotFound()

        serializer = self.get_serializer(queryset)

        users = []
        for user in queryset.organization_user.all():
            users.append(LJUserModelSerializer(user).data)
        response_data = serializer.data
        response_data.update(users=users)

        return Response(response_data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        responses={
            204: openapi.Response("The organization was successfully deleted"),
            401: openapi.Response("The user is not authenticated"),
            403: openapi.Response("The current authenticated user is not an admin"),
            404: openapi.Response("The organization is not found")
        },
        operation_description="Delete organization by ID",
        operation_summary="Delete organization",
        tags=['Admin organization'],
        manual_parameters=[
            openapi.Parameter('organization_id', openapi.IN_PATH, description="Organization ID to delete",
                              type=openapi.TYPE_INTEGER, required=True)
        ]
    )
    def delete(self, request, organization_id: int) -> Response:
        try:
            instance = self.model.objects.get(pk=organization_id)
            self.perform_destroy(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except self.model.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @swagger_auto_schema(
        responses={
            201: openapi.Response("Returns status when the organization was successfully created",
                                  LJOrganizationModelSerializer(many=False)),
            400: openapi.Response(
                "Not all the body parameters were satisfied"),
            401: openapi.Response("The user is not authenticated"),
            403: openapi.Response("The current authenticated user is not an admin")
        },
        operation_description="Create organization",
        operation_summary="Create organization",
        tags=['Admin organization'],
        manual_parameters=[
            openapi.Parameter('name', openapi.IN_FORM, description="Name of the organization",
                              type=openapi.TYPE_STRING, required=True),
            openapi.Parameter('invitation_code', openapi.IN_FORM, description="Invitation code to the organization",
                              type=openapi.TYPE_STRING, required=False),
            openapi.Parameter('photo', openapi.IN_FORM, description="Logo of the organization",
                              type=openapi.TYPE_FILE, required=False),
        ]
    )
    def post(self, request, *args, **kwargs) -> Response:
        data = dict((key, value) for (key, value) in request.data.items())

        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            instance = serializer.save()
            users = []
            for user in instance.organization_user.all():
                users.append(LJUserModelSerializer(user).data)
            response_data = serializer.data
            response_data.update(users=users)

            headers = self.get_success_headers(response_data)
            return Response(response_data, status=status.HTTP_201_CREATED,
                            headers=headers)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        responses={
            200: openapi.Response("The organization was successfully updated",
                                  LJOrganizationModelSerializer(many=False)),
            400: openapi.Response(
                "Not all the body parameters were satisfied"),
            401: openapi.Response("The user is not authenticated"),
            403: openapi.Response("The current authenticated user is not an admin"),
            404: openapi.Response(
                "The organization is not found"),
        },
        operation_description="Update the organization details",
        operation_summary="Update organization",
        tags=['Admin organization'],
        manual_parameters=[
            openapi.Parameter('organization_id', openapi.IN_PATH,
                              description="The ID of the organization to be updated",
                              type=openapi.TYPE_INTEGER, required=True),
            openapi.Parameter('name', openapi.IN_FORM, description="Name of the organization",
                              type=openapi.TYPE_STRING, required=True),
            openapi.Parameter('invitation_code', openapi.IN_FORM, description="Invitation code to the organization",
                              type=openapi.TYPE_STRING, required=False),
            openapi.Parameter('photo', openapi.IN_FORM, description="Logo of the organization",
                              type=openapi.TYPE_FILE, required=False),
        ]
    )
    def put(self, request, organization_id: int) -> Response:
        data = dict((key, value) for (key, value) in request.data.items())
        current_user = request.user

        try:
            instance = self.model.objects.get(pk=organization_id)

            serializer = self.get_serializer(instance, data=data)
            if serializer.is_valid():
                serializer.save()
                headers = self.get_success_headers(serializer.data)

                users = []
                for user in instance.organization_user.all():
                    users.append(LJUserModelSerializer(user).data)
                response_data = serializer.data
                response_data.update(users=users)

                return Response(response_data, status=status.HTTP_200_OK,
                                headers=headers)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except self.model.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
