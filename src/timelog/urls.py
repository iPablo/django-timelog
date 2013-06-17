from django.conf.urls import patterns, include, url
from django.contrib.auth.decorators import login_required

from .views import TimelogView

urlpatterns = patterns('',
    url(r'^$', login_required(TimelogView.as_view()))
)