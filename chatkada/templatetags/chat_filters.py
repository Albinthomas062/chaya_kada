from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter(name='anonymous_username')
def anonymous_username(user, room):
    """
    Generate anonymous username for stranger chats.
    Returns real username for private benches.
    """
    if room.room_type == 'stranger':
        # Generate anonymous name based on user ID
        anonymous_names = [
            "Chai Lover", "Tea Enthusiast", "Kada Regular", "Stranger Friend",
            "Mystery Guest", "Anonymous Chatter", "Friendly Stranger", "Tea Buddy"
        ]
        # Use user ID to consistently assign the same anonymous name
        name_index = user.id % len(anonymous_names)
        return f"{anonymous_names[name_index]} #{user.id % 1000}"
    return user.username


@register.filter(name='is_stranger_chat')
def is_stranger_chat(room):
    """Check if room is a stranger chat"""
    return room.room_type == 'stranger'
