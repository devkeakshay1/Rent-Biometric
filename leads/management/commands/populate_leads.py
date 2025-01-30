from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from leads.models import Lead
from faker import Faker
import random
from django.utils import timezone

class Command(BaseCommand):
    help = 'Populates the database with dummy lead data'

    def handle(self, *args, **kwargs):
        # Clear existing leads
        Lead.objects.all().delete()
        
        # Create Faker instance
        fake = Faker()
        
        # Predefined locations
        locations = [
            'New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix', 
            'Philadelphia', 'San Antonio', 'San Diego', 'Dallas', 'San Jose',
            'Austin', 'Jacksonville', 'San Francisco', 'Columbus', 'Fort Worth',
            'Indianapolis', 'Charlotte', 'Seattle', 'Denver', 'Washington D.C.'
        ]
        
        # Status choices from the model
        status_choices = [choice[0] for choice in Lead.STATUS_CHOICES]
        
        # Create 500 leads
        leads_to_create = []
        for _ in range(500):
            lead = Lead(
                name=fake.name(),
                email=fake.email(),
                location=random.choice(locations),
                status=random.choice(status_choices),
                created_at=timezone.now() - timezone.timedelta(
                    days=random.randint(0, 365),
                    hours=random.randint(0, 24),
                    minutes=random.randint(0, 60)
                )
            )
            leads_to_create.append(lead)
        
        # Bulk create leads for efficiency
        Lead.objects.bulk_create(leads_to_create)
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created 500 leads'))
