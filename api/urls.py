from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views
from .attendance import AttendanceViewSet
from .dashboard import DashboardView
from .employees import EmployeeViewSet
from .geocode import AddressReverseView, AddressSearchView
from .finance import ExpenseViewSet, IncomeViewSet, ProjectFinanceSummaryView
from .payroll import PayrollLineAdjustView, PayrollPeriodViewSet
from .projects import ProjectViewSet
from .reports import AttendanceReportView, FinanceReportView, PayrollReportView
from .scan import ScanContextView, ScanView
from .users import (
    ChangePasswordView,
    SupervisorListView,
    UserDetailView,
    UserListCreateView,
    UserResetPasswordView,
)

router = DefaultRouter()
router.include_root_view = False
router.register("employees", EmployeeViewSet, basename="employee")
router.register("projects", ProjectViewSet, basename="project")
router.register("attendance", AttendanceViewSet, basename="attendance")
router.register("payroll/periods", PayrollPeriodViewSet, basename="payroll-period")
router.register("finance/incomes", IncomeViewSet, basename="finance-income")
router.register("finance/expenses", ExpenseViewSet, basename="finance-expense")

urlpatterns = [
    path("health/", views.HealthView.as_view(), name="api-health"),
    path("auth/login/", views.LoginView.as_view(), name="api-login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="api-refresh"),
    path("auth/me/", views.MeView.as_view(), name="api-me"),
    path("scan/<slug:slug>/", ScanView.as_view(), name="api-scan"),
    path("scan/<slug:slug>/context/", ScanContextView.as_view(), name="api-scan-context"),
    path("payroll/lines/<int:pk>/adjust/", PayrollLineAdjustView.as_view(), name="payroll-line-adjust"),
    path("projects/<int:pk>/finance/", ProjectFinanceSummaryView.as_view(), name="api-project-finance"),
    path("reports/payroll/<int:pk>/<str:fmt>/", PayrollReportView.as_view(), name="report-payroll"),
    path("reports/attendance/<str:fmt>/", AttendanceReportView.as_view(), name="report-attendance"),
    path("reports/finance/<int:pk>/<str:fmt>/", FinanceReportView.as_view(), name="report-finance"),
    path("geocode/search/", AddressSearchView.as_view(), name="api-geocode-search"),
    path("geocode/reverse/", AddressReverseView.as_view(), name="api-geocode-reverse"),
    path("dashboard/", DashboardView.as_view(), name="api-dashboard"),
    path("auth/change-password/", ChangePasswordView.as_view(), name="api-change-password"),
    path("users/supervisors/", SupervisorListView.as_view(), name="api-supervisors"),
    path("users/", UserListCreateView.as_view(), name="api-users"),
    path("users/<int:pk>/", UserDetailView.as_view(), name="api-user-detail"),
    path("users/<int:pk>/reset-password/", UserResetPasswordView.as_view(), name="api-user-reset"),
    path("", include(router.urls)),
]
