# -*- coding: utf-8 -*-
from django.db import models
from api.users.models import *

class Default(models.Model):
    """This abstract class for common field
    """
    added_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'developer_project'
        abstract = True

class DeveloperProject(Default):
    project_name = models.CharField(max_length=255, null=True, blank=True)
    project_name_ar = models.CharField(max_length=255, null=True, blank=True)
    country = models.ForeignKey(LookupCountry, related_name="developer_project_country", on_delete=models.CASCADE, null=True, blank=True)
    city = models.ForeignKey(LookupState, related_name="developer_project_city", on_delete=models.CASCADE, null=True, blank=True)
    district = models.ForeignKey(LookupDistrict, related_name="pdeveloper_project_district", on_delete=models.CASCADE, null=True, blank=True)
    municipality = models.ForeignKey(LookupMunicipality, related_name="developer_project_municipality", on_delete=models.CASCADE, null=True, blank=True)
    agent = models.ForeignKey(Users, related_name="developer_project_agent", on_delete=models.CASCADE, null=True, blank=True)
    neighborhood = models.CharField(max_length=255, null=True, blank=True)
    community = models.CharField(max_length=255, null=True, blank=True)
    address_one = models.TextField(null=True, blank=True)
    postal_code = models.CharField(max_length=10, null=True, blank=True)
    registration_number = models.CharField(max_length=255, null=True, blank=True)
    # registration_date = models.DateTimeField(null=True, blank=True)
    # completion_date = models.DateTimeField(null=True, blank=True)
    registration_date = models.DateField(null=True, blank=True)
    completion_date = models.DateField(null=True, blank=True)
    starting_price = models.DecimalField(default=0.00, max_digits=15, decimal_places=2)
    total_units = models.IntegerField(null=True, blank=True)
    units_for_sale = models.IntegerField(null=True, blank=True)
    units_type = models.CharField(max_length=255, null=True, blank=True)
    property_size = models.CharField(max_length=255, null=True, blank=True)
    is_featured = models.BooleanField(default=0, null=True, blank=True)
    is_approved = models.BooleanField(default=0, null=True, blank=True)
    project_desc = models.TextField(null=True, blank=True)
    project_desc_ar = models.TextField(null=True, blank=True)
    status = models.ForeignKey(LookupStatus, related_name="developer_project_listing_status", on_delete=models.CASCADE, null=True, blank=True)
    project_status = models.ForeignKey(LookupDeveloperProjectStatus, related_name="developer_project_status", on_delete=models.CASCADE, null=True, blank=True)
    domain = models.ForeignKey(NetworkDomain, related_name="developer_project_domain", on_delete=models.CASCADE)
    project_lat = models.CharField(max_length=100, null=True, blank=True)
    project_lon = models.CharField(max_length=100, null=True, blank=True)
    is_map_view = models.BooleanField(default=1)
    is_street_view = models.BooleanField(default=1)
    is_arial_view = models.BooleanField(default=1)
    map_url = models.TextField(null=True, blank=True)
    latitude = models.CharField(max_length=251, null=True, blank=True)
    longitude = models.CharField(max_length=251, null=True, blank=True)
    create_step = models.IntegerField(choices=((1, "First"), (2, "Second"), (3, "Third"), (4, "Fourth")), default=1)
    added_by = models.ForeignKey(Users, related_name="developer_project_added_by", on_delete=models.CASCADE, db_column="added_by", null=True, blank=True)
    updated_by = models.ForeignKey(Users, related_name="developer_project_updated_by", on_delete=models.CASCADE, null=True, blank=True, db_column="updated_by")
    ordering = models.IntegerField(null=True, blank=True)
    class Meta:
        db_table = "developer_project"

class DeveloperProjectType(Default):
    project = models.ForeignKey(DeveloperProject, related_name="developer_project_type", on_delete=models.CASCADE)
    project_type = models.ForeignKey(LookupDeveloperProjectType, related_name="project_type", on_delete=models.CASCADE)
    class Meta:
        db_table = "developer_project_type"

class DeveloperProjectUploads(Default):
    upload = models.ForeignKey(UserUploads, related_name="developer_project_uploads", on_delete=models.CASCADE)
    project = models.ForeignKey(DeveloperProject, related_name="developer_project_uploads_developer_project", on_delete=models.CASCADE)
    upload_type = models.IntegerField(choices=((1, "Images"), (2, "Video"), (3, "Documents")))
    photo_description = models.TextField(null=True, blank=True)
    status = models.ForeignKey(LookupStatus, related_name="developer_project_uploads_status", on_delete=models.CASCADE)

    class Meta:
        db_table = "developer_project_uploads"

class DeveloperProjectFloorPlans(Default):
    upload = models.ForeignKey(UserUploads, related_name="developer_project_floor_plan_uploads", on_delete=models.CASCADE, null=True)
    project = models.ForeignKey(DeveloperProject, related_name="developer_project", on_delete=models.CASCADE)
    project_type = models.ForeignKey(DeveloperProjectType, related_name="developer_project_floor_plans", on_delete=models.CASCADE)
    floor_heading = models.TextField(null=True, blank=True)
    floor_bed_rooms = models.TextField(null=True, blank=True)
    floor_available_units = models.TextField(null=True, blank=True)
    floor_area = models.TextField(null=True, blank=True)
    floor_bedroom_desc = models.TextField(null=True, blank=True)
    status = models.ForeignKey(LookupStatus, related_name="developer_project_floor_plan_status", on_delete=models.CASCADE)

    class Meta:
        db_table = "developer_project_floor_plans"

class DeveloperProjectFacility(models.Model):
    name = models.CharField(max_length=255)
    upload = models.ForeignKey(UserUploads, related_name="facility_icon", on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "developer_project_facility"

class DeveloperProjectSelectedFacility(models.Model):
    project = models.ForeignKey(DeveloperProject, related_name="selected_facilities", on_delete=models.CASCADE)
    facility = models.ForeignKey(DeveloperProjectFacility, related_name="selected_in_projects", on_delete=models.CASCADE)

    class Meta:
        db_table = "developer_project_selected_facility"

class DeveloperProjectNearByPlaces(models.Model):
    PLACE_CHOICES = [
        ('SHOPPING', 'Shopping'),
        ('SCHOOL', 'School'),
        ('HOSPITAL', 'Hospital'),
        ('LIFESTYLE', 'Lifestyle'),
    ]
    project = models.ForeignKey(DeveloperProject, related_name="nearby_places", on_delete=models.CASCADE)
    places_json = models.TextField(null=True, blank=True)
    place_type = models.CharField(max_length=100, choices=PLACE_CHOICES, default="SHOPPING")
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = "developer_project_near_by_places"
