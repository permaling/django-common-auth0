from __future__ import unicode_literals

__author__ = 'David Baum'

from django.contrib import admin
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _

from lj_common_shared_service.utils.filters import LJInputFilter


class LJTeamMemberOrganizationInputFilter(LJInputFilter):
    parameter_name = 'organization'
    title = _('Organization name')

    def queryset(self, request, queryset):
        if self.value() is not None:
            name = self.value()
            return queryset.filter(
                Q(organization__name__icontains=name)
            )


class LJUserIsAuth0ListFilter(admin.SimpleListFilter):
    title = _('Auth0 user')
    parameter_name = 'is_auth0_user'

    def lookups(self, request, model_admin):
        return (
            ('Yes', 'Yes'),
            ('No', 'No'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'No':
            return queryset.filter(~Q(auth0_user_id__isnull=True))
        elif value == 'Yes':
            return queryset.exclude(~Q(auth0_user_id__isnull=True))
        return queryset


class LJOrganizationTeamMemberIsAuth0ListFilter(admin.SimpleListFilter):
    title = _('Auth0 user')
    parameter_name = 'user__is_auth0_user'

    def lookups(self, request, model_admin):
        return (
            ('Yes', 'Yes'),
            ('No', 'No'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'Yes':
            return queryset.filter(~Q(user__auth0_user_id__isnull=True))
        elif value == 'No':
            return queryset.exclude(~Q(user__auth0_user_id__isnull=True))
        return queryset
