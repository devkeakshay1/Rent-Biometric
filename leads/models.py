from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Lead(models.Model):
    # Existing fields...
    view_count = models.IntegerField(default=0)
    last_viewed_at = models.DateTimeField(null=True, blank=True)
    interaction_score = models.FloatField(default=0.0)
    
    def increment_view(self, user):
        """Track lead views and calculate interaction score"""
        self.view_count += 1
        self.last_viewed_at = timezone.now()
        
        if user.is_authenticated:
            self.interaction_score += 0.1
        
        self.save()
    
    def get_interaction_status(self):
        """Provide an interactive status based on interaction score"""
        if self.interaction_score < 1:
            return 'Low Engagement'
        elif self.interaction_score < 3:
            return 'Medium Engagement'
        else:
            return 'High Engagement'

class Biometric(models.Model):
    # Existing fields...
    verification_attempts = models.IntegerField(default=0)
    last_verification_attempt = models.DateTimeField(null=True, blank=True)
    verification_confidence = models.FloatField(default=0.0, help_text='Confidence score of biometric verification')
    
    def log_verification_attempt(self, success=False, confidence=0.0):
        """Log biometric verification attempts"""
        self.verification_attempts += 1
        self.last_verification_attempt = timezone.now()
        
        if success:
            self.verification_confidence = min(1.0, self.verification_confidence + confidence)
        else:
            self.verification_confidence = max(0.0, self.verification_confidence - 0.1)
        
        self.save()
    
    def get_verification_status(self):
        """Provide an interactive status based on verification confidence"""
        if self.verification_confidence < 0.3:
            return 'Low Confidence'
        elif self.verification_confidence < 0.7:
            return 'Medium Confidence'
        else:
            return 'High Confidence'

class Notification(models.Model):
    # Existing fields...
    is_read = models.BooleanField(default=False)
    priority = models.IntegerField(default=1, help_text='Notification priority (1-5)')
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.save()
    
    @classmethod
    def get_unread_count(cls, user):
        """Get count of unread notifications for a user"""
        return cls.objects.filter(user=user, is_read=False).count()
    
    def escalate_priority(self):
        """Increase notification priority"""
        self.priority = min(5, self.priority + 1)
        self.save()

class Lead(models.Model):
    STATUS_CHOICES = [
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ]

    VALIDITY_CHOICES = [
        ('1_hr', '1 Hr'),
        ('3_hr', '3 Hr'),
        ('6_hr', '6 Hr'),
        ('12_hr', '12 Hr'),
        ('1_day', '1 Day'),
        ('2_day', '2 Day'),
        ('1_week', '1 Week')
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='leads')
    name = models.CharField(max_length=100, default='Unknown')
    email = models.EmailField(default='default@example.com')
    phone = models.CharField(max_length=20, null=True, blank=True)
    landmark = models.CharField(max_length=200, null=True, blank=True, verbose_name='Landmark')
    city = models.CharField(max_length=100, null=True, blank=True, verbose_name='City')
    state = models.CharField(max_length=100, null=True, blank=True, verbose_name='State')
    country = models.CharField(max_length=100, null=True, blank=True, verbose_name='Country')
    pin_code = models.CharField(max_length=10, null=True, blank=True, verbose_name='PIN Code')
    map_location = models.URLField(null=True, blank=True, verbose_name='Map Location')
    location = models.CharField(max_length=100, null=True, blank=True, default='Unspecified')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    created_at = models.DateTimeField(default=timezone.now)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Lead Price')
    validity = models.CharField(max_length=20, choices=VALIDITY_CHOICES, null=True, blank=True, verbose_name='Lead Validity')
    view_count = models.IntegerField(default=0)
    last_viewed_at = models.DateTimeField(null=True, blank=True)
    interaction_score = models.FloatField(default=0.0)
    
    def __str__(self):
        return f"{self.name} - {self.email}"

    def save(self, *args, **kwargs):
        # Automatically create a biometric if lead is approved
        super().save(*args, **kwargs)
        if self.status == 'approved' and not hasattr(self, 'biometric'):
            Biometric.objects.create(
                user=self.user or User.objects.first(),
                name=self.name,
                location=self.location,
                status='pending'
            )

    def increment_view(self, user):
        """Track lead views and calculate interaction score"""
        self.view_count += 1
        self.last_viewed_at = timezone.now()
        
        # Calculate interaction score based on user actions
        if user.is_authenticated:
            # More interactions = higher score
            self.interaction_score += 0.1
        
        self.save()
    
    def get_interaction_status(self):
        """Provide an interactive status based on interaction score"""
        if self.interaction_score < 1:
            return 'Low Engagement'
        elif self.interaction_score < 3:
            return 'Medium Engagement'
        else:
            return 'High Engagement'

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Leads"

class Biometric(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ]

    lead = models.OneToOneField(Lead, on_delete=models.CASCADE, null=True, blank=True, related_name='biometric')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='biometrics')
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(null=True, blank=True)
    verification_attempts = models.IntegerField(default=0)
    last_verification_attempt = models.DateTimeField(null=True, blank=True)
    verification_confidence = models.FloatField(default=0.0, help_text='Confidence score of biometric verification')
    
    def __str__(self):
        return f"{self.name} - {self.location} ({self.status})"

    def save(self, *args, **kwargs):
        # Update status timestamps
        if self.status == 'approved' and not self.approved_at:
            self.approved_at = timezone.now()
        elif self.status == 'rejected' and not self.rejected_at:
            self.rejected_at = timezone.now()
        
        super().save(*args, **kwargs)

    def log_verification_attempt(self, success=False, confidence=0.0):
        """Log biometric verification attempts"""
        self.verification_attempts += 1
        self.last_verification_attempt = timezone.now()
        
        if success:
            # Update confidence score
            self.verification_confidence = min(1.0, self.verification_confidence + confidence)
        else:
            # Decrease confidence if verification fails
            self.verification_confidence = max(0.0, self.verification_confidence - 0.1)
        
        self.save()
    
    def get_verification_status(self):
        """Provide an interactive status based on verification confidence"""
        if self.verification_confidence < 0.3:
            return 'Low Confidence'
        elif self.verification_confidence < 0.7:
            return 'Medium Confidence'
        else:
            return 'High Confidence'

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Biometrics"

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('lead_assigned', 'Lead Assigned'),
        ('lead_status_change', 'Lead Status Changed'),
        ('biometric_status_change', 'Biometric Status Changed'),
        ('weekly_report', 'Weekly Report'),
        ('system_alert', 'System Alert')
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    priority = models.IntegerField(default=1, help_text='Notification priority (1-5)')
    
    # Optional related objects
    lead = models.ForeignKey(Lead, on_delete=models.SET_NULL, null=True, blank=True)
    biometric = models.ForeignKey(Biometric, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f"{self.type} - {self.message[:50]}"

    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.save()
    
    @classmethod
    def get_unread_count(cls, user):
        """Get count of unread notifications for a user"""
        return cls.objects.filter(user=user, is_read=False).count()
    
    def escalate_priority(self):
        """Increase notification priority"""
        self.priority = min(5, self.priority + 1)
        self.save()

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Notifications"
