from __future__ import unicode_literals

__author__ = 'David Baum'

import logging


from django.conf import settings
from django.contrib.auth import authenticate, login, get_user_model
from django.core.mail import EmailMultiAlternatives
from django.utils.translation import ugettext_lazy as _
from djrill import MandrillRecipientsRefused

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from rest_framework import parsers, renderers, serializers, status, viewsets
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView

from lj_common_shared_service.auth0.authentication import LJJSONWebTokenAuthentication
from lj_common_shared_service.rest.serializers import LJUserAuthTokenSerializer, LJUserModelSerializer, \
    LJUserRegistrationSerializer, PasswordResetSerializer, PasswordResetConfirmSerializer, \
    LJUserTokenObtainPairSerializer, LJUserTokenRefreshSerializer, LJUserTokenVerifySerializer
from lj_common_shared_service.authentication.models import LJOrganization, LJOrganizationTeamMember
from lj_common_shared_service.rest.validators import uuid_validate
from lj_common_shared_service.utils.email import BlockedEmailsProvider
from lj_common_shared_service.utils.logging.mixins import LoggingMixin

User = get_user_model()
logger = logging.getLogger(__name__)


class LJUserTokenObtainPairView(LoggingMixin, TokenObtainPairView):
    serializer_class = LJUserTokenObtainPairSerializer

    @swagger_auto_schema(
        operation_description="Obtain user token pair",
        operation_summary="User pair token obtain",
        tags=['User JWT token'],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class LJUserTokenRefreshView(LoggingMixin, TokenRefreshView):
    serializer_class = LJUserTokenRefreshSerializer

    @swagger_auto_schema(
        operation_description="Refresh user JWT token",
        operation_summary="User JWT token refresh",
        tags=['User JWT token'],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class LJUserTokenVerifyView(LoggingMixin, TokenVerifyView):
    serializer_class = LJUserTokenVerifySerializer

    @swagger_auto_schema(
        operation_description="Verify user JWT token",
        operation_summary="User JWT token verify",
        tags=['User JWT token'],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class LJUserTokenAuthenticationAPIView(LoggingMixin, APIView):
    throttle_classes = ()
    authentication_classes = (TokenAuthentication,)
    permission_classes = (AllowAny,)
    parser_classes = (parsers.FormParser, parsers.MultiPartParser,)
    renderer_classes = (renderers.JSONRenderer,)
    serializer_class = LJUserAuthTokenSerializer

    @swagger_auto_schema(
        responses={
            200: LJUserModelSerializer(many=False),
            400: openapi.Response("The user is not authenticated, returns the JSON of the relevant errors")
        },
        operation_description="Log in the user and return the serialized user JSON data with token inside.",
        operation_summary="Login user",
        operation_id="Login user",
        tags=['User'],
        manual_parameters=[
            openapi.Parameter('email', openapi.IN_QUERY, description="The email of the user to let him in",
                              type=openapi.TYPE_STRING, required=True),
            openapi.Parameter('password', openapi.IN_QUERY, description="The password of the user to authenticate",
                              type=openapi.TYPE_STRING, required=True),
        ]
    )
    def get(self, request) -> Response:
        data = request.query_params
        serializer = self.serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        if user.is_active:
            login(request, user)

        token, created = Token.objects.get_or_create(user=user)
        data = LJUserModelSerializer(context=dict(request=request)).to_representation(user)
        data.update(token=token.key)

        return Response(data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        responses={
            201: LJUserModelSerializer(many=False),
            400: openapi.Response(
                "The user already exists, whether the passwords do not match, returns the detailed errors JSON object"),
            403: openapi.Response(
                "The invitation code is required"),
            404: openapi.Response(
                "The invitation code does not exist")
        },
        operation_description="Register and log in the user and return the serialized user "
                              "JSON data with generated token inside.",
        operation_summary="Register user",
        operation_id="Register user",
        tags=['User'],
        manual_parameters=[
            openapi.Parameter('email', openapi.IN_FORM, description="The email of the user to register",
                              type=openapi.TYPE_STRING, required=True),
            openapi.Parameter('password1', openapi.IN_FORM, description="The password of the user to register",
                              type=openapi.TYPE_STRING, required=False),
            openapi.Parameter('password2', openapi.IN_FORM,
                              description="The confirmed password of the user to register",
                              type=openapi.TYPE_STRING, required=False),
            openapi.Parameter('full_name', openapi.IN_FORM,
                              description="The full name of the user",
                              type=openapi.TYPE_STRING, required=False),
            openapi.Parameter('company', openapi.IN_FORM,
                              description="The company/hospital name",
                              type=openapi.TYPE_STRING, required=False),
            openapi.Parameter('invitation_code', openapi.IN_FORM,
                              description="The invitation code",
                              type=openapi.TYPE_STRING, required=True),
        ]
    )
    def post(self, request) -> Response:
        request_data = request.data.copy()

        if not request_data.get('full_name'):
            request_data.update(full_name=request_data.get('email'))
        if not request_data.get('password1'):
            password = User.objects.make_random_password()
            request_data.update(password1=password)
            request_data.update(password2=password)

        password = request_data.get('password1')
        email = request_data.get('email')
        full_name = request_data.get('full_name')
        invitation_code = request_data.get('invitation_code')

        if not invitation_code:
            return Response(
                data=dict(invitation_code=['Invitation code is required']),
                status=status.HTTP_403_FORBIDDEN
            )

        invitation_code = invitation_code.strip()
        try:
            organization = LJOrganization.objects.get(invitation_code=invitation_code)
            if organization.is_validate_email and not BlockedEmailsProvider.is_valid(email):
                raise serializers.ValidationError([_("The email address is in the blacklist")])
        except LJOrganization.DoesNotExist:
            return Response(
                data=dict(invitation_code=['Enter valid invitation code']),
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            user = User.objects.get(email=email)
            if user.organization and user.organization.pk != organization.pk:
                return Response(
                    data=dict(invitation_code=['Enter valid invitation code']),
                    status=status.HTTP_404_NOT_FOUND
                )
        except User.DoesNotExist:
            pass

        if not user:
            serializer = LJUserRegistrationSerializer(data=request_data)
            serializer.is_valid(raise_exception=True)

            user = User._default_manager.create_user(
                email=email,
                password=password,
                full_name=full_name,
                organization=organization
            )
            user = authenticate(email=user.email, password=password)
            if user.is_active:
                login(request, user)

            LJOrganizationTeamMember(
                user=user,
                organization=organization
            ).save()

        token, created = Token.objects.get_or_create(user=user)
        data = LJUserModelSerializer(context=dict(request=request)).to_representation(user)
        data.update(token=token.key)
        return Response(
            data=data,
            status=status.HTTP_201_CREATED
        )

    @swagger_auto_schema(
        responses={
            200: LJUserModelSerializer(many=False),
            404: openapi.Response("The user is does not exist")
        },
        operation_description="Reset the password",
        operation_summary="Reset password",
        tags=['User'],
        manual_parameters=[
            openapi.Parameter('email', openapi.IN_QUERY, description="The email of the user to reset the password",
                              type=openapi.TYPE_STRING, required=True),
        ]
    )
    def put(self, request) -> Response:
        data = request.query_params
        serializer = self.serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        if user.is_active:
            login(request, user)

        token, created = Token.objects.get_or_create(user=user)
        data = LJUserModelSerializer(context=dict(request=request)).to_representation(user)
        data.update(token=token.key)
        return Response(data)

class LJUserProfileViewSet(LoggingMixin, viewsets.GenericViewSet):
    authentication_classes = (LJJSONWebTokenAuthentication, TokenAuthentication, SessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    parser_classes = (parsers.FormParser, parsers.MultiPartParser,)
    renderer_classes = (renderers.JSONRenderer,)
    serializer_class = LJUserModelSerializer
    model = User
    pagination_class = None

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        kwargs['context'] = self.get_serializer_context()
        return serializer_class(*args, **kwargs)

    @swagger_auto_schema(
        responses={
            200: LJUserModelSerializer(many=False),
            401: openapi.Response("The current authenticated user is not authenticated")
        },
        operation_description="Get user profile",
        operation_summary="Get current user profile",
        operation_id="Get current user profile",
        tags=['User'],
        manual_parameters=[]
    )
    def get(self, request) -> Response:
        current_user = request.user
        if current_user.email.startswith('auth0'):
            user_id = current_user.email.split('auth0.')[-1]
        else:
            user_id = current_user.id

        try:
            current_user = self.model.objects.prefetch_related(
                'organization_team_member'
            ).get(id=user_id)
            current_user.validate_auth0_metadata(is_merge=True)
        except self.model.DoesNotExist:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        data = self.get_serializer(current_user).data
        return Response(data, status=status.HTTP_200_OK)


class PasswordResetView(LoggingMixin, GenericAPIView):
    serializer_class = PasswordResetSerializer
    permission_classes = (AllowAny,)
    parser_classes = (parsers.FormParser, parsers.MultiPartParser,)

    @swagger_auto_schema(
        responses={
            200: openapi.Response("The reset password instructions were sent to the user email address"),
            400: openapi.Response("No possibility to reset the password for the provided email address")
        },
        operation_description="Reset user profile by email address",
        operation_summary="Reset user profile",
        tags=['User'],
        manual_parameters=[
            openapi.Parameter('email', openapi.IN_FORM, description="The email of the user to reset the password for",
                              type=openapi.TYPE_STRING, required=True),
            openapi.Parameter('domain', openapi.IN_FORM, description="The domain of the reset password URL",
                              type=openapi.TYPE_STRING, required=False),
        ]
    )
    def post(self, request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        serializer.save()

        return Response(
            {"detail": _("Password reset e-mail has been sent.")},
            status=status.HTTP_200_OK
        )


class PasswordResetConfirmView(LoggingMixin, GenericAPIView):
    serializer_class = PasswordResetConfirmSerializer
    parser_classes = (parsers.FormParser, parsers.MultiPartParser,)
    permission_classes = (AllowAny,)

    def dispatch(self, *args, **kwargs):
        return super(PasswordResetConfirmView, self).dispatch(*args, **kwargs)

    @swagger_auto_schema(
        responses={
            200: openapi.Response("The reset password instructions were sent to the user email address"),
            400: openapi.Response("No possibility to reset the password for the provided email address")
        },
        operation_description="Reset user profile by email address",
        operation_summary="Reset user profile",
        tags=['User'],
        manual_parameters=[
            openapi.Parameter('password', openapi.IN_FORM, description="The password to reset",
                              type=openapi.TYPE_STRING, required=True),
            openapi.Parameter('uid', openapi.IN_FORM, description="The uid from the mail",
                              type=openapi.TYPE_STRING, required=True),
            openapi.Parameter('token', openapi.IN_FORM, description="The token from the mail",
                              type=openapi.TYPE_STRING, required=True),
        ]
    )
    def post(self, request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"detail": _("Password has been reset with the new password.")},
            status=status.HTTP_200_OK
        )


class ContactUsView(LoggingMixin, GenericAPIView):
    serializer_class = serializers.Serializer
    parser_classes = (parsers.FormParser, parsers.MultiPartParser,)
    permission_classes = (AllowAny,)

    def dispatch(self, *args, **kwargs):
        return super(ContactUsView, self).dispatch(*args, **kwargs)

    @swagger_auto_schema(
        responses={
            200: openapi.Response("The message has been sent"),
            400: openapi.Response("No subject or message were not provided")
        },
        operation_description="Sends message to the {} email address".format(settings.DEFAULT_FROM_EMAIL),
        operation_summary="Contact us",
        tags=['User'],
        manual_parameters=[
            openapi.Parameter('message', openapi.IN_FORM, description="Message to send",
                              type=openapi.TYPE_STRING, required=True),
            openapi.Parameter('subject', openapi.IN_FORM, description="Subject of the message",
                              type=openapi.TYPE_STRING, required=True),
        ]
    )
    def post(self, request, *args, **kwargs) -> Response:
        request_data = request.data.copy()
        message = request_data.get('message')
        subject = request_data.get('subject')

        current_user = request.user

        if not message:
            return Response(
                data=dict(message=['The message is missing']),
                status=status.HTTP_400_BAD_REQUEST
            )
        if not subject:
            return Response(
                data=dict(subject=['The subject is missing']),
                status=status.HTTP_400_BAD_REQUEST
            )
        from_email = '{}<{}>'.format(current_user.get_full_name(),
                                     settings.DEFAULT_FROM_EMAIL) if current_user.get_full_name() else settings.DEFAULT_FROM_EMAIL
        mail_messsage = EmailMultiAlternatives(
            subject=subject,
            from_email=from_email,
            to=[settings.DEFAULT_FROM_EMAIL],
            headers={}
        )

        mail_messsage.attach_alternative("{}<hr/> Sent by {}".format(message, current_user.email), "text/html")
        try:
            mail_messsage.send()
        except MandrillRecipientsRefused as err:
            logger.error("Error sending mail by {}".format(current_user.email))
            logger.error(err)

        return Response(
            {"detail": _("The message has been sent")},
            status=status.HTTP_200_OK
        )


class LJUserOrganizationPinCodeAuthenticationAPIView(LoggingMixin, APIView):
    throttle_classes = ()
    authentication_classes = (TokenAuthentication,)
    permission_classes = (AllowAny,)
    parser_classes = ()
    renderer_classes = (renderers.JSONRenderer,)
    serializer_class = LJUserModelSerializer

    @swagger_auto_schema(
        responses={
            200: LJUserModelSerializer(many=False),
            400: openapi.Response("The user is not authenticated, returns the JSON of the relevant errors")
        },
        operation_description="Log in the user by organization and pin code and return the serialized user JSON data with token inside.",
        operation_summary="Pin user login",
        tags=['User'],
        manual_parameters=[
            openapi.Parameter('organization_uuid', openapi.IN_PATH, description="The uuid of the organization",
                              type=openapi.TYPE_STRING, required=True),
            openapi.Parameter('pin_code', openapi.IN_QUERY, description="The pin_code of the user to authenticate",
                              type=openapi.TYPE_NUMBER, required=True),
        ]
    )
    def get(self, request, organization_uuid: str) -> Response:
        data = request.query_params
        pin_code = data.get('pin_code')

        if not pin_code:
            return Response(
                data={"pin_code": "Pin code is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        elif not pin_code.isnumeric():
            return Response(
                data={"pin_code": "Pin code should be a 4 digit number"},
                status=status.HTTP_400_BAD_REQUEST
            )
        uuid_validate.validate(uuid=organization_uuid)
        if uuid_validate.has_errors():
            return Response(
                data=uuid_validate.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            team_member = LJOrganizationTeamMember.objects.get(organization__uuid=organization_uuid,
                                                               user__pin_code=pin_code)
        except User.DoesNotExist:
            return Response(
                data={"authentication": "Pin code or organization do not match"},
                status=status.HTTP_400_BAD_REQUEST
            )
        user = team_member.user
        if user.is_active:
            login(request, user, 'rest_framework.authentication.TokenAuthentication')

        token, created = Token.objects.get_or_create(user=user)
        data = LJUserModelSerializer(context=dict(request=request)).to_representation(user)
        data.update(token=token.key)

        return Response(data)
