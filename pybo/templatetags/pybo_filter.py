import markdown
import nh3
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def sub(value, arg):
    return value - arg

@register.filter
def mark(value):
    extensions = ["nl2br", "fenced_code"]
    html = markdown.markdown(value, extensions=extensions)
    clean_html = nh3.clean(html)
    return mark_safe(clean_html)