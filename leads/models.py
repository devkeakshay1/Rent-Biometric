from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver

class Lead(models.Model):
    STATUS_CHOICES = [
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='leads')
    name = models.CharField(max_length=100, default='Unknown')
    email = models.EmailField(default='default@example.com')
    location = models.CharField(max_length=100, null=True, blank=True, default='Unspecified')
    phone = models.CharField(max_length=20, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    created_at = models.DateTimeField(default=timezone.now)
    
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

    def __str__(self):
        return f"{self.name} - {self.location} ({self.status})"

    def save(self, *args, **kwargs):
        # Update status timestamps
        if self.status == 'approved' and not self.approved_at:
            self.approved_at = timezone.now()
        elif self.status == 'rejected' and not self.rejected_at:
            self.rejected_at = timezone.now()
        
        super().save(*args, **kwargs)

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
    
    # Optional related objects
    lead = models.ForeignKey(Lead, on_delete=models.SET_NULL, null=True, blank=True)
    biometric = models.ForeignKey(Biometric, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f"{self.type} - {self.message[:50]}"

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Notifications"
