# -*- coding: utf-8 -*-
from django.urls import path, include
from . import views
from api.cron.views import *

urlpatterns = [
    path("payment-cron/", PaymentCronApiView.as_view()),
]
