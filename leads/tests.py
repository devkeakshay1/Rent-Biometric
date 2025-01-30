from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Lead, Biometric, Notification
from .forms import LeadForm

class LeadViewTests(TestCase):
    def setUp(self):
        """
        Set up test data for lead-related tests
        """
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser', 
            password='12345'
        )
        self.client.login(username='testuser', password='12345')

    def test_create_lead_view(self):
        """
        Test lead creation view
        """
        url = reverse('create_lead')
        
        # Test GET request
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.context['form'], LeadForm)

        # Test valid POST request
        lead_data = {
            'name': 'John Doe',
            'email': 'john@example.com',
            'location': 'Test City',
            'phone': '1234567890',
            'status': 'new'
        }
        response = self.client.post(url, data=lead_data)
        
        # Check redirect and lead creation
        self.assertRedirects(response, reverse('home'))
        self.assertTrue(Lead.objects.filter(name='John Doe').exists())
        
        # Verify notification creation
        lead = Lead.objects.get(name='John Doe')
        self.assertTrue(Notification.objects.filter(lead=lead).exists())

    def test_update_lead_status(self):
        """
        Test lead status update functionality
        """
        # Create a test lead
        lead = Lead.objects.create(
            name='Test Lead', 
            email='test@example.com', 
            location='Test Location',
            user=self.user,
            status='new'
        )
        
        url = reverse('update_lead_status', args=[lead.id, 'approved'])
        response = self.client.get(url)
        
        # Refresh lead from database
        lead.refresh_from_db()
        
        # Check status update
        self.assertEqual(lead.status, 'approved')
        
        # Check biometric creation
        self.assertTrue(Biometric.objects.filter(lead=lead).exists())
        
        # Check notification creation
        self.assertTrue(Notification.objects.filter(
            lead=lead, 
            message__contains='Lead status changed'
        ).exists())

class BiometricViewTests(TestCase):
    def setUp(self):
        """
        Set up test data for biometric-related tests
        """
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser', 
            password='12345'
        )
        self.client.login(username='testuser', password='12345')

    def test_process_biometric(self):
        """
        Test biometric processing functionality
        """
        # Create a test lead and biometric
        lead = Lead.objects.create(
            name='Test Lead', 
            email='test@example.com', 
            location='Test Location',
            user=self.user,
            status='new'
        )
        biometric = Biometric.objects.create(
            name='Test Biometric',
            lead=lead,
            user=self.user,
            status='pending'
        )
        
        # Test approval
        url = reverse('process_biometric', args=[biometric.id, 'approve'])
        response = self.client.post(url)
        
        # Refresh biometric from database
        biometric.refresh_from_db()
        lead.refresh_from_db()
        
        # Check status updates
        self.assertEqual(biometric.status, 'approved')
        self.assertEqual(lead.status, 'approved')
        
        # Check notification creation
        self.assertTrue(Notification.objects.filter(
            biometric=biometric, 
            message__contains='Biometric status changed'
        ).exists())
        
        # Test rejection
        biometric.status = 'pending'
        biometric.save()
        
        url = reverse('process_biometric', args=[biometric.id, 'reject'])
        response = self.client.post(url, data={'rejection_reason': 'Test reason'})
        
        # Refresh biometric from database
        biometric.refresh_from_db()
        lead.refresh_from_db()
        
        # Check status updates
        self.assertEqual(biometric.status, 'rejected')
        self.assertEqual(lead.status, 'rejected')
        self.assertEqual(biometric.rejection_reason, 'Test reason')

class GlobalSearchTests(TestCase):
    def setUp(self):
        """
        Set up test data for global search
        """
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser', 
            password='12345'
        )
        self.client.login(username='testuser', password='12345')

        # Create test data
        lead = Lead.objects.create(
            name='John Doe', 
            email='john@example.com', 
            location='Test City',
            user=self.user
        )
        biometric = Biometric.objects.create(
            name='John Biometric',
            lead=lead,
            user=self.user
        )
        Notification.objects.create(
            user=self.user,
            lead=lead,
            message='Test Notification'
        )

    def test_global_search(self):
        """
        Test global search functionality
        """
        url = reverse('global_search')
        
        # Test search with 'John'
        response = self.client.get(url, {'q': 'John'})
        
        self.assertEqual(response.status_code, 200)
        
        # Check context data
        self.assertIn('leads', response.context)
        self.assertIn('biometrics', response.context)
        self.assertIn('notifications', response.context)
        
        # Verify results
        leads = response.context['leads']
        biometrics = response.context['biometrics']
        notifications = response.context['notifications']
        
        self.assertTrue(leads.exists())
        self.assertTrue(biometrics.exists())
        self.assertTrue(notifications.exists())
        
        # Test empty search
        response = self.client.get(url, {'q': ''})
        self.assertEqual(response.status_code, 200)

class ErrorHandlerTests(TestCase):
    def setUp(self):
        """
        Set up test client
        """
        self.client = Client()

    def test_error_handlers(self):
        """
        Test custom error handler views
        """
        # These tests simulate error conditions
        response = self.client.get('/non-existent-page/')
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, 'errors/404.html')

        # Note: Some error handlers like 500 are difficult to test automatically
        # They typically require simulating server errors
