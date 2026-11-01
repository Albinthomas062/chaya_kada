from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.cache import cache
from chatkada.models import UserProfile
import json


class LoginViewTests(TestCase):
    """Test login view functionality"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='correct123')
        # UserProfile is created by post_save signal, just get it
        self.profile = self.user.userprofile
        cache.clear()
    
    def test_login_page_has_form_fields(self):
        """Test that GET /login/ contains username and password input fields"""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        # Check for username field
        self.assertContains(response, 'name="username"')
        # Check for password field
        self.assertContains(response, 'name="password"')
        # Check for CSRF token
        self.assertContains(response, 'csrfmiddlewaretoken')
    
    def test_valid_login_succeeds(self):
        """Test that valid credentials log the user in"""
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'correct123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith('/kada/'))
        
    def test_invalid_login_fails(self):
        """Test that invalid credentials show error"""
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'wrong'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid username or password')
    
    def test_open_redirect_prevented(self):
        """Test that open redirects to external sites are blocked"""
        # Test with https:// external domain
        response = self.client.post(reverse('login') + '?next=https://evil.example.com/', {
            'username': 'testuser',
            'password': 'correct123'
        }, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertFalse('evil.example.com' in response.url)
        self.assertTrue(response.url.endswith('/kada/'))
        
        # Test with // protocol-relative URL
        self.client.logout()
        response = self.client.post(reverse('login') + '?next=//evil.example.com/', {
            'username': 'testuser',
            'password': 'correct123'
        }, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertFalse('evil.example.com' in response.url)
        self.assertTrue(response.url.endswith('/kada/'))
    
    def test_ban_message_not_shown_with_wrong_password(self):
        """Test that banned users don't reveal ban status with wrong password (prevents enumeration)"""
        # Ban the user
        self.user.is_active = False
        self.user.save()
        
        # Try login with wrong password
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)
        # Should show generic error, not ban message
        self.assertContains(response, 'Invalid username or password')
        self.assertNotContains(response, 'banned')
    
    def test_ban_message_shown_with_correct_password(self):
        """Test that banned users see ban message with correct password"""
        # Ban the user
        self.user.is_active = False
        self.user.save()
        
        # Try login with correct password
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'correct123'
        })
        self.assertEqual(response.status_code, 200)
        # Should show ban message
        self.assertContains(response, 'banned')


class BuyItemTests(TestCase):
    """buy_item endpoint security and validation (CSRF actually enforced)."""

    def setUp(self):
        from chatkada.models import Item, Purchase
        self.Item, self.Purchase = Item, Purchase
        # enforce_csrf_checks=True: the default test client silently skips CSRF.
        self.client = Client(enforce_csrf_checks=True)
        self.user = User.objects.create_user(username='buyer', password='pass123')
        self.profile = self.user.userprofile
        self.profile.coins = 100
        self.profile.save()
        self.client.login(username='buyer', password='pass123')
        self.available_item = Item.objects.create(name='Test Snack', emoji='🍪', price=10, available=True)
        self.unavailable_item = Item.objects.create(name='Sold Out', emoji='🚫', price=5, available=False)
        # The shop page must hand out the CSRF cookie the JS reads.
        r = self.client.get(reverse('kada'))
        self.assertEqual(r.status_code, 200)
        self.assertIn('csrftoken', self.client.cookies)
        self.token = self.client.cookies['csrftoken'].value

    def _buy(self, payload, raw=False, token=True):
        kwargs = {'content_type': 'application/json'}
        if token:
            kwargs['HTTP_X_CSRFTOKEN'] = self.token
        body = payload if raw else json.dumps(payload)
        return self.client.post(reverse('buy_item'), data=body, **kwargs)

    def _assert_unchanged(self, coins=100):
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.coins, coins)
        self.assertEqual(self.Purchase.objects.filter(user=self.user).count(), 0)

    def test_buy_item_requires_csrf(self):
        r = self._buy({'item_id': self.available_item.id, 'quantity': 1}, token=False)
        self.assertEqual(r.status_code, 403)
        self._assert_unchanged()

    def test_buy_item_success(self):
        r = self._buy({'item_id': self.available_item.id, 'quantity': 1})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['success'])
        self.assertEqual(r.json()['coins'], 90)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.coins, 90)
        self.assertEqual(self.Purchase.objects.get(user=self.user).total_price, 10)

    def test_multi_quantity_charges_correctly(self):
        r = self._buy({'item_id': self.available_item.id, 'quantity': 3})
        self.assertEqual(r.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.coins, 70)

    def test_negative_quantity_rejected_no_free_coins(self):
        for q in (-10, -1, 0):
            r = self._buy({'item_id': self.available_item.id, 'quantity': q})
            self.assertEqual(r.status_code, 400, q)
            self.assertFalse(r.json()['success'])
        self._assert_unchanged()

    def test_fractional_quantity_rejected(self):
        for q in (1.5, 0.5, 2.0, '1.5'):
            r = self._buy({'item_id': self.available_item.id, 'quantity': q})
            self.assertEqual(r.status_code, 400, q)
        self._assert_unchanged()

    def test_quantity_exceeds_max(self):
        r = self._buy({'item_id': self.available_item.id, 'quantity': 11})
        self.assertEqual(r.status_code, 400)
        self._assert_unchanged()

    def test_string_bool_null_quantity_rejected(self):
        for q in ('bad', '', None, True, [], {}, '-5'):
            r = self._buy({'item_id': self.available_item.id, 'quantity': q})
            self.assertEqual(r.status_code, 400, repr(q))
        self._assert_unchanged()

    def test_invalid_json_rejected(self):
        for body in ('not json', '[1,2]', '"x"', '\xff'):
            r = self._buy(body, raw=True)
            self.assertEqual(r.status_code, 400, body)
        self._assert_unchanged()

    def test_bad_item_id(self):
        self.assertEqual(self._buy({'item_id': 'abc', 'quantity': 1}).status_code, 400)
        self.assertEqual(self._buy({'item_id': 999999, 'quantity': 1}).status_code, 404)
        self.assertEqual(self._buy({'quantity': 1}).status_code, 400)
        self._assert_unchanged()

    def test_unavailable_item_rejected(self):
        r = self._buy({'item_id': self.unavailable_item.id, 'quantity': 1})
        self.assertEqual(r.status_code, 400)
        self.assertIn('not available', r.json()['message'])
        self._assert_unchanged()

    def test_insufficient_coins(self):
        self.profile.coins = 5
        self.profile.save()
        r = self._buy({'item_id': self.available_item.id, 'quantity': 1})
        self.assertFalse(r.json()['success'])
        self.assertIn('Not enough coins', r.json()['message'])
        self._assert_unchanged(coins=5)

    def test_only_post_allowed(self):
        self.assertEqual(self.client.get(reverse('buy_item')).status_code, 405)


@override_settings(LOGIN_SOFT_DELAY_SECONDS=0)
class SiteLoginLockoutTests(TestCase):
    """Issue 2: /login/ lockout is per username+REMOTE_ADDR, not username-only."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='victim', password='rightpass1')

    def _post(self, password, ip, **extra):
        c = Client(REMOTE_ADDR=ip)
        return c, c.post(reverse('login'), {'username': 'victim', 'password': password}, **extra)

    def test_attacker_ip_locked_after_five(self):
        for _ in range(5):
            self._post('wrong', '10.0.0.66')
        _, r = self._post('rightpass1', '10.0.0.66')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Too many failed login attempts')

    def test_victim_on_other_ip_not_locked(self):
        for _ in range(10):
            self._post('wrong', '10.0.0.66')
        _, r = self._post('rightpass1', '10.0.0.7')
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.url.endswith('/kada/'))

    def test_distributed_attack_does_not_lock_account(self):
        # 30 failures spread over 30 IPs (above the 20 alert threshold)
        for i in range(30):
            self._post('wrong', f'10.1.0.{i}')
        _, r = self._post('rightpass1', '10.9.9.9')
        self.assertEqual(r.status_code, 302)

    def test_spoofed_forwarded_header_ignored(self):
        for _ in range(5):
            self._post('wrong', '10.0.0.66', HTTP_X_FORWARDED_FOR='1.2.3.4')
        # changing X-Forwarded-For does not escape the lock on the same REMOTE_ADDR
        _, r = self._post('rightpass1', '10.0.0.66', HTTP_X_FORWARDED_FOR='5.6.7.8')
        self.assertContains(r, 'Too many failed login attempts')

    def test_success_clears_ip_counter(self):
        for _ in range(4):
            self._post('wrong', '10.0.0.8')
        c, r = self._post('rightpass1', '10.0.0.8')
        self.assertEqual(r.status_code, 302)
        c.logout()
        for _ in range(4):
            self._post('wrong', '10.0.0.8')
        _, r = self._post('rightpass1', '10.0.0.8')
        self.assertEqual(r.status_code, 302)
