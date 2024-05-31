from __future__ import unicode_literals

__author__ = 'David Baum'

import re
from typing import List

from django.contrib.postgres.search import TrigramSimilarity
from django.db import models
from django.db.models.functions import Greatest


class SimilaritySearchManager(models.Manager):

    def trigram_filter(self, similarity_threshold: float = 0.5, *args, **kwargs):
        trigram_similarities: List[TrigramSimilarity] = []

        for key, value in kwargs.items():
            if isinstance(value, str):
                stripped_value = "".join(re.findall('([A-Za-z\d+]+)', value.strip()))
                trigram_similarities: List[TrigramSimilarity] = [
                    TrigramSimilarity(key, value),
                    TrigramSimilarity(key, stripped_value),
                    TrigramSimilarity(key, stripped_value.lower())
                ]
        if not trigram_similarities:
            return super(SimilaritySearchManager, self).get_queryset().none()

        similarity = Greatest(*trigram_similarities) if len(trigram_similarities) > 1 else trigram_similarities[0]

        objects = super(SimilaritySearchManager, self).get_queryset().annotate(
            similarity=similarity
        ).filter(
            similarity__gt=similarity_threshold
        ).order_by('-similarity')
        return objects
