from django import template

register = template.Library()

@register.simple_tag(takes_context=True)
def active(context, prefix: str, mode: str = 'starts'):
    """Return 'active' when the current path matches the prefix.

    - mode 'exact': only when path equals prefix
    - mode 'starts': when path is the prefix or begins with prefix + '/'
    """
    request = context.get('request')
    if not request:
        return ''
    path = request.path.rstrip('/')
    px = prefix.rstrip('/')
    if not px:
        return ''
    if mode == 'exact':
        return 'active' if path == px else ''
    # default: starts-with but ensure segment boundary
    return 'active' if (path == px or path.startswith(px + '/')) else ''


