from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.cache import cache
from chatkada.models import UserProfile


class LoginViewTests(TestCase):
    """Test login view functionality"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='correct123')
        UserProfile.objects.create(user=self.user, coins=100)
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

