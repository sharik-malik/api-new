from django.db import models
from api.users.models import *
from api.property.models import *


class Default(models.Model):
    added_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "notifications"
        abstract = True


class NotificationTemplate(Default):
    site = models.ForeignKey(NetworkDomain, related_name="notification_template_site", on_delete=models.CASCADE,
                             null=True, blank=True)
    event = models.ForeignKey(LookupEvent, related_name="notification_template_event", on_delete=models.CASCADE)
    email_subject = models.CharField(max_length=255)
    email_content = models.TextField()
    notification_subject = models.CharField(max_length=255, null=True, blank=True)
    notification_text = models.TextField(null=True, blank=True)
    notification_subject_ar = models.CharField(max_length=255, null=True, blank=True)
    notification_text_ar = models.TextField(null=True, blank=True)
    push_notification_text = models.TextField(null=True, blank=True)
    added_by = models.ForeignKey(Users, related_name="notification_template_added_by", on_delete=models.CASCADE,
                                 db_column="added_by")
    updated_by = models.ForeignKey(Users, related_name="notification_template_updated_by", on_delete=models.CASCADE,
                                   db_column="updated_by")
    status = models.ForeignKey(LookupStatus, related_name="notification_template_status", on_delete=models.CASCADE)

    class Meta:
        db_table = "notification_template"


class EventNotification(Default):
    domain = models.ForeignKey(NetworkDomain, related_name="event_notification_domain", on_delete=models.CASCADE, null=True, blank=True)
    property = models.ForeignKey(PropertyListing, related_name="event_notification_property", on_delete=models.CASCADE, null=True, blank=True)
    notification_for = models.IntegerField(choices=((1, "Buyer"), (2, "Seller")), default=1)
    title = models.TextField(null=True, blank=True)
    content = models.TextField(null=True, blank=True)
    title_ar = models.TextField(null=True, blank=True)
    content_ar = models.TextField(null=True, blank=True)
    redirect_url = models.TextField(null=True, blank=True)
    app_content = models.TextField(null=True, blank=True)
    app_content_ar = models.TextField(null=True, blank=True)
    app_screen_type = models.IntegerField(null=True, blank=True)
    app_notification_image = models.CharField(max_length=100, null=True, blank=True)
    app_notification_button_text = models.CharField(max_length=200, null=True, blank=True)
    app_notification_button_text_ar = models.CharField(max_length=200, null=True, blank=True)
    is_read = models.BooleanField(default=0)
    user = models.ForeignKey(Users, related_name="event_notification_user", on_delete=models.CASCADE)
    added_by = models.ForeignKey(Users, related_name="event_notification_added_by", on_delete=models.CASCADE, db_column="added_by")
    status = models.ForeignKey(LookupStatus, related_name="event_notification_status", on_delete=models.CASCADE)

    class Meta:
        db_table = "event_notification"


class PushNotification(models.Model):
 
    """Model for Push Notification
 
    """
    property = models.ForeignKey(PropertyListing, related_name="push_notification_property", on_delete=models.CASCADE, null=True, blank=True)
    title = models.TextField(null=True, blank=True)
    message = models.TextField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    status = models.ForeignKey(LookupStatus, on_delete=models.CASCADE, default=1)
    added_on = models.DateTimeField(auto_now_add=True)
    update_on = models.DateTimeField(auto_now=True)
    notification_to = models.ForeignKey(Users, related_name='push_notification_to', on_delete=models.CASCADE, null=True, blank=True)
    redirect_to = models.IntegerField(null=True, blank=True)
 
    class Meta:
        db_table = 'push_notification'


class PushNotificationBadge(models.Model):
    """Model to save badge.
    """
    user = models.ForeignKey(Users, related_name='badge_user', on_delete=models.CASCADE, null=True, blank=True)
    badge_count = models.IntegerField(null=True, blank=True)
    added_on = models.DateTimeField(auto_now_add=True)
    update_on = models.DateTimeField(auto_now=True)
 
    class Meta:
        db_table = 'push_notification_badge'              

