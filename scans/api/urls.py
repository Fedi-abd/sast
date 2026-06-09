from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("projects", views.ProjectViewSet, basename="project")
router.register("scans", views.ScanViewSet, basename="scan")

urlpatterns = router.urls
