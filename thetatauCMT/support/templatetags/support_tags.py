from django import template

from ..services import VIEW_ONLY_MESSAGE, css_chapters

register = template.Library()


@register.simple_tag(takes_context=True)
def css_switcher(context):
    """What the Chapter Support Specialist bar needs, or None for everyone else."""
    request = context.get("request")
    if request is None or not getattr(request, "is_css", False):
        return None
    user = request.user
    return {
        "chapters": list(css_chapters(user)),
        "current": user.current_chapter,
        "view_only": getattr(request, "css_view_only", False),
        "message": VIEW_ONLY_MESSAGE,
    }
