from django.core.management.base import BaseCommand
from chatkada.models import Item

class Command(BaseCommand):
    help = 'Populate the database with initial items'

    def handle(self, *args, **options):
        # Delete existing items to avoid duplicates
        Item.objects.all().delete()
        
        items = [
            # Chai items
            {
                'name': 'Cutting Chai',
                'price': 15,
                'category': 'chai',
                'emoji': '☕',
                'description': 'Traditional small tea served in cutting glass',
                'available': True,
                'can_be_shared': True
            },
            {
                'name': 'Masala Chai',
                'price': 20,
                'category': 'chai',
                'emoji': '🫖',
                'description': 'Spiced tea with cardamom, ginger, and love',
                'available': True,
                'can_be_shared': True
            },
            {
                'name': 'Ginger Chai',
                'price': 18,
                'category': 'chai',
                'emoji': '🍵',
                'description': 'Fresh ginger tea for cold weather',
                'available': True,
                'can_be_shared': True
            },
            {
                'name': 'Kulhad Chai',
                'price': 25,
                'category': 'chai',
                'emoji': '🏺',
                'description': 'Tea served in traditional clay cup',
                'available': True,
                'can_be_shared': True
            },
            {
                'name': 'Elaichi Chai',
                'price': 22,
                'category': 'chai',
                'emoji': '🌿',
                'description': 'Cardamom flavored aromatic tea',
                'available': True,
                'can_be_shared': True
            },
            
            # Snack items
            {
                'name': 'Vada Pav',
                'price': 30,
                'category': 'snacks',
                'emoji': '🍔',
                'description': 'Mumbai\'s favorite street food',
                'available': True,
                'can_be_shared': True
            },
            {
                'name': 'Samosa',
                'price': 25,
                'category': 'snacks',
                'emoji': '🥟',
                'description': 'Crispy fried pastry with spicy filling',
                'available': True,
                'can_be_shared': True
            },
            {
                'name': 'Pakoda',
                'price': 35,
                'category': 'snacks',
                'emoji': '🍤',
                'description': 'Deep fried fritters perfect for rain',
                'available': True,
                'can_be_shared': True
            },
            {
                'name': 'Bhel Puri',
                'price': 40,
                'category': 'snacks',
                'emoji': '🥗',
                'description': 'Puffed rice snack with chutneys',
                'available': True,
                'can_be_shared': True
            },
            {
                'name': 'Pav Bhaji',
                'price': 50,
                'category': 'snacks',
                'emoji': '🍛',
                'description': 'Spicy curry with buttered bread',
                'available': True,
                'can_be_shared': True
            },
            {
                'name': 'Aloo Tikki',
                'price': 28,
                'category': 'snacks',
                'emoji': '🥔',
                'description': 'Crispy potato patties with chutney',
                'available': True,
                'can_be_shared': True
            },
            {
                'name': 'Bread Pakoda',
                'price': 32,
                'category': 'snacks',
                'emoji': '🍞',
                'description': 'Bread slices dipped in gram flour batter',
                'available': True,
                'can_be_shared': True
            },
            
            # Sweet items
            {
                'name': 'Jalebi',
                'price': 45,
                'category': 'sweets',
                'emoji': '🍩',
                'description': 'Spiral shaped sweet soaked in sugar syrup',
                'available': True,
                'can_be_shared': True
            },
            {
                'name': 'Gulab Jamun',
                'price': 40,
                'category': 'sweets',
                'emoji': '🍡',
                'description': 'Milk solid balls in rose flavored syrup',
                'available': True,
                'can_be_shared': True
            },
            {
                'name': 'Rasgulla',
                'price': 35,
                'category': 'sweets',
                'emoji': '⚪',
                'description': 'Spongy cheese balls in sugar syrup',
                'available': True,
                'can_be_shared': True
            },
            {
                'name': 'Kaju Katli',
                'price': 60,
                'category': 'sweets',
                'emoji': '💎',
                'description': 'Premium cashew fudge',
                'available': True,
                'can_be_shared': True
            },
            {
                'name': 'Laddu',
                'price': 38,
                'category': 'sweets',
                'emoji': '🟡',
                'description': 'Traditional round sweet made with gram flour',
                'available': True,
                'can_be_shared': True
            },
            {
                'name': 'Barfi',
                'price': 42,
                'category': 'sweets',
                'emoji': '🟤',
                'description': 'Rich milk-based sweet',
                'available': True,
                'can_be_shared': True
            },
        ]

        created_count = 0
        for item_data in items:
            item, created = Item.objects.get_or_create(
                name=item_data['name'],
                defaults=item_data
            )
            if created:
                created_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {created_count} items in the Kada menu!'
            )
        )
