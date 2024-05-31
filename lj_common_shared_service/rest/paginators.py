from __future__ import unicode_literals

__author__ = 'David Baum'

import hashlib
import urllib.parse
from collections import OrderedDict

from django.core.cache import cache
from rest_framework.pagination import LimitOffsetPagination, PageNumberPagination
from rest_framework.response import Response

CACHE_TIMEOUT = 3600
BASE_PARAMS_TO_EXCLUDE = ["is_pagination", "limit", "offset"]


class LJSmallLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 10
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_limit = None

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('count', self.count),
            ('results', data)
        ]))


class LJMediumLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 50
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_limit = None


class LJLargeLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 500
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_limit = None


class LJDataOnlyPageNumberPagination(LimitOffsetPagination):
    default_limit = 10
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_limit = None
    
    def get_cache_key(self, request):
        """
        Generate a cache key based on the request parameters.

        Args:
            request (Request): The request object containing query parameters.

        Returns:
            str: The cache key generated based on the request parameters.

        Note:
            This method encodes the query parameters in the request, filters out
            certain parameters, sorts them, and generates a SHA256 hash of the
            resulting query string to create a unique cache key.
        """
        filtered_params = [(k, v) for k, v in request.query_params.items() if k not in BASE_PARAMS_TO_EXCLUDE]
        query_string = urllib.parse.urlencode(sorted(filtered_params))
        return hashlib.sha256(query_string.encode()).hexdigest()

    
    def paginate_queryset(self, queryset, request, view=None):
        """
        Paginate the queryset according to the request parameters.

        Args:
            queryset (QuerySet): The queryset to paginate.
            request (Request): The request object containing pagination parameters.
            view (APIView): The view object associated with the pagination (default: None).

        Returns:
            list: A list containing the paginated queryset.

        Note:
            This method calculates pagination parameters such as limit and offset based on the request,
            retrieves or caches the total count of the queryset, sets pagination attributes, and returns
            the paginated queryset.
        """
        self.limit = self.get_limit(request)
        if self.limit is None:
            return None

        count_cache_key = self.get_cache_key(request)
        self.count = cache.get(count_cache_key)

        if self.count is None:
            # FOR TESTING REASONS
            # self.count = self.get_count(queryset)
            self.count = 1000
            cache.set(count_cache_key, self.count, timeout=CACHE_TIMEOUT)

        self.offset = self.get_offset(request)
        self.request = request
        if self.count > self.limit and self.template is not None:
            self.display_page_controls = True

        if self.count == 0 or self.offset > self.count:
            return []
        return list(queryset[self.offset:self.offset + self.limit])

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('count', self.count),
            ('results', data)
        ]))


class LJInfinityScrollPagination(LimitOffsetPagination):
    default_limit = 25
    max_limit = 100
    
    def paginate_queryset(self, queryset, request, view=None):
        self.limit = self.get_limit(request)
        if self.limit is None:
            return None

        self.offset = self.get_offset(request)
        self.request = request

        paginated_queryset = list(queryset[self.offset:self.offset + self.limit])
        return paginated_queryset

    def get_paginated_response(self, data):
        count = self.offset + len(data)
        has_more = len(data) >= self.limit
        if has_more:
            data = data[:self.limit - 1]
        return Response(OrderedDict([
            ('count', count),
            ('results', data),
            ('has_more', has_more)
        ]))
