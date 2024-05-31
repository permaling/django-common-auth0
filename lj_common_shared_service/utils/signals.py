from __future__ import unicode_literals

__author__ = 'David Baum'

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from lj_common_shared_service.authentication.models import LJOrganizationTeamMember


@receiver(post_save, sender=LJOrganizationTeamMember)
def create_organization_team_member(sender, instance, created, **kwargs):
    instance.user.validate_auth0_metadata(is_merge=True)


@receiver(post_delete, sender=LJOrganizationTeamMember)
def delete_profile(sender, instance, *args, **kwargs):
    instance.user.validate_auth0_metadata()
