from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.db.models import Q, Count, Sum
from django.db import transaction
from django.urls import reverse
from django.core.cache import cache
from datetime import date, timedelta
import time
from .models import (
    Item, Purchase, ChatMessage, UserProfile, ChatRoom, 
    BenchInvite, DailyChallenge, CoinTransaction, UserChatHistory,
    StrangerChatQueue
)
from .forms import SimpleUserCreationForm
import json
import uuid
# views.py
from django.http import HttpResponse, StreamingHttpResponse
from django.contrib.auth.models import User
import requests as req_lib
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Login rate limiting constants
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_DURATION = 900  # 15 minutes in seconds
MAX_PURCHASE_QUANTITY = 10


def get_client_ip(request):
    """Get client IP address from request (non-spoofable)"""
    # Use REMOTE_ADDR which is set by the web server
    # Daphne with --proxy-headers already sets REMOTE_ADDR from X-Forwarded-For
    # behind trusted proxies
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def get_login_lockout_key(username, ip_address):
    """Generate cache keys for login lockout tracking"""
    # Key both by IP and by username alone (to prevent distributed attacks)
    return [
        f'user_login_attempts_{username}_{ip_address}',
        f'user_login_attempts_user_{username}'
    ]


def check_user_login_attempts(username, ip_address):
    """Check if user is locked out due to failed login attempts"""
    keys = get_login_lockout_key(username, ip_address)
    
    # Check both IP-specific and username-only lockouts
    for key in keys:
        attempts_data = cache.get(key)
        if attempts_data:
            attempts, last_attempt = attempts_data
            if attempts >= MAX_LOGIN_ATTEMPTS:
                if time.time() - last_attempt < LOGIN_LOCKOUT_DURATION:
                    return False
    return True


def record_user_login_attempt(username, ip_address, success=False):
    """Record a user login attempt"""
    keys = get_login_lockout_key(username, ip_address)
    
    if success:
        # Clear both keys on success
        for key in keys:
            cache.delete(key)
    else:
        # Increment both counters
        for key in keys:
            attempts_data = cache.get(key)
            if attempts_data:
                attempts, _ = attempts_data
                cache.set(key, [attempts + 1, time.time()], LOGIN_LOCKOUT_DURATION)
            else:
                cache.set(key, [1, time.time()], LOGIN_LOCKOUT_DURATION)

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

def login_view(request):
    """Custom login view that checks for banned users and rate limits"""
    if request.user.is_authenticated:
        return redirect('kada')
    
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        ip_address = get_client_ip(request)
        
        # Check rate limiting
        if not check_user_login_attempts(username, ip_address):
            messages.error(
                request,
                f"Too many failed login attempts. Please try again in {LOGIN_LOCKOUT_DURATION // 60} minutes."
            )
            return render(request, 'registration/login.html', {'form': form})
        
        # Check if user exists and is banned (only after password verified to avoid enumeration)
        try:
            user_obj = User.objects.get(username=username)
            if not user_obj.is_active:
                # Verify password before showing ban message (prevent account enumeration)
                if user_obj.check_password(password):
                    messages.error(request, 'Your account has been banned. Please contact support.')
                    return render(request, 'registration/login.html', {'form': form})
                # If password wrong, fall through to generic error below
        except User.DoesNotExist:
            pass  # Will fail authentication below
        
        # Authenticate
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            record_user_login_attempt(username, ip_address, success=True)
            messages.success(request, f'Welcome back, {username}!')
            
            # Validate next_url to prevent open redirect
            next_url = request.GET.get('next', 'kada')
            if next_url and next_url != 'kada':
                if url_has_allowed_host_and_scheme(
                    url=next_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure()
                ):
                    return redirect(next_url)
            return redirect('kada')
        else:
            record_user_login_attempt(username, ip_address, success=False)
            messages.error(request, 'Invalid username or password.')
            return render(request, 'registration/login.html', {'form': form})
    else:
        form = AuthenticationForm()
    
    return render(request, 'registration/login.html', {'form': form})

@login_required
@ensure_csrf_cookie
def kada(request):
    items = Item.objects.filter(available=True).order_by('sort_order', 'category', 'name')
    chai_items = items.filter(category='chai')
    snack_items = items.filter(category='snacks')
    sweet_items = items.filter(category='sweets')
    gift_items = items.filter(category='gifts')  # Include gifts
    
    context = {
        'chai_items': chai_items,
        'snack_items': snack_items,
        'sweet_items': sweet_items,
        'gift_items': gift_items,
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
@require_POST
def buy_item(request):
    """Purchase an item from the shop with secure validation"""
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
        return JsonResponse({
            'success': False,
            'message': 'Invalid request format'
        }, status=400)
    if not isinstance(data, dict):
        return JsonResponse({
            'success': False,
            'message': 'Invalid request format'
        }, status=400)
    
    item_id = data.get('item_id')
    quantity = data.get('quantity', 1)
    
    # Validate item_id
    if not item_id:
        return JsonResponse({
            'success': False,
            'message': 'Item ID is required'
        }, status=400)
    
    # Validate quantity: must be a real integer between 1 and MAX_PURCHASE_QUANTITY.
    # Reject bools, floats (1.5 / 2.0), numeric strings with junk, etc. so the
    # client can never get fractional or negative totals.
    if isinstance(quantity, bool):
        quantity = None
    elif isinstance(quantity, str) and quantity.strip().isdigit():
        quantity = int(quantity.strip())
    if not isinstance(quantity, int) or isinstance(quantity, bool):
        return JsonResponse({
            'success': False,
            'message': 'Invalid quantity'
        }, status=400)
    if quantity < 1 or quantity > MAX_PURCHASE_QUANTITY:
        return JsonResponse({
            'success': False,
            'message': f'Quantity must be between 1 and {MAX_PURCHASE_QUANTITY}'
        }, status=400)

    # item_id must be an integer primary key
    if isinstance(item_id, bool) or not (isinstance(item_id, int) or (isinstance(item_id, str) and item_id.isdigit())):
        return JsonResponse({
            'success': False,
            'message': 'Invalid item ID'
        }, status=400)
    
    try:
        # Use atomic transaction with select_for_update to prevent race conditions
        with transaction.atomic():
            item = Item.objects.get(id=item_id)
            
            # Only allow available items
            if not item.available:
                return JsonResponse({
                    'success': False,
                    'message': 'Item is not available for purchase'
                }, status=400)
            
            # Lock user profile row to prevent concurrent purchases
            user_profile = UserProfile.objects.select_for_update().get(user=request.user)
            
            total_price = item.price * quantity
            
            # Check sufficient coins
            if total_price < 0 or user_profile.coins < total_price:
                return JsonResponse({
                    'success': False,
                    'message': 'Not enough coins!'
                }, status=400)
            
            # Deduct coins
            user_profile.coins -= total_price
            user_profile.save()
            
            # Record purchase
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
            
    except Item.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Item not found!'
        }, status=404)
    except UserProfile.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'User profile not found!'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred'
        }, status=500)

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
                bench_name=bench_name,  # Set bench_name field
                room_type='private_bench',
                created_by=request.user,
                max_users=4
            )
            new_room.participants.add(request.user)
            
            messages.success(request, f'Private bench "{bench_name}" created successfully!')
            return redirect('chat_room', room_id=new_room.room_id)
    
    # Get online users count (excluding current user)
    online_users_count = UserProfile.objects.filter(
        is_online=True,
        last_activity__gte=timezone.now() - timedelta(minutes=5)
    ).exclude(user=request.user).count()
    
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
        'user_stranger_chats': all_user_stranger_chats,
        'online_users_count': online_users_count,  # Add online count
    })

@login_required
def create_private_bench(request):
    """Create a new private bench"""
    if request.method == 'POST':
        bench_name = request.POST.get('bench_name', '').strip()
        
        if not bench_name:
            messages.error(request, 'Please enter a bench name.')
            return redirect('find_chat')
        
        if len(bench_name) > 50:
            messages.error(request, 'Bench name must be 50 characters or less.')
            return redirect('find_chat')
        
        new_room = ChatRoom.objects.create(
            name=f"Private Bench: {bench_name}",
            bench_name=bench_name,  # Set bench_name field
            room_type='private_bench',
            created_by=request.user,
            max_users=4
        )
        new_room.participants.add(request.user)
        messages.success(request, f'Private bench "{bench_name}" created successfully!')
        return redirect('chat_room', room_id=new_room.room_id)
    
    messages.error(request, 'Invalid request.')
    return redirect('find_chat')

@login_required
def chat_room(request, room_id):
    """Main chat room view"""
    room = get_object_or_404(ChatRoom, room_id=room_id, is_active=True)
    
    # Check if user is participant
    if request.user not in room.participants.all():
        messages.error(request, 'You are not a participant in this room.')
        return redirect('find_chat')
    
    # Clean up expired messages (only for stranger chats with expiry)
    ChatMessage.objects.filter(
        room=room,
        expires_at__lt=timezone.now(),
        expires_at__isnull=False
    ).update(is_deleted=True)
    
    # Get non-deleted messages
    # For stranger chats: only show non-expired messages
    # For benches/theatre: show all messages (no expiry)
    if room.room_type == 'stranger':
        chat_messages = ChatMessage.objects.filter(
            room=room,
            is_deleted=False,
            expires_at__gt=timezone.now()
        ).select_related('user', 'shared_item').order_by('timestamp')[:50]
    else:
        # Benches and theatre don't expire messages
        chat_messages = ChatMessage.objects.filter(
            room=room,
            is_deleted=False
        ).select_related('user', 'shared_item').order_by('timestamp')[:50]
    
    # Get shareable items user has purchased
    shareable_items = Purchase.objects.filter(
        user=request.user,
        item__can_be_shared=True
    ).select_related('item')
    
    # Get invite link if user is room creator and it's a private bench
    invite_link = None
    if room.created_by == request.user and room.room_type == 'private_bench':
        # Get existing active invite (don't create on every page load)
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
    """Create an invite link for a private bench"""
    try:
        room = get_object_or_404(ChatRoom, room_id=room_id)
        
        # Verify user is room creator
        if room.created_by != request.user:
            return JsonResponse({
                'success': False,
                'error': 'Only the room creator can create invites'
            })
        
        # Verify it's a private bench
        if room.room_type != 'private_bench':
            return JsonResponse({
                'success': False,
                'error': 'Invites can only be created for private benches'
            })
        
        if request.method == 'POST':
            max_uses = int(request.POST.get('max_uses', 10))
            
            # Handle expiration in minutes (new) or days (legacy)
            expires_in_minutes = request.POST.get('expires_in_minutes')
            
            if expires_in_minutes:
                expiration_delta = timedelta(minutes=int(expires_in_minutes))
            else:
                expires_in_days = int(request.POST.get('expires_in_days', 7))
                expiration_delta = timedelta(days=expires_in_days)
            
            # Create new invite
            invite = BenchInvite.objects.create(
                room=room,
                created_by=request.user,
                max_uses=max_uses,
                expires_at=timezone.now() + expiration_delta
            )
            
            # Build full URL using request for proper scheme and host
            invite_url = request.build_absolute_uri(
                reverse('join_bench', kwargs={'invite_code': invite.invite_code})
            )
            
            return JsonResponse({
                'success': True,
                'invite_url': invite_url,
                'invite_code': invite.invite_code,
                'expires_at': invite.expires_at.strftime('%Y-%m-%d %H:%M'),
                'max_uses': invite.max_uses,
                'current_uses': invite.current_uses
            })
        
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def join_bench(request, invite_code):
    """Join a private bench using invite code"""
    try:
        # Look up invite
        invite = get_object_or_404(BenchInvite, invite_code=invite_code)
        
        # Validate invite is active and not expired
        if not invite.is_valid():
            if invite.is_expired():
                messages.error(request, 'This invite link has expired.')
            else:
                messages.error(request, 'This invite link is no longer active.')
            return redirect('find_chat')
        
        room = invite.room
        
        # Check if user is already in the room
        if request.user in room.participants.all():
            messages.info(request, 'You are already in this bench!')
            return redirect('chat_room', room_id=room.room_id)
        
        # Check if room is full
        if room.is_full:
            messages.error(request, 'This bench is full.')
            return redirect('find_chat')
        
        # Add user to room
        room.participants.add(request.user)
        
        # Increment invite usage
        invite.current_uses += 1
        if invite.current_uses >= invite.max_uses:
            invite.status = 'used'
        invite.save()
        
        # Send system message
        ChatMessage.objects.create(
            room=room,
            user=request.user,
            message_type='system',
            content=f"{request.user.username} joined the bench via invite"
        )
        
        messages.success(request, f'Welcome to "{room.bench_name}"!')
        return redirect('chat_room', room_id=room.room_id)
        
    except Exception as e:
        messages.error(request, f'Error joining bench: {str(e)}')
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
            
            # Check if user has an ACTIVE, RECENT match (within last 2 minutes)
            # This prevents immediate reconnection but allows new searches after a brief period
            existing_match = ChatRoom.objects.filter(
                participants=request.user,
                room_type='stranger',
                is_active=True,
                created_at__gte=timezone.now() - timedelta(minutes=2)  # Only within 2 minutes
            ).first()
            
            if existing_match:
                # User was matched recently! Remove from queue and redirect
                StrangerChatQueue.objects.filter(user=request.user).delete()
                profile.looking_for_stranger_chat = False
                profile.save()
                
                return JsonResponse({
                    'status': 'matched',
                    'message': 'Connected with a stranger!',
                    'room_id': str(existing_match.room_id)
                })
            
            # Check if user already in queue
            queue_entry, created = StrangerChatQueue.objects.get_or_create(
                user=request.user,
                defaults={'connection_attempts': 0}
            )
            
            if not created:
                queue_entry.connection_attempts += 1
                queue_entry.last_attempt = timezone.now()
                queue_entry.save()
            
            # Try to match with another user in queue
            matched_user_queue = find_queue_match(request.user)
            
            if matched_user_queue:
                # Found a match! Create room and notify both users
                chat_room = create_stranger_chat_room(request, matched_user_queue)
                return JsonResponse({
                    'status': 'matched',
                    'message': 'Connected with a stranger!',
                    'room_id': str(chat_room.room_id)
                })
            
            # No match yet - check for available online users
            available_users = find_available_online_users(request.user)
            
            if not available_users.exists():
                return handle_no_users_available(request, queue_entry)
            
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
    )

def find_queue_match(current_user):
    """Find another user in the stranger chat queue to match with"""
    # Find someone who's been waiting (not the current user)
    return StrangerChatQueue.objects.filter(
        joined_at__lt=timezone.now() - timedelta(seconds=5)  # Wait 5 seconds minimum
    ).exclude(user=current_user).first()

def create_stranger_chat_room(request, matched_user_queue):
    """Create a chat room for matched strangers and return the room"""
    matched_user = matched_user_queue.user
    
    # Create chat room with max_users=2 for 1-on-1 secure chat
    chat_room = ChatRoom.objects.create(
        name=f"Stranger Chat {timezone.now().strftime('%H:%M')}",
        room_type='stranger',
        created_by=request.user,
        max_users=2,  # Secure 1-on-1 chat
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
    
    # Send system message
    ChatMessage.objects.create(
        room=chat_room,
        user=request.user,
        message_type='system',
        content=f"Connected with a stranger! Say hello! 👋"
    )
    
    return chat_room

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

# check_match_status removed - was unused and returning incorrect 'not_searching' status

@login_required
def get_online_status(request):
    """Get online users count"""
    online_users = UserProfile.objects.filter(
        is_online=True,
        last_activity__gte=timezone.now() - timedelta(minutes=5)
    ).exclude(user=request.user).count()
    
    in_queue = StrangerChatQueue.objects.filter(user=request.user).exists()
    
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


@staff_member_required
def analytics_dashboard(request):
    """Staff-only analytics dashboard with key metrics"""
    from django.db.models import Count, Avg, Sum
    from datetime import timedelta
    from .models import AnalyticsEvent, Purchase, ChatRoom, CoinTransaction
    
    now = timezone.now()
    today = now.date()
    yesterday = today - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    
    # Daily Active Users
    dau_today = User.objects.filter(userprofile__last_activity__gte=today).count()
    dau_yesterday = User.objects.filter(
        userprofile__last_activity__gte=yesterday,
        userprofile__last_activity__lt=today
    ).count()
    dau_change = ((dau_today - dau_yesterday) / dau_yesterday * 100) if dau_yesterday > 0 else 0
    
    # Signups
    signups_today = AnalyticsEvent.objects.filter(event_type='signup', timestamp__gte=today).count()
    signups_7days = AnalyticsEvent.objects.filter(event_type='signup', timestamp__gte=week_ago).count()
    
    # Matching metrics
    searches = AnalyticsEvent.objects.filter(event_type='stranger_search_started', timestamp__gte=week_ago).count()
    matches = AnalyticsEvent.objects.filter(event_type='stranger_match_made', timestamp__gte=week_ago).count()
    match_rate = (matches / searches * 100) if searches > 0 else 0
    
    # Messaging
    total_messages = AnalyticsEvent.objects.filter(event_type='message_sent', timestamp__gte=week_ago).count()
    active_chats = ChatRoom.objects.filter(is_active=True, created_at__gte=week_ago).count()
    avg_messages_per_chat = (total_messages / active_chats) if active_chats > 0 else 0
    
    # Room usage
    benches_created = AnalyticsEvent.objects.filter(event_type='bench_created', timestamp__gte=week_ago).count()
    theatres_created = AnalyticsEvent.objects.filter(event_type='theatre_created', timestamp__gte=week_ago).count()
    avg_participants = ChatRoom.objects.filter(is_active=True).annotate(
        participant_count=Count('participants')
    ).aggregate(Avg('participant_count'))['participant_count__avg'] or 0
    
    # Coin economy
    coins_earned = CoinTransaction.objects.filter(timestamp__gte=week_ago, amount__gt=0).aggregate(Sum('amount'))['amount__sum'] or 0
    coins_spent = abs(CoinTransaction.objects.filter(timestamp__gte=week_ago, amount__lt=0).aggregate(Sum('amount'))['amount__sum'] or 0)
    coin_balance = coins_earned - coins_spent
    spending_ratio = (coins_spent / coins_earned * 100) if coins_earned > 0 else 0
    
    # Top items
    top_items = Purchase.objects.filter(timestamp__gte=week_ago).values(
        'item__name', 'item__emoji'
    ).annotate(purchase_count=Count('id'), total_revenue=Sum('total_price')).order_by('-purchase_count')[:5]
    
    top_items_formatted = [
        {
            'name': item['item__name'],
            'emoji': item['item__emoji'],
            'purchase_count': item['purchase_count'],
            'total_revenue': item['total_revenue']
        }
        for item in top_items
    ]
    
    # Recent events
    recent_events = AnalyticsEvent.objects.select_related('user').order_by('-timestamp')[:50]
    
    metrics = {
        'daily_active_users': dau_today,
        'dau_change': round(dau_change, 1),
        'signups_today': signups_today,
        'signups_7days': signups_7days,
        'match_rate': round(match_rate, 1),
        'total_matches': matches,
        'median_match_time': 45,  # Placeholder
        'avg_match_time': 52,  # Placeholder
        'total_messages': total_messages,
        'avg_messages_per_chat': round(avg_messages_per_chat, 1),
        'active_chats': active_chats,
        'benches_created': benches_created,
        'theatres_created': theatres_created,
        'avg_participants': round(avg_participants, 1),
        'coins_earned': coins_earned,
        'coins_spent': coins_spent,
        'coin_balance': coin_balance,
        'spending_ratio': round(spending_ratio, 1),
        'top_items': top_items_formatted,
    }
    
    return render(request, 'analytics_dashboard.html', {
        'metrics': metrics,
        'recent_events': recent_events
    })


# ——— Theatre Room Views ———
from urllib.request import Request, urlopen
from urllib.error import URLError
from django.http import HttpResponse

@login_required
def create_theatre_room(request):
    """Create a new theatre room"""
    if request.method != 'POST':
        # Don't allow GET to create rooms - show a form or redirect
        return render(request, 'create_theatre.html')
    
    theatre_name = request.POST.get('theatre_name', f"Theatre Room {timezone.now().strftime('%H:%M')}")
    channel_url = request.POST.get('channel_url')
    
    if not theatre_name:
        theatre_name = f"Theatre Room {timezone.now().strftime('%H:%M')}"
    
    chat_room = ChatRoom.objects.create(
        name=theatre_name,
        room_type='theatre',
        created_by=request.user,
        max_users=50,
        channel_url=channel_url
    )
    chat_room.participants.add(request.user)
    
    messages.success(request, f'Theatre room "{theatre_name}" created!')
    return redirect('theatre_room_view', room_id=chat_room.room_id)

@login_required
def theatre_room_view(request, room_id):
    """View for the theatre UI"""
    room = get_object_or_404(ChatRoom, room_id=room_id, room_type='theatre')
    
    # Block access to closed rooms
    if not room.is_active:
        messages.error(request, 'This theatre room has been closed')
        return redirect('home')
    
    # Add viewer to participants if not already (Issue 9 fix)
    if not room.participants.filter(id=request.user.id).exists():
        room.participants.add(request.user)
    
    # Initialize 10 seats if they don't exist
    from .models import TheatreSeat
    for i in range(1, 11):
        TheatreSeat.objects.get_or_create(room=room, seat_number=i)
        
    seats = TheatreSeat.objects.filter(room=room).order_by('seat_number')
    
    context = {
        'room': room,
        'seats': seats,
    }
    return render(request, 'theatre_room.html', context)


@login_required
@csrf_exempt
def proxy_m3u(request):
    """Proxy view to fetch M3U playlists ONLY - streams load directly in browser."""
    url = request.GET.get('url')
    if not url:
        return HttpResponse("Missing URL", status=400)
    
    # Security: Allowlist exact hostnames for playlist sources only
    from urllib.parse import urlparse
    parsed_url = urlparse(url)
    
    # Only allow playlist fetches from trusted sources
    # Streams will load directly in browser (no proxy)
    allowed_hosts = {
        'iptv-org.github.io',
        # Add other trusted playlist sources here
    }
    
    if parsed_url.netloc not in allowed_hosts:
        return HttpResponse("URL not allowed - only playlist sources permitted", status=403)
    
    # Only allow m3u/m3u8 playlist files, not streams
    if not (url.endswith('.m3u') or url.endswith('.m3u8') or '/index.m3u' in url):
        return HttpResponse("Only playlist files allowed", status=403)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    try:
        resp = req_lib.get(
            url,
            headers=headers,
            timeout=15,
            verify=True,  # SSL verification enabled
            stream=False,  # Don't stream - only playlists
            allow_redirects=False,  # Don't follow redirects to prevent bypass
        )
        resp.raise_for_status()
        
        # Only handle redirects to allowed hosts
        if resp.status_code in (301, 302, 303, 307, 308):
            redirect_url = resp.headers.get('Location', '')
            redirect_parsed = urlparse(redirect_url)
            if redirect_parsed.netloc not in allowed_hosts:
                return HttpResponse("Redirect to non-allowlisted host blocked", status=403)
            # Follow the redirect manually
            return proxy_m3u(request)  # Recursive call with new URL

        content = resp.content.decode('utf-8', errors='replace')
        
        # Parse playlist and return stream URLs directly (no proxy)
        # Client player will load streams directly
        rewritten_lines = []
        base_url = url.rsplit('/', 1)[0] + '/'
        
        for line in content.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                # Stream URL - return as-is (no proxy)
                if stripped.startswith('http://') or stripped.startswith('https://'):
                    rewritten_lines.append(stripped)
                else:
                    # Relative URL - make absolute
                    rewritten_lines.append(base_url + stripped)
            else:
                rewritten_lines.append(line)
        
        rewritten = '\n'.join(rewritten_lines)
        response = HttpResponse(rewritten, content_type='application/vnd.apple.mpegurl; charset=utf-8')
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Headers'] = '*'
        response['Cache-Control'] = 'no-cache'
        return response

    except req_lib.exceptions.HTTPError as e:
        return HttpResponse(f"Upstream error: {e}", status=502)
    except Exception as e:
        return HttpResponse(f"Error: {str(e)}", status=500)
