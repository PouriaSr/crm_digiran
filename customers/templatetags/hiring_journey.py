from django import template
from accounts.permissions import has_permission
from crm.pagination import paginate

register = template.Library()


@register.inclusion_tag('customers/_hiring_journey.html', takes_context=True)
def hiring_journey(context, rec):
    request = context.get('request')
    if not request or not has_permission(request.user, 'customers.hiring'):
        return {}
    # The caller supplies an already authorized visit; never query another person's data.
    from customers.access import can_edit_card
    if not can_edit_card(request.user, rec.customer):
        return {}
    application = getattr(rec, 'hiring', None)
    sessions = referrals = None
    if application:
        sessions = getattr(application, 'session_history', None)
        if sessions is None:
            sessions = paginate(request, application.sessions.select_related(
                'interviewer', 'saved_by', 'first_saved_by', 'last_saved_by', 'last_edited_by', 'job_ad', 'invited_by'
            ).order_by('-round_number'), f'sessions_{rec.pk}_page')
        referrals = getattr(application, 'referral_history', None)
        if referrals is None:
            referrals = paginate(request, application.referrals.select_related(
                'from_user', 'to_user', 'actor').order_by('-created_at', '-pk'), f'referrals_{rec.pk}_page')
    return {'rec': rec, 'sessions': sessions, 'referrals': referrals, 'request': request}
