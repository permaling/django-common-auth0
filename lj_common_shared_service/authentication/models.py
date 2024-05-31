from __future__ import unicode_literals

__author__ = 'David Baum'

import logging, sys, uuid

from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser, BaseUserManager, PermissionsMixin)
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from auth0.v3 import management, Auth0Error
from avatar.templatetags.avatar_tags import avatar_url

from djstripe.enums import BankAccountStatus, CouponDuration
from djstripe.exceptions import MultipleSubscriptionException
from djstripe.models import Customer, Coupon, Plan, Subscription

from guardian.mixins import GuardianUserMixin
from rest_framework.status import HTTP_409_CONFLICT

from lj_common_shared_service.abstract.models import LJAbstractDateHistoryModel
from lj_common_shared_service.auth0.helper import get_auth0_client_access_token
from lj_common_shared_service.auth0.settings import AUTH0_SETTINGS, AUTH0_USER_META_ENV
from lj_common_shared_service.utils.file import LJRandomFileName
from lj_common_shared_service.utils.enums import LJOrganizationStatusEnum, LJOrganizationApplicationEnum, \
    OrganizationTeamMemberStatusEnum

from safedelete.models import SafeDeleteModel

logger = logging.getLogger(__name__)


class LJOrganization(SafeDeleteModel):
    name = models.CharField(max_length=255, verbose_name=_("Name"), db_index=True)
    team_name = models.CharField(max_length=255, verbose_name=_("Team name"), null=True, blank=True, default=None)
    company = models.CharField(_('Company'), max_length=512, blank=True, null=True, default=None)
    phone_number = models.CharField(_('Phone number'), max_length=512, blank=True, null=True, default=None)
    invitation_code = models.CharField(blank=True, max_length=1024, null=True, unique=True, editable=True,
                                       verbose_name=_("Invitation code"), db_index=True)
    address = models.CharField(_('Address'), max_length=1024, blank=True, null=True, default=None)
    status = models.CharField(
        max_length=255,
        choices=LJOrganizationStatusEnum.get_model_choices(),
        verbose_name=_('Status'),
        default=LJOrganizationStatusEnum.HOLD.value.key
    )
    photo = models.ImageField(default=None, null=True, blank=True, verbose_name=_('Logo'), upload_to=LJRandomFileName(''))
    is_validate_email = models.BooleanField(
        verbose_name=_("Validate mails"), help_text=_(
            'Check if the mail is not in the blacklist - '
            'https://knowledge.hubspot.com/forms/what-domains-are-blocked-when-using-the-forms-email-domains-to-block-feature'
        ),
        default=False
    )
    has_public_data = models.BooleanField(_('Contains public data to expose'), default=False)
    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False, verbose_name=_('Unique UUID hash'))

    class Meta:
        verbose_name_plural = _("Organizations")
        verbose_name = _("Organization")
        ordering = ['name']

    def __str__(self):
        return u"%s" % self.name

    def __unicode__(self):
        return self.name


class LJUserManager(BaseUserManager):
    """Custom manager for LJUser."""

    def _create_user(self, email, password,
                     is_staff, is_superuser, **extra_fields):
        """
        Create and save an EmailUser with the given email and password.

        :param str email: user email
        :param str password: user password
        :param bool is_staff: whether user staff or not
        :param bool is_superuser: whether user admin or not
        :return custom_user.models.EmailUser user: user
        :raise ValueError: email is not set
        """
        now = timezone.now()
        if not email:
            raise ValueError('The given email must be set')
        email = self.normalize_email(email)
        is_active = extra_fields.pop("is_active", True)
        user = self.model(email=email, is_staff=is_staff, is_active=is_active,
                          is_superuser=is_superuser, last_login=None,
                          date_joined=now, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        """
        Create and save an LJUser with the given email and password.

        :param str email: user email
        :param str password: user password
        :return custom_user.models.EmailUser user: regular user
        """
        is_staff = extra_fields.pop("is_staff", False)
        return self._create_user(email, password, is_staff, False,
                                 **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        """
        Create and save an EmailUser with the given email and password.

        :param str email: user email
        :param str password: user password
        :return custom_user.models.EmailUser user: admin user
        """
        return self._create_user(email, password, True, True,
                                 **extra_fields)


class AbstractLJUser(AbstractBaseUser, LJAbstractDateHistoryModel, PermissionsMixin, GuardianUserMixin,
                     SafeDeleteModel):
    """
    Abstract User with the same behaviour as Django's default User.

    AbstractLJUser does not have username field. Uses email as the
    USERNAME_FIELD for authentication.
    Use this if you need to extend LJUser.
    Inherits from both the AbstractBaseUser and PermissionMixin.
    The following attributes are inherited from the superclasses:
        * password
        * last_login
        * is_superuser

    Change the LJUser permissions for the LJPhotoReport:
    from guardian.shortcuts import assign_perm
    assign_perm('change_ljphotoreport', <LJUser instance>, <LJPhotoReport instance>)

    Check if the user has the permission:
    <LJUser instance>.has_perm('change_ljphotoreport', <LJPhotoReport instance>)
    """
    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False, verbose_name=_('Unique UUID hash'))
    username = models.CharField(_('username'), max_length=255, unique=False, null=True, default=None)
    email = models.EmailField(_('email address'), max_length=255,
                              unique=True, db_index=True)
    full_name = models.CharField(_('Full name'), max_length=100, blank=True, null=True, default=None)
    company = models.CharField(_('Company'), max_length=100, blank=True, null=True, default=None)
    is_staff = models.BooleanField(
        _('staff status'), default=False, help_text=_(
            'Designates whether the user can log into this admin site.'))
    is_active = models.BooleanField(_('active'), default=True, help_text=_(
        'Designates whether this user should be treated as '
        'active. Unselect this instead of deleting accounts.'))
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)
    is_pending_deletion = models.BooleanField(_('pending deletion'), default=False,
                                              help_text=_(
                                                  'Designates whether the user has requested full account deletion'))
    job_title = models.CharField(_('Job title'), max_length=100, blank=True, null=True, default=None)
    referral = models.CharField(_('How did you hear about us?'), max_length=255, blank=True, null=True, default=None)
    organization = models.ForeignKey(LJOrganization, blank=True, null=True, default=None,
                                     related_name='organization_user', on_delete=models.SET_NULL)
    is_organization_admin = models.BooleanField(_('Organization admin'), default=False)
    is_organization_editor = models.BooleanField(_('Organization editor'), default=True)
    is_public = models.BooleanField(_('Public account'), default=False)
    pin_code = models.PositiveIntegerField(
        _('Pin code'),
        validators=[MinValueValidator(1000), MaxValueValidator(9999)],
        default=1000
    )
    auth0_user_id = models.CharField(_('Auth0 user ID'), max_length=100, blank=True, null=True, default=None)
    picture = models.ImageField(default=None, null=True, verbose_name=_('Avatar'), upload_to=LJRandomFileName(''))
    points = models.PositiveIntegerField(default=0, verbose_name=_('Earned points'))
    is_public_contribution = models.BooleanField(_('Public contribution shown'), default=True)
    description = models.TextField(verbose_name=_("Description"), blank=True, null=True,
                                   default=None)
    objects = LJUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        abstract = True

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        """Return the email."""
        return self.email

    def email_user(self, subject, message, from_email=None, **kwargs):
        """Send an email this User."""
        send_mail(subject, message, from_email, [self.email], **kwargs)

    def avatar_url(self, size=settings.AVATAR_DEFAULT_SIZE):
        return avatar_url(self, size)

    def clean(self):
        if self.organization and self.pin_code:
            organization_users = LJUser.objects.filter(
                organization=self.organization
            )

            if self.id:
                organization_users = organization_users.exclude(id=self.id)

            organization_users_pin_codes = list(organization_users.values_list('pin_code', flat=True))
            if self.pin_code in organization_users_pin_codes:
                raise ValidationError(
                    _("Such pin code is already assigned to another user in the organization"),
                    code=HTTP_409_CONFLICT
                )

    def validate_auth0_metadata(self, is_merge=False, user_metadata=None):
        if self.auth0_user_id:
            try:
                if not user_metadata:
                    token = get_auth0_client_access_token()
                    auth0_domain = AUTH0_SETTINGS.get("AUTH0_DOMAIN")
                    auth0_users_manager = management.Users(domain=auth0_domain, token=token)
                    user_data = auth0_users_manager.get(self.auth0_user_id, fields=['user_metadata'])
                    user_metadata = user_data.get('user_metadata', {})
                if user_metadata is not None:
                    organization_data = user_metadata.get(AUTH0_USER_META_ENV, {})
                    organizations = organization_data.get('organizations', [])
                    team_members = LJOrganizationTeamMember.objects.select_related(
                        'organization'
                    ).filter(user=self)
                    organizations_count = team_members.count()
                    if is_merge or organizations_count != len(organizations):
                        organizations = [
                            dict(
                                organization=team_member.organization.name,
                                organization_uuid=str(team_member.organization.uuid),
                                is_organization_editor=team_member.is_organization_editor,
                                is_organization_admin=team_member.is_organization_admin,
                                is_organization_creator=team_member.is_organization_creator
                            ) for team_member in team_members
                        ]
                        if organizations:
                            organization_data.update(
                                organizations=organizations
                            )
                            organization_data_payload = dict(
                                user_metadata={AUTH0_USER_META_ENV: organization_data}
                            )
                            auth0_users_manager.update(self.auth0_user_id, organization_data_payload)
            except Auth0Error:
                logger.error(f'An error occurred while fetching the auth0 user data for id {self.auth0_user_id}')

    @cached_property
    def custom_subscription_settings(self):
        return getattr(self, 'organization_custom_subscription_settings', None)

    @cached_property
    def has_active_subscription(self) -> bool:
        """Check if a user has an active subscription."""
        if self.customer:
            try:
                return self.customer.has_any_active_subscription()
            except Exception:
                if self.subscription and self.subscription.is_valid():
                    return True
            return False
        return self.subscription and self.subscription.is_valid()

    @cached_property
    def customer(self) -> Customer:
        """Get or create and get a customer instance of the user."""
        customer, created = Customer.get_or_create(subscriber=self)
        return customer

    @cached_property
    def subscription(self) -> Subscription:
        """
        Get or create the active subscription of the user.

        If there are more than one active subscription, the latest one is returned.
        The others will be cancelled.
        """
        try:
            return getattr(self.customer, 'subscription', None)
        except MultipleSubscriptionException:
            # Return the latest active subscription, others should be cancelled
            latest_subscription = None
            valid_subscriptions = [sub for sub in self.customer.subscriptions.all() if sub.is_valid()]
            for subscription in valid_subscriptions:
                if not latest_subscription or latest_subscription.current_period_end < subscription.current_period_end:
                    latest_subscription = subscription
            for subscription in valid_subscriptions:
                if subscription.stripe_id != latest_subscription.stripe_id:
                    try:
                        subscription.cancel(at_period_end=False)
                    except Exception as e:
                        logger.error(f'An error occurred while cancelling the user subscription: {e}')
            return latest_subscription
        return None

    @cached_property
    def plan(self) -> Plan:
        """Return an active plan the user is currently subscribed on."""
        return getattr(self.subscription, 'plan', None)

    @property
    def has_valid_source(self) -> bool:
        payment_method = self.customer.default_source
        if payment_method is None:
            return False
        # Check the bank account status. Cards are considered as valid by default
        # and have no status field, so let they be "verified" by default too.
        status = getattr(payment_method, 'status', BankAccountStatus.verified)
        return status == BankAccountStatus.verified

    @property
    def plan_metadata(self):
        """Return metadata dictionary of the current plan of user's subscription."""
        return getattr(self.plan, 'metadata', {})

    @property
    def private_trays_number_limit(self) -> int:
        """Return limit of private trays number."""
        if self.is_superuser:
            return sys.maxsize
        if self.custom_subscription_settings:
            return getattr(self.custom_subscription_settings, 'private_trays_number_limit', 0)
        return int(self.plan_metadata.get('private_trays_number_limit', '0'))

    @property
    def team_members_number_limit(self) -> int:
        """Return limit of team members number."""
        if self.is_superuser:
            return sys.maxsize
        if self.custom_subscription_settings:
            return getattr(self.custom_subscription_settings, 'team_members_number_limit', 1)
        return int(self.plan_metadata.get('team_members_number_limit', '0'))

    @property
    def notes_number_limit(self) -> int:
        """Return limit of coders number."""
        if self.is_superuser:
            return sys.maxsize
        if self.custom_subscription_settings:
            return getattr(self.custom_subscription_settings, 'notes_number_limit', 1)
        return int(self.plan_metadata.get('notes_number_limit', '0'))

    @property
    def ai_assist_number_limit(self) -> int:
        """Return limit of AI assist number."""
        if self.is_superuser:
            return sys.maxsize
        if self.custom_subscription_settings:
            return getattr(self.custom_subscription_settings, 'ai_assist_number_limit', 1)
        return int(self.plan_metadata.get('ai_assist_number_limit', '0'))

    @property
    def private_instruments_number_limit(self) -> int:
        """Return limit of private instruments number."""
        if self.is_superuser:
            return sys.maxsize
        if self.custom_subscription_settings:
            return getattr(self.custom_subscription_settings, 'private_instruments_number_limit', 1)
        return int(self.plan_metadata.get('private_instruments_number_limit', '0'))

    def add_coupon(
            self,
            amount_off: float = 0.0,
            currency: str = 'USD',
            duration: CouponDuration = CouponDuration.once,
            percent_off=None,
            idempotency_key=None
    ) -> Coupon:
        if not duration:
            duration = CouponDuration.once
        stripe_coupon = Coupon._api_create(
            amount_off=amount_off,
            currency=currency,
            percent_off=percent_off,
            duration=duration,
            idempotency_key=idempotency_key,
        )
        coupon, _created = Coupon.objects.get_or_create(
            stripe_id=stripe_coupon["id"],
            defaults={
                "amount_off": stripe_coupon["amount_off"],
                "currency": stripe_coupon["currency"],
                "percent_off": stripe_coupon["percent_off"],
                "duration": stripe_coupon["duration"],
                "livemode": stripe_coupon["livemode"],
            }
        )
        self.customer.add_coupon(coupon)

        return coupon


class LJUser(AbstractLJUser):
    """
    Concrete class of AbstractLJUser.

    Use this if you don't need to extend LJUser.
    """

    class Meta(AbstractLJUser.Meta):
        swappable = 'AUTH_USER_MODEL'

    @property
    def contribution_ranking(self):
        rank = LJUser.objects.filter(points__gt=self.points, is_public_contribution=True).count()
        return rank + 1


class LJOrganizationTeamMember(LJAbstractDateHistoryModel):
    organization = models.ForeignKey(
        LJOrganization,
        related_name='organization_team_member',
        verbose_name=_("Team member organization"),
        on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        LJUser,
        related_name='organization_team_member',
        verbose_name=_("Organization team member"),
        on_delete=models.CASCADE
    )
    is_organization_admin = models.BooleanField(_('Organization admin'), default=False)
    is_organization_editor = models.BooleanField(_('Organization editor'), default=True)
    is_organization_creator = models.BooleanField(_('Organization creator'), default=False)
    is_customer_facing = models.BooleanField(
        _('Customer facing user'),
        default=False,
        help_text=_("User who can login to organization incognito")
    )
    status = models.CharField(
        max_length=255,
        choices=OrganizationTeamMemberStatusEnum.get_model_choices(),
        verbose_name=_('Status'),
        default=OrganizationTeamMemberStatusEnum.ACTIVE.value.key
    )
    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False, verbose_name=_('Unique UUID hash'))

    class Meta:
        verbose_name = _('Organization team member')
        verbose_name_plural = _('Organization team members')
        get_latest_by = 'date_created'

    def __str__(self):
        return u"{} - {}".format(
            self.user.email,
            self.organization.name
        )

    def __unicode__(self):
        return f'{self.user.email} - {self.organization.name}'

    def clean(self):
        organization_team_members = LJOrganizationTeamMember.objects.filter(
            organization=self.organization,
            user=self.user
        )

        if self.id:
            organization_team_members = organization_team_members.exclude(id=self.id)

        if organization_team_members:
            raise ValidationError(
                _("The user is already a team member of this organization"),
                code=HTTP_409_CONFLICT
            )


class LJOrganizationApplicationPermission(LJAbstractDateHistoryModel):
    organization = models.ForeignKey(
        LJOrganization,
        related_name='organization_application_permission',
        verbose_name=_("Organization application permission"),
        on_delete=models.CASCADE
    )
    application = models.CharField(
        max_length=10,
        choices=LJOrganizationApplicationEnum.get_model_choices(),
        verbose_name=_('Application'),
        blank=True,
        default=None,
        null=True
    )

    class Meta:
        verbose_name = _('Organization application access')
        verbose_name_plural = _('Organization application accesses')
        get_latest_by = 'date_created'

    def __str__(self):
        return u"{} - {}".format(
            self.application,
            self.organization.name
        )

    def __unicode__(self):
        return f'{self.application} - {self.organization.name}'
