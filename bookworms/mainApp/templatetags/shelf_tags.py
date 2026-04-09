from django import template

register = template.Library()


@register.inclusion_tag("mainApp/includes/shelf_user_link.html", takes_context=True)
def shelf_user_link(context, account_user, css_class=None):
    """
    Посилання на «Моя полиця» для поточного користувача, інакше — публічна полиця за id.
    Використання: {% shelf_user_link some_user %} або {% shelf_user_link some_user css_class="..." %}
    """
    request = context.get("request")
    viewer = getattr(request, "user", None) if request else None
    return {
        "account_user": account_user,
        "viewer": viewer,
        "css_class": css_class or "",
    }
