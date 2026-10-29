from django.contrib import admin
from django.utils.html import format_html
from .models import (
    UserProfile, Item, Purchase, DailyChallenge, 
    ChatRoom, ChatMessage, CoinTransaction, 
    TheatreSeat, BenchInvite, AnalyticsEvent
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'coins', 'last_activity', 'is_online')
    search_fields = ('user__username', 'user__email')
    list_filter = ('last_activity',)
    readonly_fields = ('user', 'last_activity')
    
    def is_online(self, obj):
        from django.utils import timezone
        from datetime import timedelta
        if obj.last_activity:
            return obj.last_activity > timezone.now() - timedelta(minutes=5)
        return False
    is_online.boolean = True


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'available', 'sort_order', 'image_preview', 'emoji')
    list_filter = ('category', 'available', 'can_be_shared')
    search_fields = ('name', 'description')
    list_editable = ('available', 'sort_order')
    ordering = ('sort_order', 'category', 'name')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'category', 'emoji')
        }),
        ('Pricing & Availability', {
            'fields': ('price', 'available', 'can_be_shared', 'sort_order')
        }),
        ('Content', {
            'fields': ('description', 'image')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;" />', obj.image.url)
        return obj.emoji
    image_preview.short_description = 'Preview'


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('user', 'item', 'quantity', 'total_price', 'timestamp', 'shared_in_chat', 'remaining_quantity')
    list_filter = ('timestamp', 'shared_in_chat', 'item__category')
    search_fields = ('user__username', 'item__name')
    readonly_fields = ('user', 'item', 'quantity', 'total_price', 'timestamp')
    date_hierarchy = 'timestamp'


@admin.register(DailyChallenge)
class DailyChallengeAdmin(admin.ModelAdmin):
    list_display = ('user', 'challenge_type', 'completed_date', 'coins_earned')
    list_filter = ('challenge_type', 'completed_date')
    search_fields = ('user__username',)
    date_hierarchy = 'completed_date'
    readonly_fields = ('user', 'challenge_type', 'completed_date', 'coins_earned')


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ('name_or_type', 'room_type', 'is_active', 'participant_count', 'created_at', 'expires_at')
    list_filter = ('room_type', 'is_active', 'created_at')
    search_fields = ('name', 'room_id')
    readonly_fields = ('room_id', 'created_at', 'created_by')
    date_hierarchy = 'created_at'
    
    def name_or_type(self, obj):
        return obj.name if obj.name else f"{obj.room_type.title()} Room"
    name_or_type.short_description = 'Room'
    
    def participant_count(self, obj):
        return obj.participants.count()
    participant_count.short_description = 'Participants'


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('user', 'room_short', 'message_preview', 'timestamp')
    list_filter = ('timestamp', 'room__room_type')
    search_fields = ('user__username', 'content', 'room__name')
    readonly_fields = ('user', 'room', 'content', 'timestamp')
    date_hierarchy = 'timestamp'
    
    def room_short(self, obj):
        return str(obj.room)[:30]
    room_short.short_description = 'Room'
    
    def message_preview(self, obj):
        return obj.content[:50] if obj.content else '-'
    message_preview.short_description = 'Message'


@admin.register(CoinTransaction)
class CoinTransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'transaction_type', 'description_short', 'timestamp')
    list_filter = ('transaction_type', 'timestamp')
    search_fields = ('user__username', 'description')
    readonly_fields = ('user', 'amount', 'transaction_type', 'description', 'timestamp')
    date_hierarchy = 'timestamp'
    
    def description_short(self, obj):
        return obj.description[:50] if obj.description else '-'
    description_short.short_description = 'Description'


@admin.register(TheatreSeat)
class TheatreSeatAdmin(admin.ModelAdmin):
    list_display = ('room', 'seat_number', 'occupant')
    list_filter = ('room__name',)
    search_fields = ('room__name', 'occupant__username')
    readonly_fields = ('room',)


@admin.register(BenchInvite)
class BenchInviteAdmin(admin.ModelAdmin):
    list_display = ('invite_code', 'room', 'created_by', 'created_at', 'expires_at', 'status')
    list_filter = ('status', 'created_at')
    search_fields = ('invite_code', 'room__name', 'created_by__username')
    readonly_fields = ('invite_code', 'room', 'created_by', 'created_at')
    date_hierarchy = 'created_at'


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'user', 'metadata_preview', 'timestamp')
    list_filter = ('event_type', 'timestamp')
    search_fields = ('user__username', 'event_type', 'metadata')
    readonly_fields = ('event_type', 'user', 'timestamp')
    date_hierarchy = 'timestamp'
    
    def metadata_preview(self, obj):
        if obj.metadata:
            return str(obj.metadata)[:50]
        return '-'
    metadata_preview.short_description = 'Metadata'


# Customize admin site
admin.site.site_header = "Chaya Kada Administration"
admin.site.site_title = "Chaya Kada Admin"
admin.site.index_title = "Welcome to Chaya Kada Admin Panel"
