import hashlib
from django import template

register = template.Library()

@register.filter(name='md5')
def md5_hash(value):
    """
    Generate MD5 hash for the given value (typically email)
    """
    if not value:
        return ''
    return hashlib.md5(str(value).encode('utf-8').lower()).hexdigest()

@register.filter(name='divide_by')
def divide_by(value, arg):
    """
    Divide the value by the argument
    """
    try:
        return float(value) / float(arg) if arg else 0
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter(name='multiply_by')
def multiply_by(value, arg):
    """
    Multiply the value by the argument
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0
