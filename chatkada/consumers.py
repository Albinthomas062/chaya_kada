import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import ChatRoom, ChatMessage, UserProfile, User, TheatreSeat
import logging

logger = logging.getLogger(__name__)
class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        username = self.scope['user'].username

        # Save message to database (optional, depending on requirements)
        # await self.save_message(message)

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'username': username
            }
        )

    # Receive message from room group
    async def chat_message(self, event):
        message = event['message']
        username = event['username']

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': message,
            'username': username
        }))

    @database_sync_to_async
    def save_message(self, message):
        # Implement message saving logic here if needed
        pass

class TheatreConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'theatre_{self.room_name}'
        self.user = self.scope['user']

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        if self.user.is_authenticated:
            await self.leave_seat()
        
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action')

        if action == 'chat_message':
            message = data.get('message')
            if message and self.user.is_authenticated:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': message,
                        'username': self.user.username,
                        'avatar': getattr(self.user, 'userprofile', None).avatar if hasattr(self.user, 'userprofile') else '☕'
                    }
                )
        
        elif action == 'take_seat':
            seat_number = data.get('seat_number')
            if seat_number and self.user.is_authenticated:
                success = await self.claim_seat(seat_number)
                if success:
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'seat_update',
                            'seat_number': seat_number,
                            'username': self.user.username,
                            'avatar': getattr(self.user, 'userprofile', None).avatar if hasattr(self.user, 'userprofile') else '☕'
                        }
                    )
        
        elif action == 'sync_video':
            # E.g. to broadcast play/pause/seek events to others
            video_state = data.get('state')
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'video_sync',
                    'state': video_state,
                    'username': self.user.username
                }
            )
            
        elif action == 'change_channel':
            channel_url = data.get('channel_url')
            if channel_url and self.user.is_authenticated:
                await self.update_channel(channel_url)
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'channel_sync',
                        'channel_url': channel_url,
                        'username': self.user.username
                    }
                )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'action': 'chat_message',
            'message': event['message'],
            'username': event['username'],
            'avatar': event.get('avatar', '☕')
        }))

    async def seat_update(self, event):
        await self.send(text_data=json.dumps({
            'action': 'seat_update',
            'seat_number': event['seat_number'],
            'username': event.get('username'),
            'avatar': event.get('avatar', '☕')
        }))
        
    async def video_sync(self, event):
        await self.send(text_data=json.dumps({
            'action': 'video_sync',
            'state': event['state'],
            'username': event['username']
        }))
        
    async def channel_sync(self, event):
        await self.send(text_data=json.dumps({
            'action': 'channel_sync',
            'channel_url': event['channel_url'],
            'username': event['username']
        }))

    @database_sync_to_async
    def claim_seat(self, seat_number):
        try:
            room = ChatRoom.objects.get(room_id=self.room_name)
            # Remove user from any other seat in this room first
            TheatreSeat.objects.filter(room=room, occupant=self.user).update(occupant=None)
            
            # Claim the new seat
            seat, created = TheatreSeat.objects.get_or_create(room=room, seat_number=seat_number)
            if seat.occupant is None or seat.occupant == self.user:
                seat.occupant = self.user
                seat.save()
                return True
            return False
        except ChatRoom.DoesNotExist:
            return False

    @database_sync_to_async
    def leave_seat(self):
        try:
            room = ChatRoom.objects.get(room_id=self.room_name)
            seat = TheatreSeat.objects.filter(room=room, occupant=self.user).first()
            if seat:
                seat_number = seat.seat_number
                seat.occupant = None
                seat.save()
                
                # Broadcast that the seat is empty
                from asgiref.sync import async_to_sync
                import channels.layers
                channel_layer = channels.layers.get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    self.room_group_name,
                    {
                        'type': 'seat_update',
                        'seat_number': seat_number,
                        'username': None,
                        'avatar': None
                    }
                )
        except ChatRoom.DoesNotExist:
            pass

    @database_sync_to_async
    def update_channel(self, channel_url):
        try:
            room = ChatRoom.objects.get(room_id=self.room_name)
            room.channel_url = channel_url
            room.save()
        except ChatRoom.DoesNotExist:
            pass
