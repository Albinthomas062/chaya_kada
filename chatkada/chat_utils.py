"""Helpers shared by chat views, templates and websocket consumers."""
from django.utils import dateformat, timezone

STRANGER_LABEL = 'Stranger'
SELF_LABEL = 'You'
TIME_FORMAT = 'g:i A'  # e.g. "9:05 PM" (Django date format)


def is_anonymous_room(room_or_type):
    room_type = getattr(room_or_type, 'room_type', room_or_type)
    return room_type == 'stranger'


def display_name(author, room_or_type, viewer):
    """Name to show `viewer` for a message written by `author`.

    Stranger chats are anonymous: the other side is only ever 'Stranger'
    and your own messages are 'You'. Benches/theatres show usernames.
    """
    author_id = getattr(author, 'id', author)
    viewer_id = getattr(viewer, 'id', viewer)
    if is_anonymous_room(room_or_type):
        return SELF_LABEL if author_id == viewer_id else STRANGER_LABEL
    return getattr(author, 'username', str(author))


def format_time(dt):
    """Format a datetime in the project TIME_ZONE (Asia/Kolkata)."""
    if dt is None:
        return ''
    if timezone.is_aware(dt):
        dt = timezone.localtime(dt)
    return dateformat.format(dt, TIME_FORMAT)


def iso_local(dt):
    """ISO-8601 string with the IST offset, e.g. 2026-11-01T21:05:00+05:30."""
    if dt is None:
        return ''
    if timezone.is_aware(dt):
        dt = timezone.localtime(dt)
    return dt.isoformat()
