from __future__ import unicode_literals

__author__ = 'David Baum'

from django.db import models
from django.conf.urls import url
from django.contrib import admin, messages
from django.contrib.admin.utils import model_ngettext
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, reverse
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.encoding import force_text
from django.utils.html import format_html
from django.utils.http import unquote
from django.views.decorators.csrf import csrf_protect

from functools import update_wrapper

from imagekit import ImageSpec
from imagekit.admin import AdminThumbnail
from imagekit.cachefiles import ImageCacheFile

from ordered_model.admin import OrderedModelAdmin

from pilkit.processors import ResizeToFill
from rest_framework.authtoken.admin import TokenAdmin
from rest_framework.authtoken.models import Token

from safedelete.admin import SafeDeleteAdmin
from safedelete.models import HARD_DELETE

csrf_protect_m = method_decorator(csrf_protect)


@admin.register(Token)
class LJFilterTokenAdmin(TokenAdmin):
    search_fields = ['user__email', 'user__username']
    list_filter = ['created']


class LJAdminThumbnailSpec(ImageSpec):
    processors = [ResizeToFill(200, 200)]
    format = 'JPEG'
    options = {'quality': 60}


class LJAdminThumbnail(AdminThumbnail):
    def __call__(self, obj):
        image = getattr(obj, self.image_field)
        if image:
            thumbnail = ImageCacheFile(LJAdminThumbnailSpec(image))
            try:
                thumbnail.generate()

                template = self.template or 'imagekit/admin/thumbnail.html'
                return render_to_string(template, {
                    'model': obj,
                    'thumbnail': thumbnail,
                    'original_image': image,
                })
            except IOError:
                return None
        return None


class LJDragAndDropOrderedModelAdmin(OrderedModelAdmin):
    def move_above_view(self, request, object_id, other_object_id):
        obj = get_object_or_404(self.model, pk=unquote(object_id))
        other_obj = get_object_or_404(self.model, pk=unquote(other_object_id))
        try:
            obj.above(other_obj)
        except ValueError:
            import traceback
            print(traceback.format_exc())
        # go back 3 levels (to get from /pk/move-above/other-pk back to the changelist)
        return HttpResponseRedirect('../../../')

    def get_urls(self):
        def wrap(view):
            def wrapper(*args, **kwargs):
                return self.admin_site.admin_view(view)(*args, **kwargs)

            return update_wrapper(wrapper, view)

        return [
            url(
                r'^(.+)/move-above/(\d+)/$',
                wrap(self.move_above_view),
                name='{app}_{model}_order_above'.format(**self._get_model_info())
            ),
        ] + super().get_urls()

    def make_draggable(self, obj):
        model_info = self._get_model_info()
        url = reverse(
            "{admin_name}:{app}_{model}_order_above".format(admin_name=self.admin_site.name, **model_info),
            args=[-1, 0]  # placeholder pks, will be replaced in js
        )
        template = 'admin/draggable.html'
        return render_to_string(template, {
            'pk': obj.pk,
            'url': url
        })

    make_draggable.allow_tags = True
    make_draggable.short_description = ''


class SafeDeleteAdminExtended(SafeDeleteAdmin):
    hard_delete_template = "admin/hard_delete_selected_confirmation.html"
    actions = ('undelete_selected', 'hard_delete_selected',)

    def hard_delete_selected(self, request, queryset):
        """ Admin action to delete objects finally. """
        if not self.has_delete_permission(request):
            raise PermissionDenied

        original_queryset = queryset.all()
        queryset = queryset.filter(deleted__isnull=False)

        if request.POST.get('post'):
            requested = original_queryset.count()
            changed = queryset.count()

            if changed:
                for obj in queryset:
                    obj.delete(force_policy=HARD_DELETE)
                if requested > changed:
                    self.message_user(
                        request,
                        "Successfully hard deleted %(count_changed)d of the "
                        "%(count_requested)d selected %(items)s." % {
                            "count_requested": requested,
                            "count_changed": changed,
                            "items": model_ngettext(self.opts, requested)
                        },
                        messages.WARNING,
                    )
                else:
                    self.message_user(
                        request,
                        "Successfully hard deleted %(count)d %(items)s." % {
                            "count": changed,
                            "items": model_ngettext(self.opts, requested)
                        },
                        messages.SUCCESS,
                    )
            else:
                self.message_user(
                    request,
                    "No permission for hard delete. Execute soft delete first.",
                    messages.ERROR
                )
            return None
        if queryset.count() == 0:
            self.message_user(
                request,
                "No permission for hard delete. Execute soft delete first.",
                messages.ERROR
            )
            return None

        opts = self.model._meta
        if len(original_queryset) == 1:
            objects_name = force_text(opts.verbose_name)
        else:
            objects_name = force_text(opts.verbose_name_plural)
        title = "Are you sure?"

        deletable_objects, model_count, perms_needed, protected = self.get_deleted_objects(queryset, request)

        context = {
            'title': title,
            'objects_name': objects_name,
            'queryset': queryset,
            'original_queryset': original_queryset,
            'opts': opts,
            'app_label': opts.app_label,
            'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
            'model_count': dict(model_count).items(),
            'deletable_objects': [deletable_objects],
            'perms_lacking': perms_needed,
            'protected': protected,
            'media': self.media,
        }

        return TemplateResponse(
            request,
            self.hard_delete_template,
            context,
        )

    hard_delete_selected.short_description = "Hard delete selected %(verbose_name_plural)s."


def many_2_many_field_to_html_links(obj: models.Model, field_name: str) -> str or None:
    if obj._meta and obj._meta.get_field(field_name):
        m2m_objects_list = ", ".join(
            [
                format_html(
                    "<a href='{}' class='changelink' target='_blank'>{}</a>",
                    reverse(
                        'admin:{}_{}_change'.format(m2m_object._meta.app_label,
                                                    m2m_object._meta.model_name),
                        args=[m2m_object.id]
                    ),
                    m2m_object.__str__()
                )
                for m2m_object in getattr(obj, field_name).all()
            ]
        )
        return format_html(m2m_objects_list)
    return None
