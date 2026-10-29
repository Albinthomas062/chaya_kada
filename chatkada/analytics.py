"""
Analytics utility functions for tracking user events
"""
from django.utils import timezone
from .models import AnalyticsEvent


def track_event(event_type, user=None, metadata_text=None, metadata_int=None, related_user=None, related_room=None):
    """
    Track an analytics event.
    
    Args:
        event_type: One of the EVENT_TYPES from AnalyticsEvent model
        user: The User object (can be None for anonymous events)
        metadata_text: Optional text metadata
        metadata_int: Optional integer metadata (coins, duration, etc.)
        related_user: Optional related User object
        related_room: Optional related ChatRoom object
    """
    try:
        AnalyticsEvent.objects.create(
            user=user,
            event_type=event_type,
            metadata_text=metadata_text,
            metadata_int=metadata_int,
            related_user=related_user,
            related_room=related_room
        )
    except Exception as e:
        # Silently fail - analytics shouldn't break core functionality
        print(f"Analytics tracking error: {e}")


# Convenience functions for common events
def track_signup(user):
    track_event('signup', user=user)


def track_login(user):
    track_event('login', user=user)


def track_stranger_search_started(user):
    track_event('stranger_search_started', user=user)


def track_stranger_match_made(user, matched_with_user, room):
    track_event('stranger_match_made', user=user, related_user=matched_with_user, related_room=room)


def track_message_sent(user, room):
    track_event('message_sent', user=user, related_room=room)


def track_bench_created(user, room):
    track_event('bench_created', user=user, related_room=room)


def track_bench_joined(user, room):
    track_event('bench_joined', user=user, related_room=room)


def track_theatre_created(user, room):
    track_event('theatre_created', user=user, related_room=room)


def track_theatre_joined(user, room):
    track_event('theatre_joined', user=user, related_room=room)


def track_item_bought(user, item_name, coins_spent):
    track_event('item_bought', user=user, metadata_text=item_name, metadata_int=coins_spent)


def track_item_shared(user, item_name, room):
    track_event('item_shared', user=user, metadata_text=item_name, related_room=room)


def track_challenge_claimed(user, challenge_type, coins_earned):
    track_event('challenge_claimed', user=user, metadata_text=challenge_type, metadata_int=coins_earned)
