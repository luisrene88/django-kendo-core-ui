"""
este templatetag fue tomado de la idea original de flopyforms

https://github.com/gregmuellegger/django-floppyforms

"""
from django import template


register = template.Library()


@register.filter
def istrue(value):
    return value is True


@register.filter
def isfalse(value):
    return value is False


@register.filter
def isnone(value):
    return value is None
