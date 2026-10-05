from django import template

from accounts.names import avatar_class as avatar_class_for
from accounts.names import display_name as display_name_for
from accounts.names import initials as initials_for

register = template.Library()


@register.filter
def display_name(user):
    return display_name_for(user)


@register.filter
def initials(user):
    return initials_for(user)


@register.filter
def avatar_class(user):
    return avatar_class_for(user)
