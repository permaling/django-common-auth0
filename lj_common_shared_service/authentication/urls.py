from __future__ import unicode_literals

__author__ = 'David Baum'

from django.conf.urls import url
from django.contrib import admin

urlpatterns = [
    url(r'^accounts/login/$', admin.site.login, name='login'),
]
