from datetime import datetime, timedelta

from django.contrib import admin
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import ugettext_lazy as gettext

from lj_common_shared_service.utils.decorators import with_attrs

from .models import ReferralCode, ReferralNode


class ReferralNodeInline(admin.TabularInline):
    model = ReferralNode
    extra = 0
    readonly_fields = ["date_created"]

    def has_add_permission(self, request, obj):
        """
        Deny permission to add referral nodes inline.
        """
        return False
    
    def has_delete_permission(self, request, obj):
        """
        Deny permission to delete referral nodes inline.
        """
        return False


@admin.register(ReferralCode)
class ReferralCodeAdmin(admin.ModelAdmin):
    list_display = ["owner", "code", "total_referred_users"]
    sortable_by = ["total_referred_users"]
    inlines = [ReferralNodeInline]
    list_filter = [
        ("referralnode__date_created", admin.DateFieldListFilter),
    ]
    search_fields = ["owner__email", "code"]
    
    @with_attrs(short_description=gettext('Total Referred Users'), allow_tags=True, admin_order_field="total_referred_users_count")
    def total_referred_users(self, obj):
        return obj.total_referred_users_count

    def get_queryset(self, request):
        """
        Override queryset to annotate with the count of referred users.
        """
        queryset = super().get_queryset(request)
        
        # Get the filter parameters from the request
        referralnode_date_created = request.GET.get("referralnode__date_created__gte")
        
        if referralnode_date_created:
            try:
                date = datetime.strptime(referralnode_date_created, "%Y-%m-%d %H:%M:%S%z").date()
                today = timezone.now().date()
                date_diff = today - date
                
                # Annotate with filtered count
                queryset = queryset.annotate(
                    total_referred_users_count=Count(
                        "referralnode",
                        filter=Q(referralnode__date_created__date__gte=today - timedelta(days=date_diff.days))
                    )
                )
            except ValueError:
                pass
        else:
            # Annotate with total count
            queryset = queryset.annotate(total_referred_users_count=Count("referralnode"))
        
        return queryset


@admin.register(ReferralNode)
class ReferralNodeAdmin(admin.ModelAdmin):
    list_display = ["referred", "referral_code", "date_created"]
    search_fields = ["referred__email", "referral_code__code", "referral_code__owner__email"]
