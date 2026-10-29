from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from . import admin_views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.custom_logout, name='logout'),
    path('kada/', views.kada, name='kada'),
    path('profile/', views.profile, name='profile'),
    path('buy-item/', views.buy_item, name='buy_item'),
    
    # Chat URLs
    path('find-chat/', views.find_chat, name='find_chat'),
    path('create-private-bench/', views.create_private_bench, name='create_private_bench'),
    path('chat/<uuid:room_id>/', views.chat_room, name='chat_room'),
    path('send-chat-message/', views.send_chat_message, name='send_chat_message'),
    path('get-chat-messages/<uuid:room_id>/', views.get_chat_messages, name='get_chat_messages'),
    path('leave-chat/<uuid:room_id>/', views.leave_chat, name='leave_chat'),
    
    # Challenge & Coin URLs
    path('coin-center/', views.coin_center, name='coin_center'),
    path('check-daily-login/', views.check_daily_login, name='check_daily_login'),
    path('record-chat-friend/', views.record_chat_friend, name='record_chat_friend'),
    path('get-coin-progress/', views.get_coin_progress, name='get_coin_progress'),
    path('get-online-status/', views.get_online_status, name='get_online_status'),
    path('find-stranger/', views.find_stranger_chat, name='find_stranger_chat'),
    path('handle-stranger-chat-request/', views.handle_stranger_chat_request, name='handle_stranger_chat_request'),
    # check-match-status removed - unused endpoint
    
    # Bench Invite URLs
    path('create-bench-invite/<uuid:room_id>/', views.create_bench_invite, name='create_bench_invite'),
    path('join-bench/<str:invite_code>/', views.join_bench, name='join_bench'),
    
    # Theatre Room URLs
    path('create-theatre/', views.create_theatre_room, name='create_theatre_room'),
    path('theatre/<uuid:room_id>/', views.theatre_room_view, name='theatre_room_view'),
    path('proxy-m3u/', views.proxy_m3u, name='proxy_m3u'),
    
    # Item management for admin
    path('custom-admin/login/', admin_views.custom_admin_login, name='custom_admin_login'),
    path('custom-admin/logout/', admin_views.custom_admin_logout, name='custom_admin_logout'),
    path('custom-admin/', admin_views.custom_admin_dashboard, name='custom_admin_dashboard'),
    path('custom-admin/items/', admin_views.manage_items, name='manage_items'),
    path('custom-admin/items/add/', admin_views.add_item, name='add_item'),
    path('custom-admin/items/<int:item_id>/edit/', admin_views.edit_item, name='edit_item'),
    path('custom-admin/items/<int:item_id>/delete/', admin_views.delete_item, name='delete_item'),
    path('custom-admin/items/<int:item_id>/toggle/', admin_views.toggle_item_availability, name='toggle_item_availability'),
    
    # User management
    path('custom-admin/users/', admin_views.manage_users, name='manage_users'),
    path('custom-admin/users/<int:user_id>/', admin_views.view_user, name='view_user'),
    path('custom-admin/users/<int:user_id>/adjust-coins/', admin_views.adjust_user_coins, name='adjust_user_coins'),
    path('custom-admin/users/<int:user_id>/toggle-ban/', admin_views.toggle_user_ban, name='toggle_user_ban'),
    
    # Room management
    path('custom-admin/rooms/', admin_views.manage_rooms, name='manage_rooms'),
    path('custom-admin/rooms/<uuid:room_id>/close/', admin_views.close_room, name='close_room'),
    
    # Challenge management for admin
    path('custom-admin/challenges/', admin_views.manage_challenges, name='manage_challenges'),
    path('custom-admin/challenges/assign/', admin_views.assign_challenge, name='assign_challenge'),
    path('custom-admin/analytics/', admin_views.analytics_dashboard, name='analytics_dashboard'),
]