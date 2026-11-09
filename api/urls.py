from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views
from .attendance import AttendanceViewSet
from .employees import EmployeeViewSet
from .finance import ExpenseViewSet, IncomeViewSet, ProjectFinanceSummaryView
from .payroll import PayrollLineAdjustView, PayrollPeriodViewSet
from .projects import ProjectViewSet
from .scan import ScanContextView, ScanView

router = DefaultRouter()
router.include_root_view = False
router.register("employees", EmployeeViewSet, basename="employee")
router.register("projects", ProjectViewSet, basename="project")
router.register("attendance", AttendanceViewSet, basename="attendance")
router.register("payroll/periods", PayrollPeriodViewSet, basename="payroll-period")
router.register("finance/incomes", IncomeViewSet, basename="finance-income")
router.register("finance/expenses", ExpenseViewSet, basename="finance-expense")

urlpatterns = [
    path("auth/login/", views.LoginView.as_view(), name="api-login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="api-refresh"),
    path("auth/me/", views.MeView.as_view(), name="api-me"),
    path("scan/<slug:slug>/", ScanView.as_view(), name="api-scan"),
    path("scan/<slug:slug>/context/", ScanContextView.as_view(), name="api-scan-context"),
    path("payroll/lines/<int:pk>/adjust/", PayrollLineAdjustView.as_view(), name="payroll-line-adjust"),
    path("projects/<int:pk>/finance/", ProjectFinanceSummaryView.as_view(), name="api-project-finance"),
    path("", include(router.urls)),
]
