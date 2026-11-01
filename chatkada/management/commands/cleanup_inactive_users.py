from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from chatkada.models import UserProfile, StrangerChatQueue

class Command(BaseCommand):
    help = 'Clean up inactive users and expired queue entries'

    def handle(self, *args, **options):
        # Mark users as offline if inactive for more than 5 minutes
        inactive_threshold = timezone.now() - timedelta(minutes=5)
        inactive_count = UserProfile.objects.filter(
            last_activity__lt=inactive_threshold,
            is_online=True
        ).update(is_online=False, looking_for_stranger_chat=False)
        
        # Remove expired queue entries
        expired_queue = StrangerChatQueue.objects.filter(
            joined_at__lt=timezone.now() - timedelta(minutes=10)
        )
        expired_count = expired_queue.count()
        expired_queue.delete()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Cleaned up {inactive_count} inactive users and {expired_count} expired queue entries'
            )
        )
