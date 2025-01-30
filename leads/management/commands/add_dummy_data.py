from django.core.management.base import BaseCommand
from leads.models import Lead

class Command(BaseCommand):
    help = 'Add dummy data to the Lead model'

    def handle(self, *args, **kwargs):
        Lead.objects.create(location='New York', status='agree')
        Lead.objects.create(location='Los Angeles', status='hold')
        Lead.objects.create(location='Chicago', status='reject')
        Lead.objects.create(location='Houston', status='agree')
        Lead.objects.create(location='Phoenix', status='hold')
        self.stdout.write(self.style.SUCCESS('Successfully added dummy data'))
