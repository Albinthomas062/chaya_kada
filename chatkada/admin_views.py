from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db.models import Q, Count, Sum
from django.http import JsonResponse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
from datetime import timedelta
import time

from .models import (
    Item, User, UserProfile, ChatRoom, Purchase, 
    DailyChallenge, CoinTransaction, TheatreSeat
)
from .forms import ItemForm

from . import login_throttle

# Login attempt tracking (see chatkada/login_throttle.py)
MAX_ATTEMPTS = login_throttle.MAX_ATTEMPTS
LOCKOUT_DURATION = login_throttle.LOCKOUT_SECONDS
ADMIN_SCOPE = 'admin'
get_client_ip = login_throttle.get_client_ip


def is_staff_user(user):
    """Check if user is staff"""
    return user.is_staff or user.is_superuser


def custom_admin_login(request):
    """Secure staff login with rate limiting"""
    # Redirect if already authenticated as staff
    if request.user.is_authenticated and is_staff_user(request.user):
        next_url = request.GET.get('next', 'custom_admin_dashboard')
        # Validate next_url to prevent open redirect
        if next_url and url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure()
        ):
            return redirect(next_url)
        return redirect('custom_admin_dashboard')
    
    if request.method == "POST":
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        ip_address = get_client_ip(request)
        
        # Check rate limiting
        if login_throttle.is_locked(ADMIN_SCOPE, username, ip_address):
            messages.error(
                request, 
                f"Account temporarily locked due to too many failed attempts. "
                f"Please try again in {LOCKOUT_DURATION // 60} minutes."
            )
            return render(request, 'custom_admin/admin_login.html')
        
        # Authenticate
        user = authenticate(request, username=username, password=password)
        
        if user is not None and is_staff_user(user):
            login(request, user)
            login_throttle.record_success(ADMIN_SCOPE, username, ip_address)
            
            # Handle 'next' parameter safely (prevent open redirects)
            next_url = request.POST.get('next') or request.GET.get('next', '')
            if next_url and url_has_allowed_host_and_scheme(
                url=next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure()
            ):
                return redirect(next_url)
            return redirect('custom_admin_dashboard')
        else:
            attempts_left = login_throttle.record_failure(ADMIN_SCOPE, username, ip_address)

            if attempts_left > 0:
                messages.error(
                    request, 
                    f"Invalid credentials or not a staff user. {attempts_left} attempt{'' if attempts_left == 1 else 's'} remaining."
                )
            else:
                messages.error(
                    request,
                    f"Too many failed attempts. Account locked for {LOCKOUT_DURATION // 60} minutes."
                )
    
    return render(request, 'custom_admin/admin_login.html', {
        'next': request.GET.get('next', '')
    })


@staff_member_required(login_url='custom_admin_login')
def custom_admin_logout(request):
    """Admin logout"""
    logout(request)
    messages.success(request, "Successfully logged out.")
    return redirect('custom_admin_login')


@staff_member_required(login_url='custom_admin_login')
def custom_admin_dashboard(request):
    """Enhanced admin dashboard with quick stats"""
    # Quick stats
    total_items = Item.objects.count()
    active_items = Item.objects.filter(available=True).count()
    total_users = User.objects.count()
    active_rooms = ChatRoom.objects.filter(is_active=True).count()
    
    # Recent purchases
    recent_purchases = Purchase.objects.select_related('user', 'item').order_by('-timestamp')[:10]
    
    # Low coin users (might need help)
    low_coin_users = UserProfile.objects.filter(coins__lt=50).select_related('user').order_by('coins')[:10]
    
    context = {
        'total_items': total_items,
        'active_items': active_items,
        'total_users': total_users,
        'active_rooms': active_rooms,
        'recent_purchases': recent_purchases,
        'low_coin_users': low_coin_users,
    }
    
    return render(request, 'custom_admin/dashboard.html', context)


# ==================== ITEM MANAGEMENT ====================

@staff_member_required(login_url='custom_admin_login')
def manage_items(request):
    """List items with search and filter"""
    items_list = Item.objects.all()
    
    # Search
    search_query = request.GET.get('search', '').strip()
    if search_query:
        items_list = items_list.filter(
            Q(name__icontains=search_query) | 
            Q(description__icontains=search_query)
        )
    
    # Filter by category
    category_filter = request.GET.get('category', '')
    if category_filter:
        items_list = items_list.filter(category=category_filter)
    
    # Filter by availability
    availability_filter = request.GET.get('availability', '')
    if availability_filter == 'available':
        items_list = items_list.filter(available=True)
    elif availability_filter == 'hidden':
        items_list = items_list.filter(available=False)
    
    # Order by
    order_by = request.GET.get('order_by', 'sort_order')
    if order_by in ['name', '-name', 'price', '-price', 'category', 'sort_order']:
        items_list = items_list.order_by(order_by, 'name')
    
    # Pagination
    paginator = Paginator(items_list, 20)
    page_number = request.GET.get('page', 1)
    items = paginator.get_page(page_number)
    
    categories = Item.CATEGORY_CHOICES
    
    context = {
        'items': items,
        'search_query': search_query,
        'category_filter': category_filter,
        'availability_filter': availability_filter,
        'order_by': order_by,
        'categories': categories,
    }
    
    return render(request, 'custom_admin/items.html', context)


@staff_member_required(login_url='custom_admin_login')
def add_item(request):
    """Add new item"""
    if request.method == "POST":
        form = ItemForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save()
            messages.success(request, f"✓ Item '{item.name}' added successfully!")
            return redirect('manage_items')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ItemForm()
    
    return render(request, "custom_admin/item_form.html", {
        "form": form,
        "form_title": "Add New Item",
        "submit_text": "Create Item"
    })


@staff_member_required(login_url='custom_admin_login')
def edit_item(request, item_id):
    """Edit existing item"""
    item = get_object_or_404(Item, id=item_id)
    
    if request.method == "POST":
        form = ItemForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            item = form.save()
            messages.success(request, f"✓ Item '{item.name}' updated successfully!")
            return redirect('manage_items')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ItemForm(instance=item)
    
    return render(request, "custom_admin/item_form.html", {
        "form": form,
        "form_title": f"Edit Item: {item.name}",
        "submit_text": "Save Changes",
        "item": item
    })


@staff_member_required(login_url='custom_admin_login')
@require_http_methods(["POST"])
def delete_item(request, item_id):
    """Delete item (with confirmation)"""
    item = get_object_or_404(Item, id=item_id)
    item_name = item.name
    
    # Soft delete: just mark as unavailable
    if request.POST.get('soft_delete'):
        item.available = False
        item.save()
        messages.success(request, f"✓ Item '{item_name}' hidden (soft deleted).")
    else:
        # Hard delete
        item.delete()
        messages.success(request, f"✓ Item '{item_name}' permanently deleted.")
    
    return redirect('manage_items')


@staff_member_required(login_url='custom_admin_login')
@require_http_methods(["POST"])
def toggle_item_availability(request, item_id):
    """Toggle item availability (AJAX)"""
    item = get_object_or_404(Item, id=item_id)
    item.available = not item.available
    item.save()
    
    return JsonResponse({
        'success': True,
        'available': item.available,
        'message': f"Item {'shown' if item.available else 'hidden'}."
    })


# ==================== USER MANAGEMENT ====================

@staff_member_required(login_url='custom_admin_login')
def manage_users(request):
    """List and manage users"""
    users_list = User.objects.select_related('userprofile').all()
    
    # Search
    search_query = request.GET.get('search', '').strip()
    if search_query:
        users_list = users_list.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        users_list = users_list.filter(is_active=True)
    elif status_filter == 'banned':
        users_list = users_list.filter(is_active=False)
    elif status_filter == 'staff':
        users_list = users_list.filter(is_staff=True)
    
    # Order by
    order_by = request.GET.get('order_by', '-date_joined')
    if order_by in ['username', '-username', 'date_joined', '-date_joined']:
        users_list = users_list.order_by(order_by)
    
    # Pagination
    paginator = Paginator(users_list, 25)
    page_number = request.GET.get('page', 1)
    users = paginator.get_page(page_number)
    
    context = {
        'users': users,
        'search_query': search_query,
        'status_filter': status_filter,
        'order_by': order_by,
    }
    
    return render(request, 'custom_admin/users.html', context)


@staff_member_required(login_url='custom_admin_login')
def view_user(request, user_id):
    """View user details"""
    user = get_object_or_404(User, id=user_id)
    profile = user.userprofile
    
    # User stats
    total_purchases = Purchase.objects.filter(user=user).count()
    total_spent = Purchase.objects.filter(user=user).aggregate(Sum('total_price'))['total_price__sum'] or 0
    challenges_completed = DailyChallenge.objects.filter(user=user).count()  # Having a record means completed
    
    # Recent activity
    recent_purchases = Purchase.objects.filter(user=user).select_related('item').order_by('-timestamp')[:10]
    recent_transactions = CoinTransaction.objects.filter(user=user).order_by('-timestamp')[:10]
    
    context = {
        'viewed_user': user,
        'profile': profile,
        'total_purchases': total_purchases,
        'total_spent': total_spent,
        'challenges_completed': challenges_completed,
        'recent_purchases': recent_purchases,
        'recent_transactions': recent_transactions,
    }
    
    return render(request, 'custom_admin/user_detail.html', context)


@staff_member_required(login_url='custom_admin_login')
@require_http_methods(["POST"])
def adjust_user_coins(request, user_id):
    """Adjust user coins with validation"""
    user = get_object_or_404(User, id=user_id)
    profile = user.userprofile
    
    # Validate amount
    amount_str = request.POST.get('amount', '').strip()
    reason = request.POST.get('reason', '').strip()
    
    if not amount_str:
        messages.error(request, "Amount is required.")
        return redirect('view_user', user_id=user_id)
    
    try:
        amount = int(amount_str)
    except ValueError:
        messages.error(request, "Amount must be a valid integer.")
        return redirect('view_user', user_id=user_id)
    
    if amount == 0:
        messages.error(request, "Amount cannot be zero.")
        return redirect('view_user', user_id=user_id)
    
    # Validate reason
    if not reason:
        messages.error(request, "Reason is required.")
        return redirect('view_user', user_id=user_id)
    
    # Check for negative balance
    new_balance = profile.coins + amount
    if new_balance < 0:
        messages.error(request, f"Cannot deduct {abs(amount)} coins. User only has {profile.coins} coins.")
        return redirect('view_user', user_id=user_id)
    
    # Update coins
    profile.coins = new_balance
    profile.save()
    
    # Record transaction
    CoinTransaction.objects.create(
        user=user,
        amount=amount,
        transaction_type='admin_adjustment',
        description=f"Admin: {reason}"
    )
    
    action = "added" if amount > 0 else "deducted"
    messages.success(request, f"✓ {abs(amount)} coins {action} for {user.username}. Reason: {reason}")
    
    return redirect('view_user', user_id=user_id)


@staff_member_required(login_url='custom_admin_login')
@require_http_methods(["POST"])
def toggle_user_ban(request, user_id):
    """Ban/unban user"""
    user = get_object_or_404(User, id=user_id)
    
    # Don't allow banning staff/superusers
    if user.is_staff or user.is_superuser:
        messages.error(request, "Cannot ban staff or superuser accounts.")
        return redirect('view_user', user_id=user_id)
    
    user.is_active = not user.is_active
    user.save()
    
    status = "unbanned" if user.is_active else "banned"
    messages.success(request, f"✓ User {user.username} {status}.")
    
    return redirect('view_user', user_id=user_id)


# ==================== ROOM/BENCH/THEATRE MANAGEMENT ====================

@staff_member_required(login_url='custom_admin_login')
def manage_rooms(request):
    """List and manage chat rooms"""
    rooms_list = ChatRoom.objects.annotate(
        participant_count=Count('participants')
    ).order_by('-created_at')
    
    # Filter by type
    room_type = request.GET.get('type', '')
    if room_type:
        rooms_list = rooms_list.filter(room_type=room_type)
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        rooms_list = rooms_list.filter(is_active=True)
    elif status_filter == 'closed':
        rooms_list = rooms_list.filter(is_active=False)
    
    # Pagination
    paginator = Paginator(rooms_list, 25)
    page_number = request.GET.get('page', 1)
    rooms = paginator.get_page(page_number)
    
    context = {
        'rooms': rooms,
        'room_type': room_type,
        'status_filter': status_filter,
    }
    
    return render(request, 'custom_admin/rooms.html', context)


@staff_member_required(login_url='custom_admin_login')
@require_http_methods(["POST"])
def close_room(request, room_id):
    """Close a chat room"""
    room = get_object_or_404(ChatRoom, room_id=room_id)
    room.is_active = False
    room.save()
    
    messages.success(request, f"✓ Room '{room.name or room.room_type}' closed.")
    return redirect('manage_rooms')


# ==================== CHALLENGE MANAGEMENT ====================

@staff_member_required(login_url='custom_admin_login')
def manage_challenges(request):
    """Manage daily challenges"""
    from .forms import AssignChallengeForm
    
    challenges = DailyChallenge.objects.select_related('user').order_by('-completed_date')[:100]
    
    # Stats
    today = timezone.now().date()
    today_completed = DailyChallenge.objects.filter(completed_date=today).count()  # Having a record means completed
    today_total = DailyChallenge.objects.filter(completed_date=today).count()
    completion_rate = (today_completed / today_total * 100) if today_total > 0 else 0
    
    context = {
        'challenges': challenges,
        'today_completed': today_completed,
        'today_total': today_total,
        'completion_rate': round(completion_rate, 1),
    }
    
    return render(request, 'custom_admin/challenges.html', context)


@staff_member_required(login_url='custom_admin_login')
def assign_challenge(request):
    """Assign challenge to all users"""
    from .forms import AssignChallengeForm
    
    if request.method == "POST":
        form = AssignChallengeForm(request.POST)
        if form.is_valid():
            challenge_type = form.cleaned_data["challenge_type"]
            coins_earned = form.cleaned_data["coins_earned"]
            today = timezone.now().date()
            created = 0
            
            for user in User.objects.filter(is_active=True):
                challenges = DailyChallenge.objects.filter(
                    user=user,
                    challenge_type=challenge_type,
                    completed_date=today
                )
                if not challenges.exists():
                    DailyChallenge.objects.create(
                        user=user,
                        challenge_type=challenge_type,
                        completed_date=today,
                        coins_earned=coins_earned,
                    )
                    created += 1
            
            messages.success(request, f"✓ Assigned '{challenge_type}' challenge to {created} users for today.")
            return redirect('manage_challenges')
    else:
        form = AssignChallengeForm()
    
    return render(request, "custom_admin/assign_challenges.html", {"form": form})


# ==================== ANALYTICS ====================

@staff_member_required(login_url='custom_admin_login')
def analytics_dashboard(request):
    """Analytics dashboard (keep existing implementation)"""
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
        'median_match_time': 45,
        'avg_match_time': 52,
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
