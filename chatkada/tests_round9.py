"""Round-9 regression tests: anonymity (6), streak (8), IST times (9), bench invite (11)."""
import json
from datetime import timedelta, datetime
from unittest import mock

from asgiref.sync import async_to_sync
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, TransactionTestCase, Client
from django.urls import reverse
from django.utils import timezone

from chatkada import routing
from chatkada.chat_utils import format_time, iso_local
from chatkada.models import ChatRoom, ChatMessage, BenchInvite, CoinTransaction


def _stranger_room(u1, u2):
    room = ChatRoom.objects.create(name='Stranger Chat', room_type='stranger', created_by=u1,
                                   max_users=2, expires_at=timezone.now() + timedelta(hours=1))
    room.participants.add(u1, u2)
    return room


class StrangerAnonymityViewTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice_real', password='pw12345!')
        self.bob = User.objects.create_user('bob_real', password='pw12345!')
        self.room = _stranger_room(self.alice, self.bob)
        ChatMessage.objects.create(room=self.room, user=self.alice, content='hi from alice',
                                   expires_at=timezone.now() + timedelta(hours=1))
        ChatMessage.objects.create(room=self.room, user=self.bob, content='hi from bob',
                                   expires_at=timezone.now() + timedelta(hours=1))

    def test_room_page_never_shows_other_username(self):
        c = Client(); c.login(username='bob_real', password='pw12345!')
        r = c.get(reverse('chat_room', args=[self.room.room_id]))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertNotIn('alice_real', html)
        self.assertIn("user: 'Stranger'", html)
        self.assertIn("user: 'You'", html)
        # no real user ids for messages either
        self.assertNotIn(f'user_id: {self.alice.id}', html)

    def test_get_chat_messages_json_anonymous(self):
        c = Client(); c.login(username='bob_real', password='pw12345!')
        data = c.get(reverse('get_chat_messages', args=[self.room.room_id])).json()
        users = {m['content']: m['user'] for m in data['messages']}
        self.assertEqual(users['hi from alice'], 'Stranger')
        self.assertEqual(users['hi from bob'], 'You')
        self.assertNotIn('alice_real', json.dumps(data))

    def test_leave_system_message_anonymous(self):
        c = Client(); c.login(username='alice_real', password='pw12345!')
        c.get(reverse('leave_chat', args=[self.room.room_id]))
        msg = ChatMessage.objects.filter(room=self.room, message_type='system').last()
        self.assertNotIn('alice_real', msg.content)

    def test_bench_still_shows_usernames(self):
        bench = ChatRoom.objects.create(name='Bench', bench_name='B', room_type='private_bench',
                                        created_by=self.alice, max_users=4)
        bench.participants.add(self.alice, self.bob)
        ChatMessage.objects.create(room=bench, user=self.alice, content='bench hi')
        c = Client(); c.login(username='bob_real', password='pw12345!')
        r = c.get(reverse('chat_room', args=[bench.room_id]))
        self.assertIn("user: 'alice_real'", r.content.decode())


class _InjectUser:
    """Test ASGI middleware: put a given user in scope (instead of session auth)."""
    def __init__(self, inner, user):
        self.inner, self.user = inner, user

    async def __call__(self, scope, receive, send):
        scope = dict(scope, user=self.user)
        return await self.inner(scope, receive, send)


class StrangerAnonymityWebsocketTests(TransactionTestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice_ws', password='pw12345!')
        self.bob = User.objects.create_user('bob_ws', password='pw12345!')

    def _run(self, room):
        async def go():
            app_a = _InjectUser(URLRouter(routing.websocket_urlpatterns), self.alice)
            app_b = _InjectUser(URLRouter(routing.websocket_urlpatterns), self.bob)
            ca = WebsocketCommunicator(app_a, f'/ws/chat/{room.room_id}/')
            cb = WebsocketCommunicator(app_b, f'/ws/chat/{room.room_id}/')
            ok_a, _ = await ca.connect(); ok_b, _ = await cb.connect()
            assert ok_a and ok_b
            await ca.receive_json_from(); await cb.receive_json_from()  # connection msgs
            await ca.send_json_to({'message': 'secret hello', 'message_type': 'text'})
            got_a = await ca.receive_json_from(timeout=5)
            got_b = await cb.receive_json_from(timeout=5)
            await ca.disconnect(); await cb.disconnect()
            return got_a, got_b
        return async_to_sync(go)()

    def test_stranger_ws_payload_anonymous(self):
        room = _stranger_room(self.alice, self.bob)
        got_a, got_b = self._run(room)
        self.assertEqual(got_b['username'], 'Stranger')
        self.assertFalse(got_b['is_own'])
        self.assertEqual(got_a['username'], 'You')
        self.assertTrue(got_a['is_own'])
        for payload in (got_a, got_b):
            raw = json.dumps(payload)
            self.assertNotIn('alice_ws', raw)
            self.assertNotIn('user_id', payload)
            self.assertNotIn('sender_id', payload)
        # Issue 9: live payload carries IST offset + same display string as a reload
        self.assertTrue(got_b['timestamp'].endswith('+05:30'), got_b['timestamp'])
        saved = ChatMessage.objects.get(content='secret hello')
        self.assertEqual(got_b['time_display'], format_time(saved.timestamp))

    def test_bench_ws_payload_has_username(self):
        bench = ChatRoom.objects.create(name='Bench', bench_name='B', room_type='private_bench',
                                        created_by=self.alice, max_users=4)
        bench.participants.add(self.alice, self.bob)
        _, got_b = self._run(bench)
        self.assertEqual(got_b['username'], 'alice_ws')


class DailyStreakTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('streaker', password='pw12345!')
        self.client.login(username='streaker', password='pw12345!')

    def _claim_on(self, day):
        with mock.patch('chatkada.views.timezone.localdate', return_value=day):
            return self.client.post(reverse('check_daily_login')).json()

    def test_streak_increments_on_consecutive_days(self):
        d = datetime(2026, 11, 1).date()
        self.assertEqual(self._claim_on(d)['streak'], 1)
        self.assertEqual(self._claim_on(d + timedelta(days=1))['streak'], 2)
        self.assertEqual(self._claim_on(d + timedelta(days=2))['streak'], 3)
        self.user.userprofile.refresh_from_db()
        self.assertEqual(self.user.userprofile.login_streak, 3)

    def test_same_day_claim_only_once(self):
        d = datetime(2026, 11, 1).date()
        self._claim_on(d)
        r = self._claim_on(d)
        self.assertFalse(r['success'])
        self.assertEqual(CoinTransaction.objects.filter(user=self.user, transaction_type='daily_login').count(), 1)

    def test_gap_resets_streak(self):
        d = datetime(2026, 11, 1).date()
        self._claim_on(d); self._claim_on(d + timedelta(days=1))
        self.assertEqual(self._claim_on(d + timedelta(days=3))['streak'], 1)

    def test_today_is_ist_not_utc(self):
        """At 20:00 UTC it is already the next day in IST (01:30)."""
        self.assertEqual(settings.TIME_ZONE, 'Asia/Kolkata')
        fake_now = datetime(2026, 11, 1, 20, 0, tzinfo=timezone.utc)
        with mock.patch('django.utils.timezone.now', return_value=fake_now):
            self.assertEqual(str(timezone.localdate()), '2026-11-02')
            self.client.post(reverse('check_daily_login'))
        self.user.userprofile.refresh_from_db()
        self.assertEqual(str(self.user.userprofile.last_login_date), '2026-11-02')


class ISTTimestampTests(TestCase):
    def test_reload_renders_same_ist_time_as_live(self):
        u1 = User.objects.create_user('t1', password='pw12345!')
        u2 = User.objects.create_user('t2', password='pw12345!')
        room = _stranger_room(u1, u2)
        msg = ChatMessage.objects.create(room=room, user=u1, content='time check',
                                         expires_at=timezone.now() + timedelta(hours=1))
        # 15:35 UTC == 9:05 PM IST
        ChatMessage.objects.filter(pk=msg.pk).update(timestamp=datetime(2026, 11, 1, 15, 35, tzinfo=timezone.utc))
        msg.refresh_from_db()
        self.assertEqual(format_time(msg.timestamp), '9:05 PM')
        self.assertEqual(iso_local(msg.timestamp), '2026-11-01T21:05:00+05:30')
        c = Client(); c.login(username='t2', password='pw12345!')
        html = c.get(reverse('chat_room', args=[room.room_id])).content.decode()
        self.assertIn("timestamp: '9:05 PM'", html)
        self.assertNotIn("timestamp: '3:35 PM'", html)
        data = c.get(reverse('get_chat_messages', args=[room.room_id])).json()
        m = [m for m in data['messages'] if m['content'] == 'time check'][0]
        self.assertEqual(m['time_display'], '9:05 PM')


class BenchInviteFromRoomTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='pw12345!')
        self.friend = User.objects.create_user('friend', password='pw12345!')
        self.bench = ChatRoom.objects.create(name='Private Bench: Porch', bench_name='Porch',
                                             room_type='private_bench', created_by=self.owner, max_users=4)
        self.bench.participants.add(self.owner)

    def test_invite_button_on_room_page_without_existing_invite(self):
        self.assertFalse(BenchInvite.objects.exists())
        c = Client(); c.login(username='owner', password='pw12345!')
        r = c.get(reverse('chat_room', args=[self.bench.room_id]))
        self.assertContains(r, 'id="show-invite-btn"')
        self.assertContains(r, 'id="invite-modal"')
        self.assertContains(r, reverse('create_bench_invite', args=[self.bench.room_id]))

    def test_non_creator_sees_no_invite_button(self):
        self.bench.participants.add(self.friend)
        c = Client(); c.login(username='friend', password='pw12345!')
        self.assertNotContains(c.get(reverse('chat_room', args=[self.bench.room_id])), 'id="show-invite-btn"')

    def test_full_invite_flow_with_csrf(self):
        c = Client(enforce_csrf_checks=True); c.login(username='owner', password='pw12345!')
        c.get(reverse('chat_room', args=[self.bench.room_id]))
        token = c.cookies['csrftoken'].value
        url = reverse('create_bench_invite', args=[self.bench.room_id])
        self.assertEqual(c.post(url, {'max_uses': 10}).status_code, 403)  # no CSRF token
        data = c.post(url, {'max_uses': 10, 'expires_in_days': 7}, HTTP_X_CSRFTOKEN=token).json()
        self.assertTrue(data['success'])
        f = Client(); f.login(username='friend', password='pw12345!')
        r = f.get(data['invite_url'].replace('http://testserver', ''))
        self.assertRedirects(r, reverse('chat_room', args=[self.bench.room_id]), fetch_redirect_response=False)
        self.assertTrue(self.bench.participants.filter(id=self.friend.id).exists())

    def test_non_creator_cannot_create_invite(self):
        self.bench.participants.add(self.friend)
        c = Client(); c.login(username='friend', password='pw12345!')
        data = c.post(reverse('create_bench_invite', args=[self.bench.room_id]), {'max_uses': 5}).json()
        self.assertFalse(data['success'])


class AudioBackButtonCacheHeaderTests(TestCase):
    """Item 5: authenticated pages must stay bfcache-eligible (no `no-store`) but
    still revalidate, so Back keeps the audio element alive without serving stale pages."""

    def test_authenticated_pages_are_no_cache_but_not_no_store(self):
        User.objects.create_user('listener', password='pw12345!')
        c = Client(); c.login(username='listener', password='pw12345!')
        r = c.get(reverse('kada'))
        cc = r['Cache-Control']
        self.assertIn('no-cache', cc)
        self.assertIn('private', cc)
        self.assertIn('must-revalidate', cc)
        self.assertNotIn('no-store', cc)

    def test_base_template_rechecks_session_on_bfcache_restore(self):
        User.objects.create_user('listener2', password='pw12345!')
        c = Client(); c.login(username='listener2', password='pw12345!')
        html = c.get(reverse('kada')).content.decode()
        self.assertIn('pageshow', html)
        self.assertIn('enhanced-audio-control.js', html)


class ChatRoomPhoneLayoutTests(TestCase):
    def test_send_button_overrides_global_full_width_btn(self):
        owner = User.objects.create_user('lay', password='pw12345!')
        room = ChatRoom.objects.create(room_type='private_bench', bench_name='B', created_by=owner, max_users=4)
        room.participants.add(owner)
        c = Client(); c.login(username='lay', password='pw12345!')
        html = c.get(reverse('chat_room', args=[room.room_id])).content.decode()
        self.assertIn('Phone fit:', html)
        self.assertRegex(html, r'#send-button,\s*\.chat-controls \.btn')
