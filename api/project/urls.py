# -*- coding: utf-8 -*-
from django.urls import path, include
from . import views
from api.project.views import *

urlpatterns = [
    path("project-type/", ProjectTypeApiView.as_view()),
    path("get-facility/", FacilityListApiView.as_view()),
    path("add-facility/", AddFacilityListApiView.as_view()),
    path("project-listing/", ProjectListingApiView.as_view()),
    path("add-developer-project/", AddDeveloperProjectApiView.as_view()),
    path("developer-project-detail/", DeveloperProjectDetailApiView.as_view()),
    path("add-developer-project-video/", AddDeveloperProjectVideoApiView.as_view()),
    path("developer-project-document-delete/", DeveloperProjectDocumentDeleteApiView.as_view()),
    path("developer-floor-plan-image-delete/", DeveloperProjectFloorPlanDeleteApiView.as_view()),
    path("project-status-change/", DeveloperProjectStatusChangeApiView.as_view()),
    path("project-approval-change/", DeveloperProjectApprovalChangeApiView.as_view()),

    path("subdomain-project-listing/", SubdomainProjectListingApiView.as_view()),
    path("subdomain-project-detail/", SubdomainProjectDetailApiView.as_view()),
    path("project-list/", ProjectListApiView.as_view()),
    path("delete-project/", DeleteProjectApiView.as_view()),
]
