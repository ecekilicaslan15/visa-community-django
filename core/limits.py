from datetime import timedelta

from django.utils import timezone

from .models import Comment, OpeningReport, Reply

HOURLY_POST_LIMIT = 10
HOURLY_POST_MESSAGE = (
    "You've shared 10 posts in the last hour. Please wait a little before posting again."
)


def hourly_post_limit_reached(user):
    """True when this member already posted 10 comments, replies, or openings this hour."""
    since = timezone.now() - timedelta(hours=1)
    total = (
        Comment.objects.filter(user=user, created_at__gte=since).count()
        + Reply.objects.filter(user=user, created_at__gte=since).count()
        + OpeningReport.objects.filter(user=user, created_at__gte=since).count()
    )
    return total >= HOURLY_POST_LIMIT
