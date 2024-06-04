from __future__ import unicode_literals

__author__ = 'David Baum'

from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import password_validators_help_texts, validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.utils.http import urlsafe_base64_decode as uid_decoder
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import force_text

from rest_framework import serializers
from rest_framework.fields import SerializerMethodField
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, \
    TokenRefreshSerializer, TokenVerifySerializer
from rest_framework_simplejwt.settings import APISettings, USER_SETTINGS, IMPORT_STRINGS, DEFAULTS
from rest_framework_simplejwt.tokens import RefreshToken, UntypedToken

from lj_common_shared_service.referrals.models import ReferralNode
from lj_common_shared_service.rest.serializers.organization import LJOrganizationModelSerializer

User = get_user_model()

api_settings = APISettings(USER_SETTINGS, DEFAULTS, IMPORT_STRINGS)


class LJUserAuthTokenSerializer(serializers.Serializer):
    email = serializers.CharField(
        label=_("Email address"),
        help_text=_("Email address"),
        error_messages=dict(
            required=_('Please specify email address')
        )
    )
    password = serializers.CharField(
        label=_("Password"),
        help_text=_("Password"),
        style={'input_type': 'password'},
        error_messages=dict(
            required=_('Please specify the password')
        )
    )

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            user = authenticate(email=email, password=password)

            if user:
                if not user.is_active:
                    raise serializers.ValidationError(dict(non_field_errors=_('User account is disabled.')))
                if user.is_pending_deletion:
                    raise serializers.ValidationError(dict(non_field_errors=_('Your account is queued for deletion, '
                                                                              'you must create an account with a different email address.')))
            else:
                raise serializers.ValidationError(
                    dict(non_field_errors=_("Invalid email address or password was specified")))

        attrs['user'] = user
        return attrs


class LJShortUserModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'id', 'full_name', 'email', 'username',
            'last_login', 'is_superuser',
            'is_active', 'is_staff', 'company',
            'contribution_ranking', 'points', 'is_public_contribution',
            'picture', 'description', 'uuid', 'date_created', 'date_modified',
        )
        read_only_fields = (
            'id', 'is_superuser', 'is_active', 'is_staff', 'uuid',
            'contribution_ranking', 'points', 'is_public_contribution', 'picture',
            'date_created', 'date_modified',
        )


class LJUserModelSerializer(serializers.ModelSerializer):
    organizations = SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'full_name', 'email', 'username',
            'last_login', 'is_superuser',
            'is_active', 'is_staff', 'company',
            'contribution_ranking', 'points', 'is_public_contribution',
            'picture', 'organizations', 'description', 'uuid',
            'date_created', 'date_modified',
        )
        read_only_fields = (
            'id', 'is_superuser', 'is_active', 'is_staff', 'contribution_ranking',
            'points', 'is_public_contribution', 'picture', 'organizations', 'uuid',
            'date_created', 'date_modified',
        )

    def get_organizations(self, obj):
        data = []
        for team_member in obj.organization_team_member.prefetch_related('organization').all():
            organization = team_member.organization
            serializer = LJOrganizationModelSerializer(
                organization,
                many=False
            )
            organization_data = serializer.data
            organization_data.update(
                is_organization_admin=team_member.is_organization_admin,
                is_organization_editor=team_member.is_organization_editor,
                is_organization_creator=team_member.is_organization_creator,
                team_member_status=team_member.status
            )
            data.append(organization_data)
        return data


class LJAuth0UserModelSerializer(LJUserModelSerializer):
    email = serializers.HiddenField(default=serializers.CharField(required=True))
    password = serializers.HiddenField(default=serializers.CharField(required=True))


class LJUserTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)

        user_data = LJUserModelSerializer(self.user, many=False).data
        user_data.update(
            refresh_token=data.get('refresh'),
            access_token=data.get('access')
        )

        return user_data


class LJUserTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        refresh = RefreshToken(attrs['refresh'])
        token = str(refresh.access_token)
        user_id = refresh.get(api_settings.USER_ID_CLAIM)

        user = User.objects.get(**{api_settings.USER_ID_FIELD: user_id})
        user_data = LJUserModelSerializer(user, many=False).data
        user_data.update(
            access_token=token
        )

        return user_data


class LJUserTokenVerifySerializer(TokenVerifySerializer):
    def validate(self, attrs):
        token = UntypedToken(attrs['token'])
        user_id = token.get(api_settings.USER_ID_CLAIM)

        user = User.objects.get(**{api_settings.USER_ID_FIELD: user_id})
        user_data = LJUserModelSerializer(user, many=False).data
        user_data.update(
            access_token=attrs['token']
        )

        return user_data


class LJUserRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField(
        label=_("Email address"),
        help_text=_("Email address"),
        error_messages=dict(
            required=_('Please specify email address')
        )
    )
    password1 = serializers.CharField(
        label=_("Password"),
        help_text=_("Password"),
        style={'input_type': 'password'},
        error_messages=dict(
            required=_('Please specify the password')
        )
    )
    password2 = serializers.CharField(
        label=_("Confirm password"),
        help_text=_("Confirm password"),
        style={'input_type': 'password'},
        error_messages=dict(
            required=_('Please confirm the password')
        )
    )
    full_name = serializers.CharField(
        required=False,
        label=_("Full name"),
        help_text=_("Full name"),
    )

    def validate_email(self, email):
        """
        Validate email.

        :return str email: email
        :raise serializers.ValidationError: Email is duplicated
        """
        # Since LJUser.email is unique, this check is redundant,
        # but it sets a nicer error message than the ORM. See #13147.
        email = email.lower()
        try:
            user = User._default_manager.get(email=email)
        except User.DoesNotExist:
            return email
        if user.is_pending_deletion:
            raise serializers.ValidationError([_('Your account is queued for deletion, '
                                                 'you must create an account with a different email address.')])
        raise serializers.ValidationError([_("A user with that email already exists.")])

    def validate(self, attrs):
        """
        Check that the two password entries match.

        :return str password2: password2
        :raise serializers.ValidationError: password2 != password1
        """
        password1 = attrs.get("password1")
        password2 = attrs.get("password2")
        if password1 != password2:
            raise serializers.ValidationError(
                dict(
                    password2=_("The two password fields didn't match.")
                )
            )
        try:
            validate_password(password2)
        except ValidationError:
            raise serializers.ValidationError(
                dict(password2=' '.join(password_validators_help_texts()))
            )
        return attrs


class PasswordResetSerializer(serializers.Serializer):
    """
    Serializer for requesting a password reset e-mail.
    """
    email = serializers.EmailField()
    password_reset_form_class = PasswordResetForm

    def get_email_options(self):
        """Override this method to change default e-mail options"""
        return {}

    def validate_email(self, value):
        # Create PasswordResetForm with the serializer

        self.reset_form = self.password_reset_form_class(data=self.initial_data)
        if not self.reset_form.is_valid():
            raise serializers.ValidationError(self.reset_form.errors)

        return value

    def save(self):
        request = self.context.get('request')
        domain_override = request.POST.get('domain')
        # Set some values to trigger the send_email method.
        opts = {
            'use_https': request.is_secure(),
            'from_email': getattr(settings, 'DEFAULT_FROM_EMAIL'),
            'request': request,
            'domain_override': domain_override
        }

        opts.update(self.get_email_options())
        self.reset_form.save(**opts)


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Serializer for requesting a password reset e-mail.
    """
    password = serializers.CharField(max_length=128)
    uid = serializers.CharField()
    token = serializers.CharField()

    set_password_form_class = SetPasswordForm

    def custom_validation(self, attrs):
        pass

    def validate(self, attrs):
        self._errors = {}

        # Decode the uidb64 to uid to get User object
        try:
            uid = force_text(uid_decoder(attrs['uid']))
            self.user = User._default_manager.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise ValidationError({'uid': ['Invalid value']})

        attrs.update(
            new_password1=attrs["password"],
            new_password2=attrs["password"]
        )
        self.custom_validation(attrs)
        # Construct SetPasswordForm instance
        self.set_password_form = self.set_password_form_class(
            user=self.user, data=attrs
        )
        if not self.set_password_form.is_valid():
            raise serializers.ValidationError(self.set_password_form.errors)
        if not default_token_generator.check_token(self.user, attrs['token']):
            raise ValidationError({'token': ['Invalid value']})

        return attrs

    def save(self):
        return self.set_password_form.save()


class ReferralNodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralNode
        fields = ['id', 'referral_code', 'referred', 'date_created']
