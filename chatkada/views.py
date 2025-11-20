from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Q, Count, Sum
from django.db import transaction
from django.urls import reverse
from datetime import date, timedelta
from .models import (
    Item, Purchase, ChatMessage, UserProfile, ChatRoom, 
    BenchInvite, DailyChallenge, CoinTransaction, UserChatHistory,
    StrangerChatQueue
)
from .forms import SimpleUserCreationForm
import json
import uuid
# views.py
from django.http import HttpResponse
from django.contrib.auth.models import User

def home(request):
    return render(request, 'home.html')

def register(request):
    if request.method == 'POST':
        form = SimpleUserCreationForm(request.POST)
        if form.is_valid():
            try:
                # Create user with custom form
                user = form.save()
                username = form.cleaned_data.get('username')
                password = form.cleaned_data.get('password1')
                
                print(f"User created: {username}")  # Debug
                
                # Ensure UserProfile exists
                profile, created = UserProfile.objects.get_or_create(
                    user=user,
                    defaults={'coins': 100, 'avatar': '☕'}
                )
                
                print(f"Profile created: {created}")  # Debug
                
                # Authenticate and login immediately
                user = authenticate(username=username, password=password)
                if user is not None:
                    login(request, user)
                    messages.success(request, 
                        f'Welcome to Chaya Kada, {username}! You got 100 free coins! ☕')
                    return redirect('kada')
                else:
                    messages.error(request, 'Registration successful but login failed. Please try logging in.')
                    return redirect('login')
                    
            except Exception as e:
                print(f"Registration error: {e}")  # Debug
                messages.error(request, f'Registration failed: {str(e)}')
        else:
            # Show form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{error}')
    else:
        form = SimpleUserCreationForm()
    
    return render(request, 'registration/register.html', {'form': form})

@login_required
def custom_logout(request):
    username = request.user.username
    logout(request)
    messages.success(request, f'Goodbye {username}! You have been logged out successfully.')
    return redirect('home')

@login_required
def kada(request):
    items = Item.objects.filter(available=True)
    chai_items = items.filter(category='chai')
    snack_items = items.filter(category='snacks')
    sweet_items = items.filter(category='sweets')
    
    context = {
        'chai_items': chai_items,
        'snack_items': snack_items,
        'sweet_items': sweet_items,
        'user_coins': request.user.userprofile.coins
    }
    return render(request, 'kada.html', context)

@login_required
def profile(request):
    purchases = Purchase.objects.filter(user=request.user)[:10]
    return render(request, 'profile.html', {'purchases': purchases})


@login_required
def check_daily_login(request):
    """Check and reward daily login bonus"""
    profile = request.user.userprofile
    today = date.today()
    
    # Check if user already got login bonus today
    if profile.last_login_date != today:
        # Award daily login bonus
        coins_earned = 25
        profile.coins += coins_earned
        profile.total_coins_earned += coins_earned
        profile.last_login_date = today
        
        # Update streak
        if profile.last_login_date == today - timedelta(days=1):
            profile.login_streak += 1
        else:
            profile.login_streak = 1
        
        profile.save()
        
        # Record challenge completion
        DailyChallenge.objects.get_or_create(
            user=request.user,
            challenge_type='daily_login',
            completed_date=today,
            defaults={'coins_earned': coins_earned}
        )
        
        # Record transaction
        CoinTransaction.objects.create(
            user=request.user,
            amount=coins_earned,
            transaction_type='daily_login',
            description=f'Daily login bonus - Day {profile.login_streak}'
        )
        
        return JsonResponse({
            'success': True,
            'coins_earned': coins_earned,
            'total_coins': profile.coins,
            'streak': profile.login_streak,
            'message': f'Daily login bonus: +{coins_earned} coins! 🎉'
        })
    
    return JsonResponse({
        'success': False,
        'message': 'Daily login bonus already claimed today'
    })

@login_required
@csrf_exempt
def record_chat_friend(request):
    """Record when user chats with a new stranger"""
    if request.method == 'POST':
        data = json.loads(request.body)
        friend_username = data.get('friend_username')
        
        try:
            friend = User.objects.get(username=friend_username)
            profile = request.user.userprofile
            today = date.today()
            
            # Reset daily count if it's a new day
            if profile.friends_challenge_date != today:
                profile.daily_friends_made = 0
                profile.friends_challenge_date = today
            
            # Record this chat interaction
            chat_record, created = UserChatHistory.objects.get_or_create(
                user=request.user,
                chatted_with=friend,
                chat_date=today
            )
            
            if created:
                profile.daily_friends_made += 1
                profile.save()
                
                # Check if challenge completed (5 new friends)
                if profile.daily_friends_made >= 5:
                    # Check if already rewarded today
                    challenge_exists = DailyChallenge.objects.filter(
                        user=request.user,
                        challenge_type='make_friends',
                        completed_date=today
                    ).exists()
                    
                    if not challenge_exists:
                        coins_earned = 60
                        profile.coins += coins_earned
                        profile.total_coins_earned += coins_earned
                        profile.save()
                        
                        # Record challenge completion
                        DailyChallenge.objects.create(
                            user=request.user,
                            challenge_type='make_friends',
                            completed_date=today,
                            coins_earned=coins_earned
                        )
                        
                        # Record transaction
                        CoinTransaction.objects.create(
                            user=request.user,
                            amount=coins_earned,
                            transaction_type='make_friends',
                            description='Made 5 new friends in stranger chat!'
                        )
                        
                        return JsonResponse({
                            'success': True,
                            'challenge_completed': True,
                            'coins_earned': coins_earned,
                            'total_coins': profile.coins,
                            'friends_count': profile.daily_friends_made,
                            'message': 'Challenge completed! Made 5 new friends: +60 coins! 🎉'
                        })
                
                return JsonResponse({
                    'success': True,
                    'friends_count': profile.daily_friends_made,
                    'message': f'New friend added! Progress: {profile.daily_friends_made}/5'
                })
            
            return JsonResponse({
                'success': True,
                'friends_count': profile.daily_friends_made,
                'message': 'Already chatted with this friend today'
            })
            
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Friend not found'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})

@login_required
def coin_center(request):
    """Dedicated coin management and challenge center"""
    profile = request.user.userprofile
    today = date.today()
    
    # Get today's challenges status
    daily_login_completed = DailyChallenge.objects.filter(
        user=request.user,
        challenge_type='daily_login',
        completed_date=today
    ).exists()
    
    friends_challenge_completed = DailyChallenge.objects.filter(
        user=request.user,
        challenge_type='make_friends',
        completed_date=today
    ).exists()
    
    # Reset daily friends count if new day
    if profile.friends_challenge_date != today:
        profile.daily_friends_made = 0
        profile.friends_challenge_date = today
        profile.save()
    
    # Weekly coin summary (last 7 days)
    week_ago = today - timedelta(days=7)
    weekly_transactions = CoinTransaction.objects.filter(
        user=request.user,
        timestamp__gte=week_ago,
        amount__gt=0  # Only positive transactions
    )
    
    weekly_summary = weekly_transactions.values('transaction_type').annotate(
        total_coins=Sum('amount'),
        count=Count('id')
    )
    
    # Recent transactions (last 10)
    recent_transactions = CoinTransaction.objects.filter(
        user=request.user
    )[:10]
    
    # Daily progress this week
    daily_progress = []
    for i in range(7):
        day = today - timedelta(days=i)
        day_transactions = CoinTransaction.objects.filter(
            user=request.user,
            timestamp__date=day,
            amount__gt=0
        ).aggregate(total=Sum('amount'))
        
        daily_progress.append({
            'date': day,
            'coins': day_transactions['total'] or 0
        })
    
    daily_progress.reverse()  # Show oldest to newest
    
    context = {
        'profile': profile,
        'daily_login_completed': daily_login_completed,
        'friends_challenge_completed': friends_challenge_completed,
        'friends_progress': profile.daily_friends_made,
        'weekly_summary': weekly_summary,
        'recent_transactions': recent_transactions,
        'daily_progress': daily_progress,
        'login_streak': profile.login_streak
    }
    
    return render(request, 'coin_center.html', context)

@login_required
def get_coin_progress(request):
    """API endpoint for coin progress (for navigation bar)"""
    profile = request.user.userprofile
    today = date.today()
    
    # Check challenge status
    daily_login_completed = DailyChallenge.objects.filter(
        user=request.user,
        challenge_type='daily_login',
        completed_date=today
    ).exists()
    
    friends_challenge_completed = DailyChallenge.objects.filter(
        user=request.user,
        challenge_type='make_friends',
        completed_date=today
    ).exists()
    
    # Reset friends count if new day
    if profile.friends_challenge_date != today:
        profile.daily_friends_made = 0
        profile.friends_challenge_date = today
        profile.save()
    
    return JsonResponse({
        'total_coins': profile.coins,
        'daily_login_completed': daily_login_completed,
        'friends_progress': profile.daily_friends_made,
        'friends_challenge_completed': friends_challenge_completed,
        'login_streak': profile.login_streak
    })

@login_required
@csrf_exempt
def buy_item(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        item_id = data.get('item_id')
        quantity = data.get('quantity', 1)
        
        try:
            item = Item.objects.get(id=item_id)
            user_profile = request.user.userprofile
            total_price = item.price * quantity
            
            if user_profile.coins >= total_price:
                user_profile.coins -= total_price
                user_profile.save()
                
                Purchase.objects.create(
                    user=request.user,
                    item=item,
                    quantity=quantity,
                    total_price=total_price
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'Enjoyed {item.name}! {item.emoji}',
                    'coins': user_profile.coins
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Not enough coins!'
                })
        except Item.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Item not found!'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})

# ========== NEW ADVANCED CHAT FEATURES ==========

@login_required
def find_chat(request):
    """Find a chat room or create a private bench"""
    if request.method == 'POST':
        chat_type = request.POST.get('chat_type', 'stranger')
        
        if chat_type == 'stranger':
            # First, check if user already has an active stranger chat
            existing_stranger_chat = ChatRoom.objects.filter(
                room_type='stranger',
                participants=request.user,
                is_active=True
            ).first()
            
            if existing_stranger_chat:
                # User already has a stranger chat, redirect to it
                return redirect('chat_room', room_id=existing_stranger_chat.room_id)
            
            # Find an available stranger chat room
            available_room = ChatRoom.objects.filter(
                room_type='stranger',
                is_active=True
            ).annotate(
                participant_count=Count('participants')
            ).filter(
                participant_count__lt=4
            ).exclude(
                participants=request.user
            ).first()
            
            if available_room:
                available_room.participants.add(request.user)
                ChatMessage.objects.create(
                    room=available_room,
                    user=request.user,
                    message_type='system',
                    content=f"{request.user.username} joined the chat"
                )
                return redirect('chat_room', room_id=available_room.room_id)
            else:
                # Create new stranger room
                new_room = ChatRoom.objects.create(
                    name=f"Stranger Chat {timezone.now().strftime('%H:%M')}",
                    room_type='stranger',
                    created_by=request.user,
                    expires_at=timezone.now() + timedelta(hours=1)  # Add expiration
                )
                new_room.participants.add(request.user)
                return redirect('chat_room', room_id=new_room.room_id)
        
        elif chat_type == 'private_bench':
            bench_name = request.POST.get('bench_name', '').strip()
            
            if not bench_name:
                messages.error(request, 'Please enter a bench name.')
                return redirect('find_chat')
            
            # Create private bench
            new_room = ChatRoom.objects.create(
                name=f"Private Bench: {bench_name}",
                bench_name=bench_name,
                room_type='private_bench',
                created_by=request.user
            )
            new_room.participants.add(request.user)
            
            messages.success(request, f'Private bench "{bench_name}" created successfully!')
            return redirect('chat_room', room_id=new_room.room_id)
    
    # Get user's active benches (private benches)
    user_benches = ChatRoom.objects.filter(
        created_by=request.user,
        room_type='private_bench',
        is_active=True
    )
    
    # Get user's active stranger chats
    user_stranger_chats = ChatRoom.objects.filter(
        participants=request.user,
        room_type='stranger',
        is_active=True,
        created_at__gte=timezone.now() - timedelta(hours=1)  # Only show chats from last hour
    ).exclude(created_by=request.user)
    
    # Get user's created stranger chats
    user_created_stranger_chats = ChatRoom.objects.filter(
        created_by=request.user,
        room_type='stranger',
        is_active=True,
        created_at__gte=timezone.now() - timedelta(hours=1)  # Only show chats from last hour
    )
    
    # Combine all user's stranger chats
    all_user_stranger_chats = user_stranger_chats.union(user_created_stranger_chats)
    
    return render(request, 'find_chat.html', {
        'user_benches': user_benches,
        'user_stranger_chats': all_user_stranger_chats
    })

@login_required
def chat_room(request, room_id):
    """Main chat room view"""
    room = get_object_or_404(ChatRoom, room_id=room_id, is_active=True)
    
    # Check if user is participant
    if request.user not in room.participants.all():
        messages.error(request, 'You are not a participant in this room.')
        return redirect('find_chat')
    
    # Clean up expired messages
    ChatMessage.objects.filter(
        room=room,
        expires_at__lt=timezone.now()
    ).update(is_deleted=True)
    
    # Get non-expired messages
    chat_messages = ChatMessage.objects.filter(
        room=room,
        is_deleted=False,
        expires_at__gt=timezone.now()
    ).select_related('user', 'shared_item').order_by('timestamp')[:50]
    
    # Get shareable items user has purchased
    shareable_items = Purchase.objects.filter(
        user=request.user,
        item__can_be_shared=True
    ).select_related('item')
    
    # Get invite link if user is room creator and it's a private bench
    invite_link = None
    if room.created_by == request.user and room.room_type == 'private_bench':
        active_invite = BenchInvite.objects.filter(
            room=room,
            status='active'
        ).first()
        if active_invite and active_invite.is_valid():
            invite_link = request.build_absolute_uri(
                reverse('join_bench', kwargs={'invite_code': active_invite.invite_code})
            )
    
    # Calculate time remaining for stranger chats
    time_remaining = None
    if room.room_type == 'stranger':
        time_remaining = timezone.now() + timedelta(hours=1) - room.created_at
        if time_remaining.total_seconds() <= 0:
            time_remaining = None
    
    return render(request, 'chat_room.html', {
        'room': room,
        'messages': chat_messages,
        'shareable_items': shareable_items,
        'room_id': str(room_id),
        'invite_link': invite_link,
        'is_room_creator': room.created_by == request.user,
        'time_remaining': time_remaining
    })
@login_required
@csrf_exempt
def send_chat_message(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            room_id = data.get('room_id')
            content = data.get('content', '').strip()
            message_type = data.get('message_type', 'text')
            shared_item_id = data.get('shared_item_id')
            
            if not content and message_type == 'text':
                return JsonResponse({'success': False, 'error': 'Message cannot be empty'})
            
            room = get_object_or_404(ChatRoom, room_id=room_id)
            
            # Check if user is in the room
            if request.user not in room.participants.all():
                return JsonResponse({'success': False, 'error': 'You are not in this chat room'})
            
            # Handle item sharing
            if message_type == 'shared_item' and shared_item_id:
                return handle_item_sharing(request, room, shared_item_id)
            
            # Create regular text message
            message = ChatMessage.objects.create(
                user=request.user,
                room=room,
                content=content,
                message_type=message_type
            )
            
            return JsonResponse({
                'success': True,
                'message': {
                    'id': message.id,
                    'user': message.user.username,
                    'content': message.content,
                    'message_type': message.message_type,
                    'timestamp': message.timestamp.isoformat(),
                }
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

def handle_item_sharing(request, room, shared_item_id):
    """Handle sharing items from user's purchases"""
    try:
        # Find a purchase with remaining quantity for this item
        purchase = Purchase.objects.filter(
            user=request.user,
            item_id=shared_item_id,
            remaining_quantity__gt=0
        ).first()
        
        if not purchase:
            return JsonResponse({
                'success': False, 
                'error': 'You don\'t have this item to share or you\'ve used all of them'
            })
        
        # Share the item (decreases remaining_quantity)
        if purchase.share_item():
            # Create chat message for shared item
            message = ChatMessage.objects.create(
                user=request.user,
                room=room,
                content=f"shared {purchase.item.name}",
                message_type='shared_item',
                shared_item=purchase.item,
                shared_purchase=purchase
            )
            
            return JsonResponse({
                'success': True,
                'message': {
                    'id': message.id,
                    'user': message.user.username,
                    'content': f"shared {purchase.item.name} {purchase.item.emoji}",
                    'message_type': 'shared_item',
                    'shared_item': {
                        'name': purchase.item.name,
                        'emoji': purchase.item.emoji,
                        'description': purchase.item.description
                    },
                    'timestamp': message.timestamp.isoformat(),
                },
                'remaining_quantity': purchase.remaining_quantity
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Failed to share item'
            })
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def get_shareable_items(request):
    """Get user's purchasable items that can be shared"""
    purchases = Purchase.objects.filter(
        user=request.user,
        remaining_quantity__gt=0
    ).select_related('item')
    
    shareable_items = []
    for purchase in purchases:
        shareable_items.append({
            'id': purchase.item.id,
            'name': purchase.item.name,
            'emoji': purchase.item.emoji,
            'description': purchase.item.description,
            'remaining_quantity': purchase.remaining_quantity,
            'purchase_id': purchase.id
        })
    
    return JsonResponse({'shareable_items': shareable_items})

@login_required
def get_chat_messages(request, room_id):
    try:
        room = get_object_or_404(ChatRoom, room_id=room_id)
        
        # Check if user is in the room
        if request.user not in room.participants.all():
            return JsonResponse({'success': False, 'error': 'Access denied'})
        
        # Get non-deleted messages
        messages = ChatMessage.objects.filter(
            room=room,
            is_deleted=False
        ).select_related('user', 'shared_item').order_by('-timestamp')[:50]
        
        messages_data = []
        for msg in reversed(messages):
            message_data = {
                'id': msg.id,
                'user': msg.user.username,
                'content': msg.content,
                'message_type': msg.message_type,
                'timestamp': msg.timestamp.isoformat(),
            }
            
            # Add shared item data if applicable
            if msg.message_type == 'shared_item' and msg.shared_item:
                message_data['shared_item'] = {
                    'name': msg.shared_item.name,
                    'emoji': msg.shared_item.emoji,
                    'description': msg.shared_item.description
                }
            
            messages_data.append(message_data)
        
        return JsonResponse({
            'success': True,
            'messages': messages_data,
            'room_info': {
                'name': room.get_display_name(),
                'type': room.room_type,
                'participant_count': room.participants.count()
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def profile(request):
    # Get user's purchases with remaining quantities
    purchases = Purchase.objects.filter(
        user=request.user
    ).select_related('item').order_by('-timestamp')
    
    # Group purchases by item and sum quantities
    purchase_summary = {}
    for purchase in purchases:
        item_id = purchase.item.id
        if item_id not in purchase_summary:
            purchase_summary[item_id] = {
                'item': purchase.item,
                'total_purchased': 0,
                'total_remaining': 0,
                'total_shared': 0,
                'purchases': []
            }
        
        purchase_summary[item_id]['total_purchased'] += purchase.quantity
        purchase_summary[item_id]['total_remaining'] += purchase.remaining_quantity
        purchase_summary[item_id]['total_shared'] += (purchase.quantity - purchase.remaining_quantity)
        purchase_summary[item_id]['purchases'].append(purchase)
    
    context = {
        'purchases': purchases,
        'purchase_summary': purchase_summary.values()
    }
    return render(request, 'profile.html', context)

# Add cleanup view for manual cleanup
@login_required
def cleanup_old_messages(request):
    """Manual cleanup endpoint for admins"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Permission denied'})
    
    if request.method == 'POST':
        hours = int(request.POST.get('hours', 24))
        cutoff_time = timezone.now() - timedelta(hours=hours)
        
        # Delete old stranger chat messages
        deleted_count = ChatMessage.objects.filter(
            room__room_type='stranger',
            timestamp__lt=cutoff_time,
            is_deleted=False
        ).delete()[0]
        
        return JsonResponse({
            'success': True,
            'deleted_count': deleted_count,
            'message': f'Deleted {deleted_count} old stranger chat messages'
        })
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
def accept_invitation(request, invitation_id):
    """Accept a chat invitation"""
    invitation = get_object_or_404(
        BenchInvite, 
        invitation_id=invitation_id,
        recipient=request.user,
        status='pending'
    )
    
    if invitation.is_expired():
        invitation.status = 'expired'
        invitation.save()
        messages.error(request, 'This invitation has expired.')
        return redirect('find_chat')
    
    room = invitation.room
    
    if room.participants.count() >= room.max_users:
        messages.error(request, 'This chat room is full.')
        return redirect('find_chat')
    
    # Accept invitation
    invitation.status = 'accepted'
    invitation.save()
    
    # Add user to room
    room.participants.add(request.user)
    
    # Send system message
    ChatMessage.objects.create(
        room=room,
        user=request.user,
        message_type='system',
        content=f"{request.user.username} joined the chat"
    )
    
    messages.success(request, 'Invitation accepted! Welcome to the chat.')
    return redirect('chat_room', room_id=room.room_id)

@login_required
def decline_invitation(request, invitation_id):
    """Decline a chat invitation"""
    invitation = get_object_or_404(
        BenchInvite,
        invitation_id=invitation_id,
        recipient=request.user,
        status='pending'
    )
    
    invitation.status = 'declined'
    invitation.save()
    
    messages.info(request, 'Invitation declined.')
    return redirect('find_chat')

@login_required
def leave_chat(request, room_id):
    """Leave a chat room"""
    room = get_object_or_404(ChatRoom, room_id=room_id)
    
    if request.user in room.participants.all():
        room.participants.remove(request.user)
        
        # Send system message
        ChatMessage.objects.create(
            room=room,
            user=request.user,
            message_type='system',
            content=f"{request.user.username} left the chat"
        )
        
        # If room is empty, deactivate it
        if room.participants.count() == 0:
            room.is_active = False
            room.save()
    
    messages.info(request, 'You left the chat room.')
    return redirect('find_chat')

@login_required
def chat(request):
    """Legacy chat view - redirects to find_chat"""
    return redirect('find_chat')

@login_required
@csrf_exempt
def send_message(request):
    """Legacy send message - kept for backward compatibility"""
    return JsonResponse({'success': False, 'message': 'Please use the new chat system'})

@login_required
def get_messages(request):
    """Legacy get messages - kept for backward compatibility"""
    return JsonResponse({'success': False, 'message': 'Please use the new chat system'})

# ========== UTILITY VIEWS ==========

@login_required
def cleanup_expired_content(request):
    """Manual cleanup of expired content (for testing)"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'message': 'Not authorized'})
    
    # Delete expired messages
    expired_messages = ChatMessage.objects.filter(
        expires_at__lt=timezone.now(),
        is_deleted=False
    )
    
    deleted_count = expired_messages.count()
    expired_messages.update(is_deleted=True)
    
    # Delete empty rooms older than 1 hour
    empty_rooms = ChatRoom.objects.filter(
        participants__isnull=True,
        created_at__lt=timezone.now() - timedelta(hours=1)
    )
    
    rooms_deleted = empty_rooms.count()
    empty_rooms.delete()
    
    return JsonResponse({
        'success': True,
        'message': f'Cleaned up {deleted_count} expired messages and {rooms_deleted} empty rooms'
    })

@login_required
def toggle_chat_availability(request):
    """Toggle user's availability for chat invitations"""
    profile = request.user.userprofile
    profile.is_available_for_chat = not profile.is_available_for_chat
    profile.save()
    
    status = "available" if profile.is_available_for_chat else "unavailable"
    messages.success(request, f'Chat availability set to {status}.')
    
    return redirect('profile')
@login_required
def create_bench_invite(request, room_id):
    """Create an invite link for a private bench (placeholder)"""
    messages.info(request, 'Invite feature coming soon!')
    return redirect('find_chat')

@login_required
def join_bench(request, invite_code):
    """Join a private bench using invite code (placeholder)"""
    messages.info(request, 'Join via invite feature coming soon!')
    return redirect('find_chat')

@login_required
def accept_invitation(request, invitation_id):
    """Accept a chat invitation (placeholder)"""
    messages.info(request, 'Invitation feature coming soon!')
    return redirect('find_chat')

@login_required
def decline_invitation(request, invitation_id):
    """Decline a chat invitation (placeholder)"""
    messages.info(request, 'Invitation feature coming soon!')
    return redirect('find_chat')

@login_required
def toggle_chat_availability(request):
    """Toggle user's availability for chat invitations (placeholder)"""
    messages.info(request, 'Availability toggle feature coming soon!')
    return redirect('profile')

@login_required
def get_user_chat_rooms(request):
    """Return a JSON list of private benches / chat rooms the user belongs to."""
    rooms = (
        ChatRoom.objects
        .filter(participants=request.user, is_active=True)
        .values('room_id', 'bench_name', 'name', 'room_type')
    )
    return JsonResponse({'rooms': list(rooms)})

@login_required
def find_stranger_chat(request):
    """Enhanced stranger chat finder with online user detection"""
    if request.method == 'POST':
        action = request.POST.get('action', 'find_stranger')
        
        if action == 'find_stranger':
            return handle_stranger_chat_request(request)
        elif action == 'cancel_search':
            return cancel_stranger_search(request)
    
    # Get current search status
    in_queue = StrangerChatQueue.objects.filter(user=request.user).exists()
    
    # Get online users count (excluding current user)
    online_users_count = UserProfile.objects.filter(
        is_online=True,
        last_activity__gte=timezone.now() - timedelta(minutes=5)
    ).exclude(user=request.user).count()
    
    context = {
        'in_queue': in_queue,
        'online_users_count': online_users_count,
    }
    
    return render(request, 'find_chat.html', context)

def handle_stranger_chat_request(request):
    """Handle stranger chat matching with comprehensive error handling"""
    profile = request.user.userprofile
    profile.looking_for_stranger_chat = True
    profile.save()
    
    try:
        with transaction.atomic():
            # Clean up expired queue entries
            StrangerChatQueue.objects.filter(
                joined_at__lt=timezone.now() - timedelta(minutes=10)
            ).delete()
            
            # Check if user already in queue
            queue_entry, created = StrangerChatQueue.objects.get_or_create(
                user=request.user,
                defaults={'connection_attempts': 0}
            )
            
            if not created:
                queue_entry.connection_attempts += 1
                queue_entry.last_attempt = timezone.now()
                queue_entry.save()
            
            # Find available online users
            available_users = find_available_online_users(request.user)
            
            if not available_users:
                return handle_no_users_available(request, queue_entry)
            
            # Try to match with another user in queue
            matched_user = find_queue_match(request.user)
            
            if matched_user:
                return create_stranger_chat_room(request, matched_user)
            else:
                return wait_for_match(request, queue_entry, available_users)
                
    except Exception as e:
        return handle_connection_error(request, str(e))

def find_available_online_users(current_user):
    """Find users who are online and available for stranger chat"""
    return User.objects.filter(
        userprofile__is_online=True,
        userprofile__is_available_for_chat=True,
        userprofile__last_activity__gte=timezone.now() - timedelta(minutes=5)
    ).exclude(
        id=current_user.id
    ).exclude(
        # Exclude users already in active chats
        chat_rooms__room_type='stranger',
        chat_rooms__is_active=True
    )

def find_queue_match(current_user):
    """Find another user in the stranger chat queue to match with"""
    return StrangerChatQueue.objects.filter(
        joined_at__lt=timezone.now() - timedelta(seconds=30)  # Wait 30 seconds before matching
    ).exclude(user=current_user).first()

def create_stranger_chat_room(request, matched_user_queue):
    """Create a chat room for matched strangers"""
    matched_user = matched_user_queue.user
    
    # Create chat room
    chat_room = ChatRoom.objects.create(
        name=f"Stranger Chat {timezone.now().strftime('%H:%M')}",
        room_type='stranger',
        created_by=request.user,
        expires_at=timezone.now() + timedelta(hours=1)
    )
    
    # Add both users to the room
    chat_room.participants.add(request.user, matched_user)
    
    # Remove both users from queue
    StrangerChatQueue.objects.filter(
        user__in=[request.user, matched_user]
    ).delete()
    
    # Update profiles
    for user in [request.user, matched_user]:
        profile = user.userprofile
        profile.looking_for_stranger_chat = False
        profile.save()
    
    # Send system messages
    ChatMessage.objects.create(
        room=chat_room,
        user=request.user,
        message_type='system',
        content=f"Connected with {matched_user.username}! Say hello! 👋"
    )
    
    messages.success(request, f'Connected with a stranger! Enjoy your chat! ☕')
    return redirect('chat_room', room_id=chat_room.room_id)

def wait_for_match(request, queue_entry, available_users):
    """Handle waiting state when no immediate match is available"""
    wait_time = (timezone.now() - queue_entry.joined_at).total_seconds()
    
    if wait_time > 300:  # 5 minutes
        return handle_timeout(request, queue_entry)
    
    return JsonResponse({
        'status': 'waiting',
        'message': f'Looking for strangers... {len(available_users)} users online',
        'wait_time': int(wait_time),
        'online_count': len(available_users),
        'estimated_wait': '30-60 seconds'
    })

def handle_no_users_available(request, queue_entry):
    """Handle case when no users are available"""
    # Check if it's a connection issue or genuinely no users
    total_recent_users = User.objects.filter(
        last_login__gte=timezone.now() - timedelta(hours=1)
    ).exclude(id=request.user.id).count()
    
    if total_recent_users == 0:
        # Truly no recent users
        return JsonResponse({
            'status': 'no_users',
            'message': 'No one else is online right now',
            'suggestion': 'Try creating a private bench and invite friends!',
            'action': 'create_bench'
        })
    else:
        # Users exist but might be connection issues
        return JsonResponse({
            'status': 'connection_issue',
            'message': 'Having trouble finding users. This might be a connection issue.',
            'suggestion': 'Please check your internet connection and try again',
            'action': 'retry',
            'retry_count': queue_entry.connection_attempts
        })

def handle_timeout(request, queue_entry):
    """Handle search timeout"""
    queue_entry.delete()
    
    profile = request.user.userprofile
    profile.looking_for_stranger_chat = False
    profile.save()
    
    return JsonResponse({
        'status': 'timeout',
        'message': 'Search timed out. No strangers found.',
        'suggestion': 'Try again or create a private bench',
        'action': 'timeout'
    })

def handle_connection_error(request, error_message):
    """Handle connection errors"""
    return JsonResponse({
        'status': 'error',
        'message': 'Connection error occurred',
        'error': error_message,
        'suggestion': 'Please check your internet connection',
        'action': 'error'
    })

@login_required
def cancel_stranger_search(request):
    """Cancel stranger chat search"""
    StrangerChatQueue.objects.filter(user=request.user).delete()
    
    profile = request.user.userprofile
    profile.looking_for_stranger_chat = False
    profile.save()
    
    messages.info(request, 'Search cancelled.')
    return redirect('find_chat')

@login_required
def check_match_status(request):
    """API endpoint to check if a match has been found"""
    try:
        queue_entry = StrangerChatQueue.objects.get(user=request.user)
        
        # Check if user has been matched (removed from queue but has active chat)
        active_chat = ChatRoom.objects.filter(
            participants=request.user,
            room_type='stranger',
            is_active=True,
            created_at__gte=queue_entry.joined_at
        ).first()
        
        if active_chat:
            return JsonResponse({
                'status': 'matched',
                'room_id': str(active_chat.room_id),
                'message': 'Match found! Redirecting to chat...'
            })
        
        # Still waiting
        wait_time = (timezone.now() - queue_entry.joined_at).total_seconds()
        online_count = find_available_online_users(request.user).count()
        
        if wait_time > 300:  # 5 minutes timeout
            return handle_timeout(request, queue_entry)
        
        return JsonResponse({
            'status': 'waiting',
            'wait_time': int(wait_time),
            'online_count': online_count,
            'message': f'Searching... {online_count} users online'
        })
        
    except StrangerChatQueue.DoesNotExist:
        return JsonResponse({
            'status': 'not_searching',
            'message': 'Not currently searching'
        })

@login_required
def get_online_status(request):
    from .models import UserProfile
    online_users = UserProfile.objects.filter(
        is_online=True,
        last_activity__gte=timezone.now() - timezone.timedelta(minutes=5)
    ).exclude(user=request.user).count()
    in_queue = False  # Alternatively, check StrangerChatQueue for the user
    return JsonResponse({
        "online_users": online_users,
        "in_queue": in_queue,
        "timestamp": timezone.now().isoformat(),
    })

#for custom admin dashboard
from .forms import ItemForm, AssignChallengeForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from django.contrib.admin.views.decorators import staff_member_required

def custom_admin_login(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('custom_admin_dashboard')
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_staff:
            login(request, user)
            return redirect('custom_admin_dashboard')
        messages.error(request, "Invalid credentials or not a staff user.")
    return render(request, 'custom_admin/admin_login.html')

@staff_member_required
def custom_admin_dashboard(request):
    return render(request, 'custom_admin/dashboard.html')

# ——— Items ———

@staff_member_required
def manage_items(request):
    items = Item.objects.all().order_by('category', 'name')
    return render(request, 'custom_admin/items.html', {"items": items})

@staff_member_required
def add_item(request):
    if request.method == "POST":
        form = ItemForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Item added!")
            return redirect('manage_items')
    else:
        form = ItemForm()
    return render(request, "custom_admin/item_form.html", {"form": form, "form_title": "Add Item"})

@staff_member_required
def edit_item(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    if request.method == "POST":
        form = ItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, "Item updated!")
            return redirect('manage_items')
    else:
        form = ItemForm(instance=item)
    return render(request, "custom_admin/item_form.html", {"form": form, "form_title": "Edit Item"})

@staff_member_required
def delete_item(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    if request.method == "POST":
        item.delete()
        messages.success(request, "Item deleted.")
        return redirect('manage_items')
    return render(request, "custom_admin/item_form.html", {"form": None, "form_title": "Delete Item", "item": item, "delete_confirm": True})

# ——— Daily Challenges ———

@staff_member_required
def manage_challenges(request):
    challenges = DailyChallenge.objects.order_by('-completed_date')[:50]
    return render(request, 'custom_admin/challenges.html', {"challenges": challenges})

@staff_member_required
def assign_challenge(request):
    if request.method == "POST":
        form = AssignChallengeForm(request.POST)
        if form.is_valid():
            challenge_type = form.cleaned_data["challenge_type"]
            coins_earned = form.cleaned_data["coins_earned"]
            today = timezone.now().date()
            created = 0
            for user in User.objects.all():
                challenges = DailyChallenge.objects.filter(user=user, challenge_type=challenge_type, completed_date=today)
                if not challenges.exists():
                    DailyChallenge.objects.create(
                        user=user,
                        challenge_type=challenge_type,
                        completed_date=today,
                        coins_earned=coins_earned,
                    )
                    created += 1
            messages.success(request, f"Assigned {challenge_type} to {created} users for today.")
            return redirect('manage_challenges')
    else:
        form = AssignChallengeForm()
    return render(request, "custom_admin/assign_challenges.html", {"form": form})
