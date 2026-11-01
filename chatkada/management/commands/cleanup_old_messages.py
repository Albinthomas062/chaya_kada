from django.core.management.base import BaseCommand
from django.utils import timezone
from chatkada.models import ChatMessage
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Clean up expired chat messages from stranger chats'

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Messages older than this many hours will be deleted (default: 24)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )

    def handle(self, *args, **options):
        hours = options['hours']
        dry_run = options['dry_run']
        
        # Calculate cutoff time
        cutoff_time = timezone.now() - timezone.timedelta(hours=hours)
        
        # Get expired stranger chat messages
        expired_messages = ChatMessage.objects.filter(
            room__room_type='stranger',  # Only stranger chat messages
            timestamp__lt=cutoff_time,
            is_deleted=False
        )
        
        count = expired_messages.count()
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'DRY RUN: Would delete {count} expired stranger chat messages')
            )
            
            # Show sample messages that would be deleted
            sample_messages = expired_messages[:5]
            for msg in sample_messages:
                self.stdout.write(f'  - {msg.user.username}: {msg.content[:50]}... ({msg.timestamp})')
            
            if count > 5:
                self.stdout.write(f'  ... and {count - 5} more messages')
        else:
            # Actually delete the messages
            deleted_count = expired_messages.delete()[0]
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully deleted {deleted_count} expired stranger chat messages')
            )
            
            logger.info(f'Cleanup command deleted {deleted_count} expired stranger chat messages')
