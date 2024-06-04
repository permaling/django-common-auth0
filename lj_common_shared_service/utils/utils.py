from __future__ import unicode_literals

__author__ = 'David Baum'

import itertools, uuid
from typing import List

from django.conf import settings
from django.contrib.admin.utils import NestedObjects
from django.http import QueryDict
from django.templatetags.static import static
from django.db import router

from rest_framework.request import Request

from storages.backends.gcloud import GoogleCloudStorage

value_to_bool = lambda v: v.lower() in ("yes", "true", "t", "1", "y") if isinstance(v, str) else v in (1,)
value_to_int = lambda s: int(s) if s and s.isdigit() else 0


def validate_request_list_parameters(parameters: list or str):
    if isinstance(parameters, str):
        return [parameter.strip() for parameter in parameters.replace('"', '').split(',') if
                parameter.strip()]
    else:
        return [parameter.strip() for parameter in parameters if parameter.strip()]


def parse_request_list_parameter(request: Request, parameter_name: str) -> List[str]:
    parameter = request.data.get(parameter_name, [])
    if parameter and isinstance(parameter, str) and "," in parameter:
        request.data._mutable = True  # make QueryDict mutable to perform updates
        parsed_params = parameter.split(",")  # services are of form ["1,5,9"] now

        parameter = []
        for param in parsed_params:
            if param.startswith('"') and param.endswith('"'):
                param = param[1:]
                param = param[:-1]
            if param:
                parameter.append(param)

        request.data.setlist(parameter_name, parameter)  # set as a list in the request
        request.data._mutable = False  # make the QueryDict immutable again

    if isinstance(request.data, QueryDict):
        parameter = request.data.getlist(parameter_name, [])

    return validate_request_list_parameters(parameter)


def is_valid_uuid(val):
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, AttributeError):
        return False


def related_objects(obj):
    """ Return a generator to the objects that would be deleted if we delete "obj" (excluding obj) """

    collector = NestedObjects(using=router.db_for_write(obj))
    collector.collect([obj])

    def flatten(elem):
        if isinstance(elem, list):
            return itertools.chain.from_iterable(map(flatten, elem))
        elif obj != elem:
            return (elem,)
        return ()

    return flatten(collector.nested())


def get_static_url(path):
    try:
        if path.startswith('/'):
            path = path[1:]
        storage_module_split = settings.STATICFILES_STORAGE.split('.')
        storage_module = '.'.join(storage_module_split[:-1])
        module = __import__(storage_module, fromlist=[storage_module_split[-1]])
        if getattr(module, storage_module_split[-1]).__name__ is GoogleCloudStorage.__name__:
            return static(path)
        return '{0}{1}{2}'.format(settings.BASE_URL, settings.STATIC_URL, path)
    except Exception:
        return '{0}{1}{2}'.format(settings.BASE_URL, settings.STATIC_URL, path)


class Proxy(object):
    __slots__ = ["_obj", "__weakref__"]

    def __init__(self, obj):
        object.__setattr__(self, "_obj", obj)

    #
    # proxying (special cases)
    #
    def __getattribute__(self, name):
        return getattr(object.__getattribute__(self, "_obj"), name)

    def __delattr__(self, name):
        delattr(object.__getattribute__(self, "_obj"), name)

    def __setattr__(self, name, value):
        setattr(object.__getattribute__(self, "_obj"), name, value)

    def __nonzero__(self):
        return bool(object.__getattribute__(self, "_obj"))

    def __str__(self):
        return str(object.__getattribute__(self, "_obj"))

    def __repr__(self):
        return repr(object.__getattribute__(self, "_obj"))

    #
    # factories
    #
    _special_names = [
        '__abs__', '__add__', '__and__', '__call__', '__cmp__', '__coerce__',
        '__contains__', '__delitem__', '__delslice__', '__div__', '__divmod__',
        '__eq__', '__float__', '__floordiv__', '__ge__', '__getitem__',
        '__getslice__', '__gt__', '__hash__', '__hex__', '__iadd__', '__iand__',
        '__idiv__', '__idivmod__', '__ifloordiv__', '__ilshift__', '__imod__',
        '__imul__', '__int__', '__invert__', '__ior__', '__ipow__', '__irshift__',
        '__isub__', '__iter__', '__itruediv__', '__ixor__', '__le__', '__len__',
        '__long__', '__lshift__', '__lt__', '__mod__', '__mul__', '__ne__',
        '__neg__', '__oct__', '__or__', '__pos__', '__pow__', '__radd__',
        '__rand__', '__rdiv__', '__rdivmod__', '__reduce__', '__reduce_ex__',
        '__repr__', '__reversed__', '__rfloorfiv__', '__rlshift__', '__rmod__',
        '__rmul__', '__ror__', '__rpow__', '__rrshift__', '__rshift__', '__rsub__',
        '__rtruediv__', '__rxor__', '__setitem__', '__setslice__', '__sub__',
        '__truediv__', '__xor__', 'next',
    ]

    @classmethod
    def _create_class_proxy(cls, theclass):
        """creates a proxy for the given class"""

        def make_method(name):
            def method(self, *args, **kw):
                return getattr(object.__getattribute__(self, "_obj"), name)(*args, **kw)

            return method

        namespace = {}
        for name in cls._special_names:
            if hasattr(theclass, name):
                namespace[name] = make_method(name)
        return type("%s(%s)" % (cls.__name__, theclass.__name__), (cls,), namespace)

    def __new__(cls, obj, *args, **kwargs):
        """
        creates an proxy instance referencing `obj`. (obj, *args, **kwargs) are
        passed to this class' __init__, so deriving classes can define an
        __init__ method of their own.
        note: _class_proxy_cache is unique per deriving class (each deriving
        class must hold its own cache)
        """
        try:
            cache = cls.__dict__["_class_proxy_cache"]
        except KeyError:
            cls._class_proxy_cache = cache = {}
        try:
            theclass = cache[obj.__class__]
        except KeyError:
            cache[obj.__class__] = theclass = cls._create_class_proxy(obj.__class__)
        ins = object.__new__(theclass)
        theclass.__init__(ins, obj, *args, **kwargs)
        return ins
