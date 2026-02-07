# -*- coding: utf-8 -*-
"""Notification Serializer

"""
from rest_framework import serializers
from api.notifications.models import *
from django.db.models import F


class TemplateListingSerializer(serializers.ModelSerializer):
    """
    TemplateListingSerializer
    """
    event_name = serializers.CharField(source="event.event_name", read_only=True, default="")
    event_slug = serializers.CharField(source="event.slug", read_only=True, default="")
    status_name = serializers.CharField(source="status.status_name", read_only=True, default="")
    domain = serializers.CharField(source="site.domain_name", read_only=True, default="")

    class Meta:
        model = NotificationTemplate
        fields = ("id", "status_name", "domain", "event_name", "event_slug", "status", "email_subject", "added_on")


class AddTemplateSerializer(serializers.ModelSerializer):
    """
    AddTemplateSerializer
    """

    class Meta:
        model = NotificationTemplate
        fields = "__all__"


class TemplateDetailSerializer(serializers.ModelSerializer):
    """
    TemplateDetailSerializer
    """

    class Meta:
        model = NotificationTemplate
        fields = ("id", "site_id", "event_id", "email_subject", "email_content", "notification_text",
                  "push_notification_text", "status", "notification_subject", "notification_subject_ar",
                  "notification_text_ar"
                  )


class SubdomainTemplateListingSerializer(serializers.ModelSerializer):
    """
    SubdomainTemplateListingSerializer
    """
    event_name = serializers.CharField(source="event.event_name", read_only=True, default="")
    event_slug = serializers.CharField(source="event.slug", read_only=True, default="")
    status_name = serializers.CharField(source="status.status_name", read_only=True, default="")
    domain = serializers.CharField(source="site.domain_name", read_only=True, default="")

    class Meta:
        model = NotificationTemplate
        fields = ("id", "status_name", "domain", "event_name", "event_slug", "status", "email_subject", "added_on")


class SubdomainTemplateDetailSerializer(serializers.ModelSerializer):
    """
    SubdomainTemplateDetailSerializer
    """

    class Meta:
        model = NotificationTemplate
        fields = ("id", "site_id", "event_id", "email_subject", "email_content", "notification_text",
                  "push_notification_text", "status")


class NotificationDetailSerializer(serializers.ModelSerializer):
    """
    NotificationDetailSerializer
    """
    prop_id = serializers.SerializerMethodField()

    class Meta:
        model = EventNotification
        fields = ("id", "prop_id", "title", "content", "added_on", "redirect_url", "is_read", "app_content", "app_screen_type", "app_notification_image", "app_notification_button_text", 
                  "title_ar", "content_ar", "app_content_ar", "app_notification_button_text_ar")

    @staticmethod
    def get_prop_id(obj):
        try:
            return obj.property_id if obj.property_id else None
        except Exception as exp:
            return None


class NotificationListingSerializer(serializers.ModelSerializer):
    """
    NotificationListingSerializer
    """

    prop_id = serializers.SerializerMethodField()
    class Meta:
        model = EventNotification
        fields = ("id", "prop_id", "title", "content", "added_on", "redirect_url", "is_read", "app_content", "app_screen_type", "app_notification_image", "app_notification_button_text",
                  "title_ar", "content_ar", "app_content_ar", "app_notification_button_text_ar")

    @staticmethod
    def get_prop_id(obj):
        try:
            return obj.property_id if obj.property_id else None
        except Exception as exp:
            return None    


class TemplateListSerializer(serializers.ModelSerializer):
    """
    TemplateListSerializer
    """
    event_name = serializers.CharField(source="event.event_name", read_only=True, default="")
    event_slug = serializers.CharField(source="event.slug", read_only=True, default="")

    class Meta:
        model = NotificationTemplate
        fields = ("id", "event_name", "event_slug")     





