from django.db.models.functions import Coalesce

from core import models


def update_opportunity_latest_followup(opportunity_id):
    if not opportunity_id:
        return None
    activity = (
        models.Activity.objects
        .filter(opportunity_id=opportunity_id)
        .annotate(order_time=Coalesce('due_at', 'created_at'))
        .order_by('-order_time', '-id')
        .first()
    )
    opportunity = models.Opportunity.objects.filter(id=opportunity_id).first()
    if not opportunity:
        return None
    if not activity:
        opportunity.latest_followup_at = None
        opportunity.latest_followup_note = None
        opportunity.save(update_fields=['latest_followup_at', 'latest_followup_note'])
        return None
    opportunity.latest_followup_at = activity.due_at or activity.created_at
    opportunity.latest_followup_note = activity.description or activity.subject
    opportunity.save(update_fields=['latest_followup_at', 'latest_followup_note'])
    return activity
