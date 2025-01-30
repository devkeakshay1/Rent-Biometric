import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'biometric_leads.settings')
django.setup()

from django.contrib.auth.models import User
from leads.models import Notification, Lead, Biometric

def create_sample_notifications():
    # Get or create a user
    user, created = User.objects.get_or_create(username='admin')
    
    # Create sample notifications
    notifications_data = [
        {
            'user': user,
            'message': 'New lead received from John Doe',
            'notification_type': 'lead',
        },
        {
            'user': user,
            'message': 'Biometric data processing completed',
            'notification_type': 'biometric',
        },
        {
            'user': user,
            'message': 'System update available',
            'notification_type': 'system',
        }
    ]
    
    # Bulk create notifications
    Notification.objects.bulk_create([
        Notification(**data) for data in notifications_data
    ])
    
    print(f"Created {len(notifications_data)} sample notifications")

if __name__ == '__main__':
    create_sample_notifications()
