from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
import uuid
import secrets

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    coins = models.IntegerField(default=100)
    avatar = models.CharField(max_length=50, default='☕')
    created_at = models.DateTimeField(auto_now_add=True)
    is_available_for_chat = models.BooleanField(default=True)
    last_activity = models.DateTimeField(null=True, blank=True)
    is_online = models.BooleanField(default=False)
    looking_for_stranger_chat = models.BooleanField(default=False)
    last_login_date = models.DateField(null=True, blank=True)
    login_streak = models.IntegerField(default=0)
    daily_friends_made = models.IntegerField(default=0)
    friends_challenge_date = models.DateField(null=True, blank=True)
    total_coins_earned = models.IntegerField(default=0)
    
    def is_currently_online(self):
        """Check if user is online (active within last 5 minutes)"""
        if not self.is_online:
            return False
        return timezone.now() - self.last_activity < timedelta(minutes=5)
    
    def update_activity(self):
        """Update user's last activity timestamp"""
        self.last_activity = timezone.now()
        self.is_online = True
        self.save(update_fields=['last_activity', 'is_online'])
    
    def __str__(self):
        return f"{self.user.username}'s Profile"

class StrangerChatQueue(models.Model):
    """Queue system for users looking for stranger chats"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)
    connection_attempts = models.IntegerField(default=0)
    last_attempt = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['joined_at']
    
    def is_expired(self):
        """Check if queue entry is expired (older than 10 minutes)"""
        return timezone.now() - self.joined_at > timedelta(minutes=10)

class DailyChallenge(models.Model):
    CHALLENGE_TYPES = [
        ('daily_login', 'Daily Login'),
        ('make_friends', 'Make 5 New Friends'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    challenge_type = models.CharField(max_length=20, choices=CHALLENGE_TYPES)
    completed_date = models.DateField()
    coins_earned = models.IntegerField()
    
    class Meta:
        unique_together = ['user', 'challenge_type', 'completed_date']
    
    def __str__(self):
        return f"{self.user.username} - {self.get_challenge_type_display()}"

class CoinTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('daily_login', 'Daily Login Bonus'),
        ('make_friends', 'Make 5 Friends Challenge'),
        ('purchase', 'Item Purchase'),
        ('signup_bonus', 'Signup Bonus'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.IntegerField()
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    description = models.CharField(max_length=200)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.user.username}: {self.amount} coins ({self.get_transaction_type_display()})"

class UserChatHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    chatted_with = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_chats')
    chat_date = models.DateField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'chatted_with', 'chat_date']
    
    def __str__(self):
        return f"{self.user.username} chatted with {self.chatted_with.username}"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if not hasattr(instance, 'userprofile'):
        UserProfile.objects.create(user=instance)
    instance.userprofile.save()
    
class ChatRoom(models.Model):
    ROOM_TYPES = [
        ('stranger', 'Stranger Chat'),
        ('private_bench', 'Private Bench'),
    ]
    
    room_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=100, default="Chat Room")
    bench_name = models.CharField(max_length=100, blank=True, null=True)
    room_type = models.CharField(max_length=15, choices=ROOM_TYPES, default='stranger')
    max_users = models.IntegerField(default=2)  # 2 for secure 1-on-1 stranger chats, can be overridden for benches
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)  # Add expiration field
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_rooms')
    participants = models.ManyToManyField(User, related_name='chat_rooms', blank=True)
    is_active = models.BooleanField(default=True)
    
    def save(self, *args, **kwargs):
        # Set expiration for stranger chats
        if self.room_type == 'stranger' and not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=1)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.bench_name or self.name} ({self.room_type})"
    
    @property
    def is_full(self):
        return self.participants.count() >= self.max_users
    
    @property
    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    def get_participant_count(self):
        return self.participants.count()
    
    def get_display_name(self):
        if self.room_type == 'stranger':
            return f"Stranger Chat (expires in {self.time_remaining})"
        return self.bench_name or self.name
    
    @property
    def time_remaining(self):
        if self.expires_at:
            remaining = self.expires_at - timezone.now()
            if remaining.total_seconds() > 0:
                minutes = int(remaining.total_seconds() / 60)
                return f"{minutes} min"
        return "Expired"

class BenchInvite(models.Model):
    INVITE_STATUS = [
        ('active', 'Active'),
        ('used', 'Used'),
        ('expired', 'Expired'),
    ]
    
    invite_code = models.CharField(max_length=32, unique=True, editable=False)
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='bench_invites')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_invites')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    max_uses = models.IntegerField(default=10)
    current_uses = models.IntegerField(default=0)
    status = models.CharField(max_length=10, choices=INVITE_STATUS, default='active')
    
    def save(self, *args, **kwargs):
        if not self.invite_code:
            self.invite_code = secrets.token_urlsafe(16)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)
    
    def is_expired(self):
        return timezone.now() > self.expires_at or self.current_uses >= self.max_uses
    
    def is_valid(self):
        return self.status == 'active' and not self.is_expired()
    
    def get_invite_url(self):
        from django.urls import reverse
        return reverse('join_bench', kwargs={'invite_code': self.invite_code})
    
    def __str__(self):
        return f"Invite to {self.room.bench_name} by {self.created_by.username}"


class Item(models.Model):
    CATEGORY_CHOICES = [
        ('chai', 'Chai'),
        ('snacks', 'Snacks'),
        ('sweets', 'Sweets'),
    ]
    
    name = models.CharField(max_length=100)
    price = models.IntegerField()
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)
    emoji = models.CharField(max_length=10, default='☕')
    description = models.TextField(blank=True)
    available = models.BooleanField(default=True)
    can_be_shared = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class Purchase(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    total_price = models.IntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)
    shared_in_chat = models.BooleanField(default=False)
    remaining_quantity = models.IntegerField(default=1)  # Track remaining items after sharing
    
    def __str__(self):
        return f"{self.user.username} bought {self.quantity}x {self.item.name}"
    
    def save(self, *args, **kwargs):
        # Set remaining_quantity to quantity on first save
        if not self.pk:
            self.remaining_quantity = self.quantity
        super().save(*args, **kwargs)
    
    def can_share(self):
        """Check if user has remaining items to share"""
        return self.remaining_quantity > 0
    
    def share_item(self):
        """Share one item and decrease remaining quantity"""
        if self.can_share():
            self.remaining_quantity -= 1
            self.shared_in_chat = True
            self.save()
            return True
        return False

class ChatMessage(models.Model):
    MESSAGE_TYPES = [
        ('text', 'Text Message'),
        ('shared_item', 'Shared Item'),
        ('system', 'System Message'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, default=1)  # Add default here
    content = models.TextField()
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    shared_item = models.ForeignKey(Item, on_delete=models.CASCADE, null=True, blank=True)
    shared_purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-timestamp']
    
    def save(self, *args, **kwargs):
        # Set expiration time for stranger chat messages (24 hours)
        if not self.expires_at and self.room.room_type == 'stranger':
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.user.username}: {self.content[:50]}"
