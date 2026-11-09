from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views
from .employees import EmployeeViewSet
from .projects import ProjectViewSet
from .scan import ScanContextView, ScanView

router = DefaultRouter()
router.include_root_view = False
router.register("employees", EmployeeViewSet, basename="employee")
router.register("projects", ProjectViewSet, basename="project")

urlpatterns = [
    path("auth/login/", views.LoginView.as_view(), name="api-login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="api-refresh"),
    path("auth/me/", views.MeView.as_view(), name="api-me"),
    path("scan/<slug:slug>/", ScanView.as_view(), name="api-scan"),
    path("scan/<slug:slug>/context/", ScanContextView.as_view(), name="api-scan-context"),
    path("", include(router.urls)),
]
