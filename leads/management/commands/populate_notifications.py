from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from leads.models import Notification
from faker import Faker
import random
from django.utils import timezone

class Command(BaseCommand):
    help = 'Populate the database with dummy notifications'

    def handle(self, *args, **kwargs):
        # Create a Faker instance
        fake = Faker()

        # Get or create a default user
        try:
            user = User.objects.get(username='testuser')
        except User.DoesNotExist:
            user = User.objects.create_user(
                username='testuser', 
                email='testuser@example.com', 
                password='testpassword'
            )

        # Notification types
        notification_types = [
            'biometric', 'lead', 'approval', 'system'
        ]

        # Generate 50 dummy notifications
        notifications = []
        for _ in range(50):
            notification = Notification(
                user=user,
                message=self.generate_notification_message(fake, random.choice(notification_types)),
                is_read=random.choice([True, False]),
                created_at=timezone.now() - timezone.timedelta(days=random.randint(0, 30)),
                notification_type=random.choice(notification_types)
            )
            notifications.append(notification)

        # Bulk create notifications
        Notification.objects.bulk_create(notifications)

        self.stdout.write(self.style.SUCCESS(f'Successfully created {len(notifications)} dummy notifications'))

    def generate_notification_message(self, fake, notification_type):
        """Generate context-specific notification messages"""
        if notification_type == 'biometric':
            return f"New biometric record for {fake.name()} added in {fake.city()}"
        elif notification_type == 'lead':
            return f"Lead status updated for {fake.company()} - {random.choice(['Pending', 'In Progress', 'Approved'])}"
        elif notification_type == 'approval':
            return f"Approval request received from {fake.name()} for {fake.job()}"
        else:
            return f"System update: {fake.bs()}"
