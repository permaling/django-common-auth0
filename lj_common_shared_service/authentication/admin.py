from __future__ import unicode_literals

__author__ = 'David Baum'

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse, path
from django.utils.translation import ugettext_lazy as _

from django_admin_relation_links import AdminChangeLinksMixin

from hijack.contrib.admin import HijackUserAdminMixin
from rangefilter.filter import DateRangeFilter
from safedelete.admin import SafeDeleteAdmin, highlight_deleted
from lj_common_shared_service.utils.admin import LJAdminThumbnail, SafeDeleteAdminExtended

from .filters import *
from .forms import LJUserCreationForm
from .models import LJUser, LJOrganization, LJOrganizationTeamMember, LJOrganizationApplicationPermission
from ..utils.db import get_model_duplicates
from ..utils.decorators import display


@admin.register(LJOrganizationTeamMember)
class LJOrganizationTeamMemberAdmin(AdminChangeLinksMixin, admin.ModelAdmin):
    list_per_page = 25
    list_display = (
        'id', 'user_link', 'organization_link', 'get_user_full_name',
        'is_organization_admin', 'is_organization_editor',
        'is_organization_creator', 'status', 'date_created', 'date_modified',
        'uuid', 'is_customer_facing',
    )
    search_fields = (
        'user__email', 'user__full_name', 'organization__name', 'status', 'uuid',
    )
    list_filter = (
        LJOrganizationTeamMemberIsAuth0ListFilter,
        LJTeamMemberOrganizationInputFilter,
        'is_organization_admin',
        'is_organization_editor',
        'is_organization_creator',
        'is_customer_facing',
        ('date_created', DateRangeFilter),
        ('date_modified', DateRangeFilter),
    )
    ordering = ('user', 'organization',)
    change_links = ['user', 'organization', ]
    readonly_fields = ('user_link', 'organization_link', 'date_created', 'date_modified', 'uuid',)
    autocomplete_fields = ('user', 'organization',)
    is_remove_duplicate_team_members = True
    change_list_template = 'admin/authentication/organization_team_member_change_list.html'

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context.update(
            is_remove_duplicate_team_members=self.is_remove_duplicate_team_members
        )
        return super(LJOrganizationTeamMemberAdmin, self).changelist_view(
            request, extra_context)

    def get_urls(self):
        urls = super(LJOrganizationTeamMemberAdmin, self).get_urls()
        custom_urls = [
            path(
                "remove-duplicates/",
                self.admin_site.admin_view(self.remove_duplicate_models),
                name='%s_%s_remove_duplicates' % (self.model._meta.app_label, self.model._meta.model_name),
            ),
        ]
        return custom_urls + urls

    def remove_duplicate_models(self, request):
        if request.method == 'GET':
            queryset = get_model_duplicates(self.model, ['user', 'organization'])
            request.current_app = self.admin_site.name
            context = dict(
                self.admin_site.each_context(request),
                action="delete",
                opts=self.model._meta,
                queryset=queryset
            )
            return TemplateResponse(request, "admin/action_confirmation.html", context)

        queryset = self.model.objects.filter(pk__in=request.POST.getlist('_selected_action'))
        for model in queryset:
            model.delete()

        messages.add_message(
            request,
            messages.SUCCESS,
            _("The duplicate team members have been successfully removed")
        )
        return HttpResponseRedirect(
            reverse(
                "admin:%s_%s_changelist" % (self.model._meta.app_label, self.model._meta.model_name)
            )
        )

    @display(ordering='user__full_name', description=_('Full name'))
    def get_user_full_name(self, obj):
        return obj.user.full_name

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        obj.user.validate_auth0_metadata(is_merge=True)


@admin.register(LJUser)
class LJUserAdmin(SafeDeleteAdminExtended, AdminChangeLinksMixin, HijackUserAdminMixin, UserAdmin):
    """EmailUser Admin model."""

    fieldsets = (
        (
            None, {
                'fields': (
                    'email', 'password', 'username', 'pin_code', 'full_name', 'company', 'job_title',
                    'referral', 'organization', 'is_organization_admin', 'is_organization_editor',
                    'auth0_user_id', 'picture_display', 'points', 'is_public_contribution',
                    'description', 'uuid', 'date_created', 'date_modified',
                )
            }
        ),
        (
            _('Permissions'),
            {
                'fields': ('is_pending_deletion', 'is_active', 'is_staff', 'is_superuser',
                           'groups', 'user_permissions')
            }
        ),
        (
            _('Important dates'),
            {
                'fields': (
                    'last_login', 'date_joined'
                )
            }
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': ('email', 'password1', 'password2', 'pin_code',)
            }
        ),
    )
    list_per_page = 25
    # The forms to add and change user instances
    add_form = LJUserCreationForm

    # The fields to be used in displaying the User model.
    # These override the definitions on the base UserAdmin
    # that reference specific fields on auth.User.
    list_display = (
                       highlight_deleted, 'get_user', 'username', 'full_name', 'organization',
                       'picture_display', 'is_pending_deletion', 'is_staff',
                       'date_joined', 'date_created', 'date_modified',
                       'last_login', 'is_organization_admin', 'is_organization_editor',
                       'company', 'pin_code', 'auth0_user_id', 'is_public_contribution', 'points',
                       'organization_team_member_link', 'uuid',
                   ) + SafeDeleteAdminExtended.list_display
    list_filter = (
                      'is_pending_deletion', 'is_staff', 'is_superuser',
                      'is_active', 'groups', 'is_organization_admin',
                      'is_public_contribution', 'is_organization_editor', LJUserIsAuth0ListFilter,
                      ('date_joined', DateRangeFilter), ('last_login', DateRangeFilter),
                      ('date_created', DateRangeFilter), ('date_modified', DateRangeFilter),
                  ) + SafeDeleteAdminExtended.list_filter
    search_fields = ('email', 'full_name', 'organization__name', 'company', 'uuid',)
    ordering = ('email',)
    filter_horizontal = ('groups', 'user_permissions',)
    readonly_fields = (
        'picture_display', 'organization_team_member_link', 'uuid',
        'date_created', 'date_modified',
    )
    changelist_links = ('organization_team_member',)
    picture_display = LJAdminThumbnail(image_field='picture')
    picture_display.short_description = _('Avatar Preview')
    actions = (
                  'add_organization_admin_rights', 'remove_organization_admin_rights',
                  'add_organization_editor_rights', 'remove_organization_editor_rights',
              ) + SafeDeleteAdminExtended.actions
    hijack_success_url = settings.HIJACK_LOGOUT_REDIRECT_URL

    def get_form(self, request, obj=None, **kwargs):
        kwargs['widgets'] = {'description': forms.Textarea}
        return super().get_form(request, obj, **kwargs)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        obj.validate_auth0_metadata(is_merge=True)

    def add_organization_admin_rights(self, request, queryset):
        queryset.update(
            is_organization_admin=True
        )

    def remove_organization_admin_rights(self, request, queryset):
        queryset.update(
            is_organization_admin=False
        )

    def add_organization_editor_rights(self, request, queryset):
        queryset.update(
            is_organization_editor=True
        )

    def remove_organization_editor_rights(self, request, queryset):
        queryset.update(
            is_organization_editor=False
        )

    def get_user(self, obj):
        if obj.email:
            return u"%s" % obj.email
        return u"%s" % obj.username

    add_organization_admin_rights.short_description = _("Add organization admin rights")
    remove_organization_admin_rights.short_description = _("Remove organization admin rights")
    add_organization_editor_rights.short_description = _("Add organization editor rights")
    remove_organization_editor_rights.short_description = _("Remove organization editor rights")
    get_user.short_description = _('User')


@admin.register(LJOrganization)
class LJOrganizationAdmin(SafeDeleteAdminExtended):
    search_fields = ('name',)
    fields = [
        "name", "invitation_code", 'has_public_data', 'photo', 'photo_display',
        'is_validate_email', 'uuid', 'team_name', 'address', 'company', 'phone_number',
        'status'
    ]
    list_display = (
                       highlight_deleted, "invitation_code", 'photo_display', 'has_public_data',
                       'is_validate_email', 'uuid', 'team_name', 'address', 'company',
                       'phone_number', 'status',
                   ) + SafeDeleteAdmin.list_display
    list_filter = (
                      'is_validate_email', 'has_public_data', 'status',
                  ) + SafeDeleteAdmin.list_filter
    readonly_fields = ['photo_display', 'uuid', ]
    photo_display = LJAdminThumbnail(image_field='photo')
    photo_display.short_description = _('Logo Preview')


@admin.register(LJOrganizationApplicationPermission)
class LJOrganizationApplicationPermissionAdmin(AdminChangeLinksMixin, admin.ModelAdmin):
    search_fields = ('organization__name', 'application',)
    fields = [
        'organization', 'application',
    ]
    list_display = (
        'organization_link', 'application',
    )
    list_filter = (
        'application',
    )
    change_links = ['organization', ]
    readonly_fields = ('organization_link', 'date_created', 'date_modified',)
    autocomplete_fields = ('organization',)