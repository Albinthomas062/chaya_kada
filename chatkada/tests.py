from django.test import TestCase, Client
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
    """Test buy_item endpoint security and validation"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='buyer', password='pass123')
        self.profile = self.user.userprofile
        self.profile.coins = 100
        self.profile.save()
        self.client.login(username='buyer', password='pass123')
        
        # Import Item and Purchase models
        from chatkada.models import Item
        self.Item = Item
        
        # Create test items
        self.available_item = Item.objects.create(
            name='Test Snack',
            emoji='🍪',
            price=10,
            available=True
        )
        self.unavailable_item = Item.objects.create(
            name='Sold Out',
            emoji='🚫',
            price=5,
            available=False
        )
    
    def test_buy_item_requires_csrf(self):
        """Test that CSRF protection is enabled"""
        response = self.client.post(
            reverse('buy_item'),
            data=json.dumps({'item_id': self.available_item.id, 'quantity': 1}),
            content_type='application/json'
        )
        # Without CSRF token, should fail
        self.assertEqual(response.status_code, 403)
    
    def test_buy_item_success(self):
        """Test successful purchase"""
        response = self.client.post(
            reverse('buy_item'),
            data=json.dumps({'item_id': self.available_item.id, 'quantity': 1}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=self.client.cookies.get('csrftoken', '').value
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['coins'], 90)  # 100 - 10
        
        # Verify profile updated
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.coins, 90)
    
    def test_negative_quantity_adds_coins(self):
        """Test that negative quantity is rejected"""
        response = self.client.post(
            reverse('buy_item'),
            data=json.dumps({'item_id': self.available_item.id, 'quantity': -10}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=self.client.cookies.get('csrftoken', '').value
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        
        # Coins should not change
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.coins, 100)
    
    def test_fractional_quantity_rejected(self):
        """Test that fractional quantity is rejected"""
        response = self.client.post(
            reverse('buy_item'),
            data=json.dumps({'item_id': self.available_item.id, 'quantity': 1.5}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=self.client.cookies.get('csrftoken', '').value
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
    
    def test_quantity_exceeds_max(self):
        """Test that quantity over 10 is rejected"""
        response = self.client.post(
            reverse('buy_item'),
            data=json.dumps({'item_id': self.available_item.id, 'quantity': 11}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=self.client.cookies.get('csrftoken', '').value
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
    
    def test_string_quantity_rejected(self):
        """Test that string quantity is rejected"""
        response = self.client.post(
            reverse('buy_item'),
            data=json.dumps({'item_id': self.available_item.id, 'quantity': 'bad'}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=self.client.cookies.get('csrftoken', '').value
        )
        self.assertEqual(response.status_code, 400)
    
    def test_invalid_json_rejected(self):
        """Test that invalid JSON returns 400"""
        response = self.client.post(
            reverse('buy_item'),
            data='not json',
            content_type='application/json',
            HTTP_X_CSRFTOKEN=self.client.cookies.get('csrftoken', '').value
        )
        self.assertEqual(response.status_code, 400)
    
    def test_unavailable_item_rejected(self):
        """Test that unavailable items cannot be purchased"""
        response = self.client.post(
            reverse('buy_item'),
            data=json.dumps({'item_id': self.unavailable_item.id, 'quantity': 1}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=self.client.cookies.get('csrftoken', '').value
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('not available', data['message'])
    
    def test_insufficient_coins(self):
        """Test that purchase fails with insufficient coins"""
        self.profile.coins = 5
        self.profile.save()
        
        response = self.client.post(
            reverse('buy_item'),
            data=json.dumps({'item_id': self.available_item.id, 'quantity': 1}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=self.client.cookies.get('csrftoken', '').value
        )
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('Not enough coins', data['message'])
    
    def test_only_post_allowed(self):
        """Test that only POST requests are allowed"""
        response = self.client.get(reverse('buy_item'))
        self.assertEqual(response.status_code, 405)  # Method Not Allowed

