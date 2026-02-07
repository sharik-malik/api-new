# -*- coding: utf-8 -*-
"""Project Serializer

"""
from rest_framework import serializers
from api.project.models import *
from api.property.models import *
from django.db.models import F

class ProjectListingSerializer(serializers.ModelSerializer):
    """
    ProjectListingSerializer
    """
    name = serializers.SerializerMethodField()
    project_type = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    approval = serializers.SerializerMethodField()
    created_date = serializers.SerializerMethodField()
    project_status = serializers.SerializerMethodField()
    project_location = serializers.SerializerMethodField()
    project_image = serializers.SerializerMethodField()
    developer_name = serializers.SerializerMethodField()
    domain_url = serializers.CharField(source="domain.domain_url", read_only=True, default="")
    domain = serializers.SerializerMethodField()
    no_of_property = serializers.SerializerMethodField()

    class Meta:
        model = DeveloperProject
        fields = ("id", "name", "project_name", "developer_name", "neighborhood", "community", "registration_date", "completion_date", "created_date",
                  "status", "project_status", "project_status_id", "project_location", "project_image", "project_type", "approval", "is_approved",
                  "status_id", "domain_url", "domain", "no_of_property")


    @staticmethod
    def get_name(obj):
        try:
            name = obj.address_one
            return name
        except Exception as exp:
            print(exp)
            return ""

    @staticmethod
    def get_created_date(obj):
        try:
            return obj.added_on
        except Exception as exp:
            return ""

    @staticmethod
    def get_project_status(obj):
        try:
            return obj.project_status.status_name
        except Exception as exp:
            return ""

    @staticmethod
    def get_status(obj):
        try:
            return obj.status.status_name
        except Exception as exp:
            return ""

    @staticmethod
    def get_project_type(obj):
        try:
            project_types = obj.developer_project_type.select_related('project_type').all()
            project_type_names = [project_type.project_type.name for project_type in project_types]
            return project_type_names
        except Exception as exp:
            print("Error while fetching project types:", exp)
            return []

    @staticmethod
    def get_project_location(obj):
        try:
            name = obj.city.state_name if obj.city is not None else ""
            name += ", " + obj.country.country_name if obj.country is not None else ""
            name += ", " + obj.postal_code if obj.postal_code is not None else ""
            return name
        except Exception as exp:
            return ""

    @staticmethod
    def get_project_image(obj):
        try:
            uploads = obj.developer_project_uploads_developer_project.filter(upload_type=1).select_related('upload')
            images = [{
                "file_name": upload.upload.doc_file_name,
                "bucket_name": upload.upload.bucket_name,
                "file_size": upload.upload.file_size
            } for upload in uploads]
            return images
        except Exception as exp:
            print(exp)
            return []

    @staticmethod
    def get_domain(obj):
        try:
            return obj.domain_id
        except Exception as exp:
            return ""

    @staticmethod
    def get_approval(obj):
        try:
            return "Approved" if obj.is_approved is not None and obj.is_approved == 1 else "Not Approved"
        except Exception as exp:
            return ""

    @staticmethod
    def get_developer_name(obj):
        try:
            return obj.agent.first_name
        except Exception as exp:
            return ""
        
    @staticmethod
    def get_no_of_property(obj):
        try:
            return PropertyListing.objects.filter(project=obj.id).exclude(status=5).count()
        except Exception as exp:
            return 0    

class SubdomainProjectListingSerializer(serializers.ModelSerializer):
    """
    SubdomainProjectListingSerializer
    """
    project_status = serializers.SerializerMethodField()
    project_image = serializers.SerializerMethodField()
    project_type = serializers.SerializerMethodField()
    project_uri = serializers.SerializerMethodField()

    class Meta:
        model = DeveloperProject
        fields = ("id", "project_name", "project_uri", "starting_price", "total_units", "project_status",
                  "project_image", "project_type", "project_name_ar", "project_desc_ar")

    @staticmethod
    def get_project_status(obj):
        try:
            return obj.project_status.status_name
        except Exception as exp:
            return ""

    @staticmethod
    def get_project_type(obj):
        try:
            project_types = obj.developer_project_type.select_related('project_type').all()
            project_type_names = [project_type.project_type.name for project_type in project_types]
            return project_type_names
        except Exception as exp:
            print("Error while fetching project types:", exp)
            return []

    @staticmethod
    def get_project_image(obj):
        try:
            last_upload = obj.developer_project_uploads_developer_project.filter(upload_type=1).select_related('upload').last()
            if last_upload and last_upload.upload:
                return {
                    "file_name": last_upload.upload.doc_file_name,
                    "bucket_name": last_upload.upload.bucket_name,
                    "file_size": last_upload.upload.file_size,
                }
            return None
        except Exception as exp:
            return None

    @staticmethod
    def get_project_uri(obj):
        try:
            name = obj.project_name if obj.project_name is not None else ""
            name += "-"+obj.city.state_name if obj.city is not None else ""
            name += "-" + obj.country.country_name if obj.country is not None else ""
            return name
        except Exception as exp:
            return ""

class FloorPlanSerializer(serializers.ModelSerializer):
    upload_details = serializers.SerializerMethodField()

    class Meta:
        model = DeveloperProjectFloorPlans
        fields = [
            'id', 'upload', 'upload_details', 'floor_heading',
            'floor_bed_rooms', 'floor_available_units', 'floor_area',
            'floor_bedroom_desc', 'status'
        ]

    def get_upload_details(self, obj):
        """Fetch details of the upload from the UserUploads model."""
        if obj.upload:
            return {
                "id": obj.upload.id,
                "doc_file_name": obj.upload.doc_file_name,
                "file_size": obj.upload.file_size,
                "bucket_name": obj.upload.bucket_name,
                "added_on": obj.upload.added_on,
                "updated_on": obj.upload.updated_on,
            }
        return None

class DeveloperProjectTypeSerializer(serializers.ModelSerializer):
    project_type_name = serializers.CharField(source='project_type.name', read_only=True)
    floor_plans = FloorPlanSerializer(source='developer_project_floor_plans', many=True)

    class Meta:
        model = DeveloperProjectType
        fields = ['id', 'project_type_name', 'project_type_id', 'floor_plans']

class AddDeveloperProjectSerializer(serializers.ModelSerializer):
    """
    AddDeveloperProjectSerializer
    """

    class Meta:
        model = DeveloperProject
        fields = "__all__"

class DeveloperProjectDetailStepOneSerializer(serializers.ModelSerializer):
    """
    PropertyDetailStepOneSerializer
    """
    project_type = serializers.SerializerMethodField()
    property_subtype = serializers.SerializerMethodField()
    project_selected_facilities = serializers.SerializerMethodField()


    class Meta:
        model = DeveloperProject
        fields = ("id", "project_name", "city", "district", "municipality", "neighborhood", "community", "address_one", "postal_code", "project_selected_facilities",
                   "project_type", "property_subtype", "registration_number", "registration_date", "completion_date", "starting_price", "total_units", "units_for_sale",
                  "units_type", "property_size", "is_featured", "is_approved", "project_desc", "project_lat",
                  "project_lon", "create_step", "country", "domain", "status", "project_status_id", "project_name_ar",
                  "project_desc_ar")

    @staticmethod
    def get_project_type(obj):
        try:
            return obj.developer_project_type.values(feature_id=F("project_type_id"))
        except Exception as exp:
            print(exp)
            return []

    @staticmethod
    def get_project_selected_facilities(obj):
        try:
            return obj.selected_facilities.values(feature_id=F("facility_id"))
        except Exception as exp:
            return []

    @staticmethod
    def get_property_subtype(obj):
        try:
            return [] #obj.property_subtype.values(feature_id=F("subtype_id"))
        except Exception as exp:
            return []

class DeveloperProjectDetailStepTwoSerializer(serializers.ModelSerializer):
    """
    PropertyDetailStepTwoSerializer
    """
    city = serializers.CharField(source="city.state_name", read_only=True, default="")
    country_name = serializers.CharField(source="country.country_name", read_only=True, default="")

    class Meta:
        model = DeveloperProject
        fields = ("id", "is_map_view", "is_street_view", "is_arial_view", "address_one", "city", "postal_code", "map_url", "latitude",
                  "longitude", "country_name", "project_name")

class DeveloperProjectDetailStepThreeSerializer(serializers.ModelSerializer):
    """
    PropertyDetailStepThreeSerializer
    """
    photo = serializers.SerializerMethodField()
    video = serializers.SerializerMethodField()

    class Meta:
        model = DeveloperProject
        fields = ("id", "photo", "video")

    @staticmethod
    def get_photo(obj):
        try:
            return obj.developer_project_uploads_developer_project.filter(upload_type=1).values("upload_id", "photo_description", "added_on", file_size=F("upload__file_size"), doc_file_name=F("upload__doc_file_name"), bucket_name=F("upload__bucket_name"))
        except Exception as exp:
            return []

    @staticmethod
    def get_video(obj):
        try:
            return obj.developer_project_uploads_developer_project.filter(upload_type=2).values("upload_id", "added_on", file_size=F("upload__file_size"), doc_file_name=F("upload__doc_file_name"), bucket_name=F("upload__bucket_name"))
        except Exception as exp:
            return []

class DeveloperProjectDetailStepFourSerializer(serializers.ModelSerializer):
    project_types = DeveloperProjectTypeSerializer(source='developer_project_type', many=True)
    documents = serializers.SerializerMethodField()

    class Meta:
        model = DeveloperProject
        fields = [
            'id', 'project_name', 'project_types', 'documents'
        ]

    @staticmethod
    def get_documents(obj):
        try:
            return obj.developer_project_uploads_developer_project.filter(upload_type=3).order_by("id").values("upload_id", "added_on", file_size=F("upload__file_size"), doc_file_name=F("upload__doc_file_name"), bucket_name=F("upload__bucket_name"))
        except Exception as exp:
            return []

class DeveloperProjectFacilitySerializer(serializers.ModelSerializer):
    doc_file_name = serializers.SerializerMethodField()
    bucket_name = serializers.SerializerMethodField()

    class Meta:
        model = DeveloperProjectFacility
        fields = ("id", "name", "bucket_name", "doc_file_name")

    def get_doc_file_name(self, obj):
        # Accessing the related 'upload' field and returning the icon URL
        return obj.upload.doc_file_name if obj.upload else None

    def get_bucket_name(self, obj):
        # Accessing the related 'upload' field and returning the icon URL
        return obj.upload.bucket_name if obj.upload else None

class SubdomainProjectDetailSerializer(serializers.ModelSerializer):

    project_status = serializers.SerializerMethodField()
    project_location = serializers.SerializerMethodField()
    project_photo = serializers.SerializerMethodField()
    project_video = serializers.SerializerMethodField()
    project_type = serializers.SerializerMethodField()
    project_brochure = serializers.SerializerMethodField()
    project_floor_plans = DeveloperProjectTypeSerializer(source='developer_project_type', many=True)
    project_facility = serializers.SerializerMethodField()
    project_near_by_places = serializers.SerializerMethodField()

    class Meta:
        model = DeveloperProject
        fields = [
            'id', 'project_name', 'project_status', 'project_location', 'total_units', 'units_for_sale',
            'completion_date', 'units_type', 'property_size', 'project_desc', 'is_map_view', 'is_street_view',
            'is_arial_view', 'map_url', 'project_lat', 'project_lon', 'latitude', 'longitude', 'project_type',
            'project_photo', 'project_video', 'project_brochure','project_floor_plans', 'project_facility', 'project_near_by_places',
            'project_name_ar', 'project_desc_ar'
        ]

    @staticmethod
    def get_project_near_by_places(obj):
        try:
            places = obj.nearby_places.all()
            places_info = places.values('place_type', 'places_json')
            return list(places_info)
        except Exception as exp:
            return []

    @staticmethod
    def get_project_status(obj):
        try:
            return obj.project_status.status_name
        except Exception as exp:
            return ""

    @staticmethod
    def get_project_location(obj):
        try:
            name = obj.city.state_name if obj.city is not None else ""
            name += ", " + obj.neighborhood
            name += ", " + obj.community
            return name
        except Exception as exp:
            return ""

    @staticmethod
    def get_project_photo(obj):
        try:
            return obj.developer_project_uploads_developer_project.filter(upload_type=1).values(doc_file_name=F("upload__doc_file_name"), bucket_name=F("upload__bucket_name"))
        except Exception as exp:
            return []

    @staticmethod
    def get_project_video(obj):
        try:
            return obj.developer_project_uploads_developer_project.filter(upload_type=2).values(doc_file_name=F("upload__doc_file_name"), bucket_name=F("upload__bucket_name"))
        except Exception as exp:
            return []

    @staticmethod
    def get_project_type(obj):
        try:
            project_types = obj.developer_project_type.select_related('project_type').all()
            project_type_names = [project_type.project_type.name for project_type in project_types]
            return project_type_names
        except Exception as exp:
            print("Error while fetching project types:", exp)
            return []

    @staticmethod
    def get_project_brochure(obj):
        try:
            return obj.developer_project_uploads_developer_project.filter(upload_type=3).order_by("id").values(doc_file_name=F("upload__doc_file_name"), bucket_name=F("upload__bucket_name"))
        except Exception as exp:
            return []

    @staticmethod
    def get_project_facility(obj):
        try:
            facilities = obj.selected_facilities.annotate(
                name=F("facility__name"),
                bucket_name=F("facility__upload__bucket_name"),
                doc_file_name=F("facility__upload__doc_file_name"),
            ).values("name", "bucket_name","doc_file_name")

            return list(facilities)
        except Exception as exp:
            return []