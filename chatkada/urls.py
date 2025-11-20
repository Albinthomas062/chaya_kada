from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', views.custom_logout, name='logout'),
    path('kada/', views.kada, name='kada'),
    path('profile/', views.profile, name='profile'),
    path('buy-item/', views.buy_item, name='buy_item'),
    
    # Chat URLs
    path('find-chat/', views.find_chat, name='find_chat'),
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
    
    # Item management for admin
    path('custom-admin/login/', views.custom_admin_login, name='custom_admin_login'),
    path('custom-admin/', views.custom_admin_dashboard, name='custom_admin_dashboard'),
    path('custom-admin/items/', views.manage_items, name='manage_items'),
    path('custom-admin/items/add/', views.add_item, name='add_item'),
    path('custom-admin/items/<int:item_id>/edit/', views.edit_item, name='edit_item'),
    path('custom-admin/items/<int:item_id>/delete/', views.delete_item, name='delete_item'),
    # Challenge management for admin
    path('custom-admin/challenges/', views.manage_challenges, name='manage_challenges'),
    path('custom-admin/challenges/assign/', views.assign_challenge, name='assign_challenge'),
]