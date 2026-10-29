from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from chatkada.models import Item, UserProfile, CoinTransaction, ChatRoom
from chatkada import admin_views
import time
from io import BytesIO
from PIL import Image


class AdminPermissionTests(TestCase):
    """Test that non-staff users are blocked from admin views"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='normaluser', password='test123')
        # Profile created by signal, just get it
        self.profile = self.user.userprofile
        
        self.staff_user = User.objects.create_user(username='staffuser', password='test123', is_staff=True)
        self.staff_profile = self.staff_user.userprofile
        
    def test_anonymous_blocked_from_dashboard(self):
        response = self.client.get(reverse('custom_admin_dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirected to login
        
    def test_normal_user_blocked_from_dashboard(self):
        self.client.login(username='normaluser', password='test123')
        response = self.client.get(reverse('custom_admin_dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirected to login
        
    def test_staff_can_access_dashboard(self):
        self.client.login(username='staffuser', password='test123')
        response = self.client.get(reverse('custom_admin_dashboard'))
        self.assertEqual(response.status_code, 200)
        
    def test_anonymous_blocked_from_items(self):
        response = self.client.get(reverse('manage_items'))
        self.assertEqual(response.status_code, 302)
        
    def test_normal_user_blocked_from_items(self):
        self.client.login(username='normaluser', password='test123')
        response = self.client.get(reverse('manage_items'))
        self.assertEqual(response.status_code, 302)
        
    def test_staff_can_access_items(self):
        self.client.login(username='staffuser', password='test123')
        response = self.client.get(reverse('manage_items'))
        self.assertEqual(response.status_code, 200)
        
    def test_anonymous_blocked_from_users(self):
        response = self.client.get(reverse('manage_users'))
        self.assertEqual(response.status_code, 302)
        
    def test_normal_user_blocked_from_users(self):
        self.client.login(username='normaluser', password='test123')
        response = self.client.get(reverse('manage_users'))
        self.assertEqual(response.status_code, 302)


class AdminLoginTests(TestCase):
    """Test admin login with rate limiting"""
    
    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(username='admin', password='correct', is_staff=True)
        # Clear cache (used for rate limiting) before each test
        from django.core.cache import cache
        cache.clear()
        
    def test_valid_login_succeeds(self):
        response = self.client.post(reverse('custom_admin_login'), {
            'username': 'admin',
            'password': 'correct'
        })
        self.assertEqual(response.status_code, 302)  # Redirect on success
        self.assertEqual(response.url, reverse('custom_admin_dashboard'))
        
    def test_invalid_login_shows_error(self):
        response = self.client.post(reverse('custom_admin_login'), {
            'username': 'admin',
            'password': 'wrong'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid credentials')
        
    def test_lockout_after_five_attempts(self):
        # Make 5 failed attempts
        for i in range(5):
            self.client.post(reverse('custom_admin_login'), {
                'username': 'admin',
                'password': 'wrong'
            })
        
        # 6th attempt should be locked out
        response = self.client.post(reverse('custom_admin_login'), {
            'username': 'admin',
            'password': 'wrong'
        })
        self.assertContains(response, 'locked')
        
        # Even correct password should be locked
        response = self.client.post(reverse('custom_admin_login'), {
            'username': 'admin',
            'password': 'correct'
        })
        self.assertContains(response, 'locked')


class ItemCRUDTests(TestCase):
    """Test item creation, reading, updating, deletion"""
    
    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(username='staff', password='test123', is_staff=True)
        # Profile created by signal
        self.client.login(username='staff', password='test123')
        
    def test_create_item_without_image(self):
        response = self.client.post(reverse('add_item'), {
            'name': 'Test Chai',
            'category': 'chai',
            'price': 10,
            'emoji': '☕',
            'description': 'Test description',
            'available': True,
            'can_be_shared': True,
            'sort_order': 0,
        })
        self.assertEqual(response.status_code, 302)  # Redirect on success
        
        item = Item.objects.get(name='Test Chai')
        self.assertEqual(item.price, 10)
        self.assertEqual(item.category, 'chai')
        self.assertFalse(item.image)  # No image
        
    def test_create_item_with_valid_image(self):
        # Create a small test image
        img = Image.new('RGB', (100, 100), color='red')
        img_io = BytesIO()
        img.save(img_io, format='PNG')
        img_io.seek(0)
        
        image_file = SimpleUploadedFile(
            'test.png',
            img_io.read(),
            content_type='image/png'
        )
        
        response = self.client.post(reverse('add_item'), {
            'name': 'Chai with Image',
            'category': 'chai',
            'price': 15,
            'emoji': '☕',
            'image': image_file,
            'available': True,
            'can_be_shared': True,
            'sort_order': 0,
        })
        
        self.assertEqual(response.status_code, 302)
        item = Item.objects.get(name='Chai with Image')
        self.assertTrue(item.image)  # Has image
        
    def test_reject_large_image(self):
        # Create image >5MB (simulate)
        large_data = b'x' * (6 * 1024 * 1024)  # 6MB
        image_file = SimpleUploadedFile('large.png', large_data, content_type='image/png')
        
        response = self.client.post(reverse('add_item'), {
            'name': 'Chai Large',
            'category': 'chai',
            'price': 10,
            'emoji': '☕',
            'image': image_file,
            'available': True,
            'can_be_shared': True,
            'sort_order': 0,
        })
        
        # Should show error, not redirect
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'too large')
        
    def test_reject_non_image_file(self):
        text_file = SimpleUploadedFile('test.txt', b'not an image', content_type='text/plain')
        
        response = self.client.post(reverse('add_item'), {
            'name': 'Chai Text',
            'category': 'chai',
            'price': 10,
            'emoji': '☕',
            'image': text_file,
            'available': True,
            'can_be_shared': True,
            'sort_order': 0,
        })
        
        self.assertEqual(response.status_code, 200)
        # Django's actual error message
        self.assertIn('valid image', response.content.decode().lower())
        
    def test_edit_item(self):
        item = Item.objects.create(
            name='Original',
            category='chai',
            price=10,
            emoji='☕'
        )
        
        response = self.client.post(reverse('edit_item', args=[item.id]), {
            'name': 'Updated',
            'category': 'snacks',
            'price': 20,
            'emoji': '🍪',
            'available': True,
            'can_be_shared': True,
            'sort_order': 0,
        })
        
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.name, 'Updated')
        self.assertEqual(item.price, 20)
        
    def test_toggle_availability(self):
        item = Item.objects.create(
            name='Test',
            category='chai',
            price=10,
            emoji='☕',
            available=True
        )
        
        # Toggle to hidden
        response = self.client.post(
            reverse('toggle_item_availability', args=[item.id]),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertFalse(item.available)
        
    def test_soft_delete_item(self):
        item = Item.objects.create(
            name='To Delete',
            category='chai',
            price=10,
            emoji='☕',
            available=True
        )
        
        response = self.client.post(reverse('delete_item', args=[item.id]), {
            'soft_delete': '1'
        })
        
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertFalse(item.available)  # Soft deleted (hidden)
        
        # Item still exists
        self.assertTrue(Item.objects.filter(id=item.id).exists())


class KadaViewTests(TestCase):
    """Test that /kada/ only shows available items, ordered correctly"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='test123')
        # Profile created by signal
        self.profile = self.user.userprofile
        
        # Create items with different availability and sort_order
        self.visible_item1 = Item.objects.create(
            name='Visible 1',
            category='chai',
            price=10,
            emoji='☕',
            available=True,
            sort_order=1
        )
        
        self.visible_item2 = Item.objects.create(
            name='Visible 2',
            category='chai',
            price=15,
            emoji='☕',
            available=True,
            sort_order=0  # Should appear first
        )
        
        self.hidden_item = Item.objects.create(
            name='Hidden',
            category='chai',
            price=20,
            emoji='☕',
            available=False
        )
        
    def test_hidden_item_not_in_kada(self):
        self.client.login(username='testuser', password='test123')
        response = self.client.get(reverse('kada'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Visible 1')
        self.assertContains(response, 'Visible 2')
        self.assertNotContains(response, 'Hidden')
        
    def test_items_ordered_by_sort_order(self):
        self.client.login(username='testuser', password='test123')
        response = self.client.get(reverse('kada'))
        
        content = response.content.decode()
        # Visible 2 (sort_order=0) should appear before Visible 1 (sort_order=1)
        pos_v2 = content.find('Visible 2')
        pos_v1 = content.find('Visible 1')
        
        self.assertGreater(pos_v1, pos_v2)  # V1 comes after V2


class CoinAdjustmentTests(TestCase):
    """Test coin adjustment with audit trail"""
    
    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(username='staff', password='test123', is_staff=True)
        self.client.login(username='staff', password='test123')
        
        self.user = User.objects.create_user(username='testuser', password='test123')
        # Profile created by signal
        self.profile = self.user.userprofile
        self.profile.coins = 100
        self.profile.save()
        
    def test_adjust_coins_creates_audit_record(self):
        response = self.client.post(reverse('adjust_user_coins', args=[self.user.id]), {
            'amount': 50,
            'reason': 'Bonus for feedback'
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Check coins updated
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.coins, 150)
        
        # Check audit record created
        transaction = CoinTransaction.objects.filter(
            user=self.user,
            amount=50
        ).first()
        
        self.assertIsNotNone(transaction)
        self.assertIn('Bonus for feedback', transaction.description)
        
    def test_deduct_coins(self):
        response = self.client.post(reverse('adjust_user_coins', args=[self.user.id]), {
            'amount': -30,
            'reason': 'Penalty'
        })
        
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.coins, 70)
        
    def test_coin_adjust_requires_reason(self):
        # Without reason, should be rejected or use default
        response = self.client.post(reverse('adjust_user_coins', args=[self.user.id]), {
            'amount': 50,
            'reason': ''
        })
        
        # Should redirect or show error
        # If it redirects, check no transaction was created
        if response.status_code == 302:
            transaction = CoinTransaction.objects.filter(user=self.user, amount=50).first()
            # If transaction exists, reason should not be empty
            if transaction:
                self.assertTrue(transaction.description)


class UserBanTests(TestCase):
    """Test that banned users cannot login"""
    
    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(username='staff', password='test123', is_staff=True)
        self.user = User.objects.create_user(username='testuser', password='test123')
        # Profile created by signal
        
    def test_ban_user(self):
        self.client.login(username='staff', password='test123')
        
        # Ban the user
        response = self.client.post(reverse('toggle_user_ban', args=[self.user.id]))
        self.assertEqual(response.status_code, 302)
        
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        
    def test_banned_user_cannot_login(self):
        self.user.is_active = False
        self.user.save()
        
        # Try to login
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'test123'
        })
        
        # Should not be logged in
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        
    def test_cannot_ban_staff_user(self):
        staff2 = User.objects.create_user(username='staff2', password='test123', is_staff=True)
        
        self.client.login(username='staff', password='test123')
        
        # Try to ban staff user
        response = self.client.post(reverse('toggle_user_ban', args=[staff2.id]))
        
        # Should show error or redirect without banning
        staff2.refresh_from_db()
        self.assertTrue(staff2.is_active)  # Still active


class RoomManagementTests(TestCase):
    """Test room closing"""
    
    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(username='staff', password='test123', is_staff=True)
        self.client.login(username='staff', password='test123')
        
        self.user = User.objects.create_user(username='testuser', password='test123')
        self.room = ChatRoom.objects.create(
            name='Test Room',
            room_type='bench',
            created_by=self.user,
            is_active=True
        )
        
    def test_close_room(self):
        response = self.client.post(reverse('close_room', args=[self.room.room_id]))
        
        self.assertEqual(response.status_code, 302)
        self.room.refresh_from_db()
        self.assertFalse(self.room.is_active)
