from __future__ import unicode_literals

__author__ = 'David Baum'

from django.contrib.postgres.search import TrigramSimilarity
from django.db import connection
from django.db.models import Case, When, Q, IntegerField


def get_mapped_model_db_names(model):
    fields = model._meta.local_fields
    db_field_names = dict()
    for f in fields:
        db_field_names[f.name] = f.name + '_id' if f.related_model is not None else f.name
    return db_field_names


def get_model_duplicates(model, unique_fields):
    mapped_table_names = get_mapped_model_db_names(model)
    table_column_names = []

    for unique_field in unique_fields:
        mapped_table_name = mapped_table_names.get(unique_field)
        if mapped_table_name:
            table_column_names.append(mapped_table_name)

    fields = ', '.join(f't."{f}"' for f in table_column_names)
    sql = f"""
            SELECT 
                UNNEST(ARRAY_REMOVE(dupe_ids, max_id))
            FROM (
                SELECT 
                    {fields},
                    MIN(t.id) AS max_id,
                    ARRAY_AGG(t.id) AS dupe_ids
                FROM
                    {model._meta.db_table} t
                GROUP BY
                    {fields}
                HAVING
                    COUNT(t.id) > 1
            ) a
        """
    with connection.cursor() as cursor:
        cursor.execute(sql)
        results = [row[0] for row in cursor.fetchall()]
    return model.objects.filter(pk__in=results)


def remove_model_duplicates(model, unique_fields):
    get_model_duplicates(model, unique_fields).delete()


def filter_by_trigram_similarity(qs, field_name, search_term, similarity_threshold=0.15):
    if not search_term:
        return qs

    similarity_name = f'{field_name}_similarity'
    strict_matching_name = f'{field_name}_strict_matching'

    qs = qs.annotate(
        **{
            strict_matching_name: Case(
                When(**{f'{field_name}__iexact': search_term, 'then': 3}),
                When(**{f'{field_name}__istartswith': search_term, 'then': 2}),
                When(**{f'{field_name}__icontains': search_term, 'then': 1}),
                output_field=IntegerField(),
                default=0
            )
        }
    )

    qs = qs.annotate(**{similarity_name: TrigramSimilarity(field_name, search_term)})

    qs = qs.filter(
        Q(**{f'{similarity_name}__gt': similarity_threshold}) |
        # following line is required if column's max length is big,
        # because in this case similarity can be less
        # than minimum similarity, but strict match exists
        Q(**{f'{strict_matching_name}__gt': 0})
    )

    return qs.order_by(
        f'-{strict_matching_name}',
        f'-{similarity_name}'
    )
