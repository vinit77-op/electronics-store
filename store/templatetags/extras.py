from django import template
from django.db.models import Avg

register = template.Library()

@register.filter
def average(queryset, field_name):
    return queryset.aggregate(avg=Avg(field_name)).get('avg') or 0

@register.filter
def to(start, end):
    return range(start, end + 1)

@register.filter
def make_range(start, end=None):
    """Generates a range to loop over in templates"""
    if end is None:
        return range(start)
    return range(start, end)