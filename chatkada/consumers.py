import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import ChatRoom, ChatMessage, UserProfile, User, TheatreSeat
from .chat_utils import display_name, format_time, iso_local, is_anonymous_room
import logging

logger = logging.getLogger(__name__)

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'
        self.user = self.scope['user']
        
        # Reject anonymous users
        if not self.user.is_authenticated:
            await self.close()
            return

        # Verify room membership - room_name is the room_id UUID
        try:
            room = await database_sync_to_async(ChatRoom.objects.get)(room_id=self.room_name)
            is_participant = await database_sync_to_async(
                lambda: room.participants.filter(id=self.user.id).exists()
            )()
            
            if not is_participant:
                # User is not a participant - reject connection
                await self.close()
                return
            self.room_type = room.room_type
                
        except ChatRoom.DoesNotExist:
            await self.close()
            return

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        
        # Send initial connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection',
            'message': 'Connected to chat'
        }))

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message = text_data_json.get('message', '').strip()
            # Server controls message_type - don't trust client
            client_message_type = text_data_json.get('message_type', 'text')
            
            if not message or not self.user.is_authenticated:
                return
            
            # Validate and sanitize message_type on server
            if client_message_type == 'shared_item':
                # TODO: Validate user has the item
                message_type = 'shared_item'
            elif client_message_type == 'system':
                # Clients cannot send system messages
                message_type = 'text'
            else:
                message_type = 'text'
            
            # Save message to database
            saved_message = await self.save_message(message, message_type)
            
            if saved_message:
                # Send message to room group
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': message,
                        # Internal to the channel layer only; chat_message()
                        # decides per recipient what identity is revealed.
                        'sender_id': self.user.id,
                        'sender_username': self.user.username,
                        'message_type': message_type,  # Server-controlled
                        'timestamp': saved_message['timestamp'],
                        'time_display': saved_message['time_display'],
                    }
                )
        except Exception as e:
            logger.error(f"Error in ChatConsumer.receive: {e}")

    # Receive message from room group (runs once per recipient socket)
    async def chat_message(self, event):
        sender_id = event.get('sender_id')
        is_own = sender_id == self.user.id
        room_type = getattr(self, 'room_type', 'stranger')
        payload = {
            'type': 'message',
            'message': event['message'],
            'username': (display_name(sender_id, room_type, self.user.id)
                         if is_anonymous_room(room_type)
                         else event.get('sender_username', '')),
            'is_own': is_own,
            'anonymous': is_anonymous_room(room_type),
            'message_type': event.get('message_type', 'text'),
            'timestamp': event.get('timestamp', ''),
            'time_display': event.get('time_display', ''),
        }
        # Never leak the real identity (username or user id) in stranger chats
        if not is_anonymous_room(room_type):
            payload['user_id'] = sender_id

        await self.send(text_data=json.dumps(payload))

    @database_sync_to_async
    def save_message(self, message, message_type='text'):
        try:
            room = ChatRoom.objects.get(room_id=self.room_name)
            chat_message = ChatMessage.objects.create(
                user=self.user,
                room=room,
                content=message,
                message_type=message_type
            )
            return {
                'id': chat_message.id,
                'timestamp': iso_local(chat_message.timestamp),
                'time_display': format_time(chat_message.timestamp),
            }
        except Exception as e:
            logger.error(f"Error saving message: {e}")
            return None

class TheatreConsumer(AsyncWebsocketConsumer):
    SEAT_COUNT = 10
    ALLOWED_REACTIONS = {'❤️', '😂', '😮', '👏', '☕'}

    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'theatre_{self.room_name}'
        self.user = self.scope['user']
        
        # Reject anonymous users
        if not self.user.is_authenticated:
            await self.close()
            return

        # Verify room membership/access
        try:
            room = await database_sync_to_async(ChatRoom.objects.get)(
                room_id=self.room_name, 
                room_type='theatre'
            )
            
            # For theatre rooms: verify user is participant (added by the view)
            is_participant = await database_sync_to_async(
                lambda: room.participants.filter(id=self.user.id).exists()
            )()
            
            if not is_participant:
                # Not a participant - reject connection
                await self.close()
                return
                
        except ChatRoom.DoesNotExist:
            await self.close()
            return

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
        try:
            data = json.loads(text_data)
        except (TypeError, ValueError):
            return
        if not isinstance(data, dict):
            return
        action = data.get('action')

        if action == 'chat_message':
            message = data.get('message')
            if isinstance(message, str):
                message = message.strip()[:500]
            if message and self.user.is_authenticated:
                # Get user avatar safely
                user_avatar = await self.get_user_avatar()
                now = timezone.now()
                
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': message,
                        'username': self.user.username,
                        'avatar': user_avatar,
                        'timestamp': iso_local(now),
                        'time_display': format_time(now),
                    }
                )
        
        elif action == 'reaction':
            emoji = data.get('emoji')
            if emoji not in self.ALLOWED_REACTIONS:
                return
            if emoji and self.user.is_authenticated:
                # Rate limit: check last reaction time (simple in-memory check)
                now = timezone.now().timestamp()
                last_reaction_key = f'last_reaction_{self.user.id}'
                last_reaction = getattr(self, last_reaction_key, 0)
                
                if now - last_reaction < 1:  # 1 second rate limit
                    return
                
                setattr(self, last_reaction_key, now)
                
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'reaction',
                        'emoji': emoji,
                        'username': self.user.username
                    }
                )
        
        elif action == 'take_seat':
            seat_number = data.get('seat_number')
            # Only real seats 1..10 (prevents creating arbitrary seat rows)
            if isinstance(seat_number, bool) or not isinstance(seat_number, int) \
                    or not 1 <= seat_number <= self.SEAT_COUNT:
                await self.send(text_data=json.dumps({
                    'action': 'seat_error', 'message': 'Invalid seat'}))
                return
            if seat_number and self.user.is_authenticated:
                # Get user avatar safely
                user_avatar = await self.get_user_avatar()
                result = await self.claim_seat(seat_number)
                
                if result['success']:
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'seat_update',
                            'seat_number': seat_number,
                            'username': self.user.username,
                            'avatar': user_avatar
                        }
                    )
                    # Send confirmation to this user
                    await self.send(text_data=json.dumps({
                        'action': 'seat_confirmed',
                        'seat_number': seat_number
                    }))
                    
                    # Broadcast old seat as freed if there was one
                    if result['old_seat']:
                        await self.channel_layer.group_send(
                            self.room_group_name,
                            {
                                'type': 'seat_update',
                                'seat_number': result['old_seat'],
                                'username': None,
                                'avatar': None
                            }
                        )
                else:
                    # Send error to this user
                    await self.send(text_data=json.dumps({
                        'action': 'seat_error',
                        'message': 'Seat is already occupied'
                    }))
        
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
            'avatar': event.get('avatar', '☕'),
            'timestamp': event.get('timestamp', ''),
            'time_display': event.get('time_display', '')
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
    
    async def reaction(self, event):
        await self.send(text_data=json.dumps({
            'action': 'reaction',
            'emoji': event['emoji'],
            'username': event['username']
        }))

    @database_sync_to_async
    def get_user_avatar(self):
        """Safely get user avatar"""
        try:
            if hasattr(self.user, 'userprofile'):
                return self.user.userprofile.avatar
        except Exception:
            pass
        return '☕'

    @database_sync_to_async
    def claim_seat(self, seat_number):
        try:
            room = ChatRoom.objects.get(room_id=self.room_name)
            
            # Find if user has an old seat
            old_seat_obj = TheatreSeat.objects.filter(room=room, occupant=self.user).first()
            old_seat_number = old_seat_obj.seat_number if old_seat_obj else None
            
            # Check if the requested seat is available
            seat, created = TheatreSeat.objects.get_or_create(room=room, seat_number=seat_number)
            
            if seat.occupant is not None and seat.occupant != self.user:
                # Seat is occupied by someone else
                return {'success': False, 'old_seat': None}
            
            # Remove user from any other seat in this room first
            if old_seat_obj and old_seat_obj.seat_number != seat_number:
                old_seat_obj.occupant = None
                old_seat_obj.save()
            
            # Claim the new seat
            seat.occupant = self.user
            seat.save()
            
            return {'success': True, 'old_seat': old_seat_number if old_seat_number != seat_number else None}
        except ChatRoom.DoesNotExist:
            return {'success': False, 'old_seat': None}

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
