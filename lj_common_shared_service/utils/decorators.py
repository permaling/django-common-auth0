from __future__ import unicode_literals

__author__ = 'David Baum'

from functools import wraps


def display(function=None, *, boolean=None, ordering=None, description=None, empty_value=None):
    """
    Conveniently add attributes to a display function::

        @admin.display(
            boolean=True,
            ordering='-publish_date',
            description='Is Published?',
        )
        def is_published(self, obj):
            return obj.publish_date is not None

    This is equivalent to setting some attributes (with the original, longer
    names) on the function directly::

        def is_published(self, obj):
            return obj.publish_date is not None
        is_published.boolean = True
        is_published.admin_order_field = '-publish_date'
        is_published.short_description = 'Is Published?'
    """

    def decorator(func):
        if boolean is not None and empty_value is not None:
            raise ValueError(
                'The boolean and empty_value arguments to the @display '
                'decorator are mutually exclusive.'
            )
        if boolean is not None:
            func.boolean = boolean
        if ordering is not None:
            func.admin_order_field = ordering
        if description is not None:
            func.short_description = description
        if empty_value is not None:
            func.empty_value_display = empty_value
        return func

    if function is None:
        return decorator
    else:
        return decorator(function)


def with_attrs(**func_attrs):
    """Set attributes in the decorated function, at definition time.
    Only accepts keyword arguments.
    E.g.:
        @with_attrs(counter=0, something='boing')
        def count_it():
            count_it.counter += 1
        print count_it.counter
        print count_it.something
        # Out:
        # >>> 0
        # >>> 'boing'
    """

    def attr_decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)

        for attr, value in func_attrs.items():
            setattr(wrapper, attr, value)

        return wrapper

    return attr_decorator
