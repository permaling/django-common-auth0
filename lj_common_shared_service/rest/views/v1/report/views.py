from __future__ import unicode_literals

__author__ = 'Soren Harner'

import logging, datetime

from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from google.cloud import vision

from rest_framework import parsers, renderers, status, mixins, viewsets
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from lj_common_shared_service.core.models import LJPhotoReport
from lj_common_shared_service.rest.views.v1.report.swagger import LJPhotoReportViewSetAutoSchema
from lj_common_shared_service.utils.enums import LJDeviceTypeEnum
from lj_common_shared_service.utils.image import LJImageUtils
from lj_common_shared_service.rest.permissions import HasOrganizationAuthenticated, \
    IsAuthenticatedSuperUser, IsAuthenticatedStaffUser
from lj_common_shared_service.rest.serializers import LJPhotoReportModelSerializer
from lj_common_shared_service.utils.logging.mixins import LoggingMixin

logger = logging.getLogger(__name__)

photo_report_device_types = ", ".join(
    [
        "{} {} {}".format(device_type.value.key, _("which designates"), device_type.value.raw_value, ) for
        device_type in LJDeviceTypeEnum
    ]
)


class LJPhotoReportViewSet(
    LoggingMixin,
    mixins.DestroyModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet
):
    permission_classes = [IsAuthenticated,
                          HasOrganizationAuthenticated | IsAuthenticatedSuperUser | IsAuthenticatedStaffUser]
    parser_classes = (parsers.FormParser, parsers.MultiPartParser,)
    renderer_classes = (renderers.JSONRenderer,)
    serializer_class = LJPhotoReportModelSerializer
    model = LJPhotoReport
    swagger_schema = LJPhotoReportViewSetAutoSchema
    queryset = LJPhotoReport.objects.all()
    lookup_field = "uuid"

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        kwargs['context'] = self.get_serializer_context()
        return serializer_class(*args, **kwargs)

    @swagger_auto_schema(
        responses={
            200: openapi.Response("The photo report was successfully created."),
            400: openapi.Response(
                "Not all the body parameters were satisfied; see required parameters"),
            401: openapi.Response(
                "The user is not authorized"),
            403: openapi.Response(
                "The user does not have the permission for the photo report"),
        },
        operation_description="Create photo report with output results",
        operation_summary="Create photo report",
        tags=['Photo report'],
        manual_parameters=[
            openapi.Parameter('name', openapi.IN_FORM,
                              description="The photo report name",
                              type=openapi.TYPE_STRING, required=True),
            openapi.Parameter('output', openapi.IN_FORM,
                              description="The photo report output",
                              type=openapi.TYPE_STRING, required=True),
            openapi.Parameter(
                'device_type',
                openapi.IN_FORM,
                description=f"Photo report device type - {LJDeviceTypeEnum.drf_description()}",
                type=openapi.TYPE_STRING,
                required=True,
                default=LJDeviceTypeEnum.WEB.value.key,
                enum=[device_type.value.key for device_type in LJDeviceTypeEnum]
            ),
            openapi.Parameter(settings.REST_FRAMEWORK_USER_ORGANIZATION_HEADER, openapi.IN_HEADER,
                              description="The user organization UUID",
                              type=openapi.TYPE_STRING, required=True),
        ]
    )
    def post(self, request: Request) -> Response:
        data = dict((key, value) for (key, value) in request.data.items())
        data.update(user=request.user)
        serializer = self.get_serializer(
            data=data,
            many=False,
            context=self.get_serializer_context()
        )
        if not serializer.is_valid(raise_exception=False):
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        self.perform_create(serializer)
        response_data = serializer.data
        return Response(response_data, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(
        responses={
            200: openapi.Response("The photo report was successfully updated."),
            400: openapi.Response(
                "Not all the body parameters were satisfied; see required parameters"),
            401: openapi.Response(
                "The user is not authorized"),
            403: openapi.Response(
                "The user does not have the permission for the photo report"),
            404: openapi.Response(
                "The photo report is not found")
        },
        operation_description="Photo report voting whether it contains correct or wrong results",
        operation_summary="Photo report vote",
        tags=['Photo report'],
        manual_parameters=[
            openapi.Parameter('uuid', openapi.IN_PATH,
                              description="The uuid of the photo report to vote for",
                              type=openapi.TYPE_STRING, required=True),
            openapi.Parameter('is_result_correct', openapi.IN_FORM,
                              description="The photo report correctness flag",
                              type=openapi.TYPE_INTEGER, required=True,
                              enum=[0, 1]),
            openapi.Parameter(settings.REST_FRAMEWORK_USER_ORGANIZATION_HEADER, openapi.IN_HEADER,
                              description="The user organization UUID",
                              type=openapi.TYPE_STRING, required=True),
        ]
    )
    def put(self, request: Request, uuid: str) -> Response:
        data = dict((key, value) for (key, value) in request.data.items())
        data.update(
            user=request.user,
            uuid=uuid,
        )

        serializer = self.get_serializer(
            instance=self.get_object(),
            data=data,
            many=False,
            context=self.get_serializer_context()
        )
        if not serializer.is_valid(raise_exception=False):
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        self.perform_update(serializer)
        response_data = serializer.data
        return Response(response_data, status=status.HTTP_200_OK)


class LJPhotoReportTextDetectionViewSet(LoggingMixin, APIView):
    permission_classes = (AllowAny,)
    parser_classes = (parsers.FormParser, parsers.MultiPartParser,)

    @swagger_auto_schema(
        responses={
            200: openapi.Response("The image has been successfully resolved"),
            400: openapi.Response("Not all the parameters were satisfied"),
        },
        operation_description="Detects the texts on the image using Google Vision API",
        operation_summary="Photo report text detect",
        tags=['Photo report'],
        manual_parameters=[
            openapi.Parameter('file', openapi.IN_FORM, description="The file to detect texts on it",
                              type=openapi.TYPE_FILE, required=True),
            openapi.Parameter('rotate_angle', openapi.IN_FORM, description="The angle to rotate image by",
                              type=openapi.TYPE_INTEGER, required=False)
        ]
    )
    def post(self, request) -> Response:
        data = dict((key, value) for (key, value) in request.data.items())
        file = data.get('file')
        rotate_angle = data.get('rotate_angle', 0)

        try:
            rotate_angle = int(rotate_angle)
            if rotate_angle < -360 or rotate_angle > 360:
                raise ValueError(
                    _("Rotate angle should be less or equal to 360 degrees and greater or equal to the -360 degrees")
                )
        except ValueError:
            return Response(
                dict(rotate_angle=[
                    _("Rotate angle should be less or equal to 360 degrees and greater or equal to the -360 degrees")]),
                status=status.HTTP_400_BAD_REQUEST
            )

        start_time = datetime.datetime.now()
        image_bytes = LJImageUtils.get_valid_image_bytes(file, rotate_angle=rotate_angle)
        if not image_bytes:
            return Response(
                dict(file=[_("Not a valid image")]),
                status=status.HTTP_400_BAD_REQUEST
            )
        end_time = datetime.datetime.now()
        time_diff = (end_time - start_time)
        execution_time = time_diff.total_seconds() * 1000
        print("LJImageUtils.get_valid_image_bytes completed in {0:.0f}ms".format(execution_time))

        start_time = datetime.datetime.now()
        google_client = vision.ImageAnnotatorClient(credentials=getattr(settings, 'GS_CREDENTIALS'))

        end_time = datetime.datetime.now()
        time_diff = (end_time - start_time)
        execution_time = time_diff.total_seconds() * 1000
        print("vision.ImageAnnotatorClient.from_service_account_file completed in {0:.0f}ms".format(execution_time))

        start_time = datetime.datetime.now()
        image = vision.Image(content=image_bytes)
        response = google_client.text_detection(image=image)
        texts = response.text_annotations
        data = []

        for text in texts:
            vertices = [dict(x=vertex.x, y=vertex.y) for vertex in text.bounding_poly.vertices]
            data.append(
                dict(text=text.description, vertices=vertices)
            )
        end_time = datetime.datetime.now()
        time_diff = (end_time - start_time)
        execution_time = time_diff.total_seconds() * 1000
        print("google_client.text_detection completed in {0:.0f}ms".format(execution_time))

        if response.error.message:
            return Response(
                dict(error='{}\nFor more info on error messages, check: '
                           'https://cloud.google.com/apis/design/errors'.format(
                    response.error.message)),
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(data, status=status.HTTP_200_OK)
