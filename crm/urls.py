from django.contrib import admin
from django.urls import include, path, re_path
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from django.views.generic import TemplateView, RedirectView

from core import views
from approval import views as approval_views

router = DefaultRouter()
router.register(r'users', views.UserViewSet, basename='user')
router.register(r'regions', views.RegionViewSet, basename='region')
router.register(r'roles', views.RoleViewSet, basename='role')
router.register(r'leads', views.LeadViewSet, basename='lead')
router.register(r'opportunities', views.OpportunityViewSet, basename='opportunity')
router.register(r'opportunity-attachments', views.OpportunityAttachmentViewSet, basename='opportunity-attachment')
router.register(r'accounts', views.AccountViewSet, basename='account')
router.register(r'contacts', views.ContactViewSet, basename='contact')
router.register(r'lookups', views.LookupCategoryViewSet, basename='lookup')
router.register(r'lookup-options', views.LookupOptionViewSet, basename='lookup-option')
router.register(r'quotes', views.QuoteViewSet, basename='quote')
router.register(r'contracts', views.ContractViewSet, basename='contract')
router.register(r'contract-attachments', views.ContractAttachmentViewSet, basename='contract-attachment')
router.register(r'invoices', views.InvoiceViewSet, basename='invoice')
router.register(r'payments', views.PaymentViewSet, basename='payment')
router.register(r'common-doc-directories', views.CommonDocDirectoryViewSet, basename='common-doc-directory')
router.register(r'common-documents', views.CommonDocumentViewSet, basename='common-document')
router.register(r'activities', views.ActivityViewSet, basename='activity')
router.register(r'tasks', views.TaskViewSet, basename='task')
router.register(r'approval-flows', approval_views.ApprovalFlowViewSet, basename='approval-flow')
router.register(r'approval-steps', approval_views.ApprovalStepViewSet, basename='approval-step')
router.register(r'approval-instances', approval_views.ApprovalInstanceViewSet, basename='approval-instance')
router.register(r'approval-tasks', approval_views.ApprovalTaskViewSet, basename='approval-task')
router.register(r'reports', views.ReportViewSet, basename='report')

urlpatterns = [
    path('', RedirectView.as_view(url='/admin/', permanent=False)),
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/auth/', include('rest_framework.urls')),
    path('api/auth/me/', views.current_user, name='current_user'),
    path('api/auth/password/', views.change_password, name='change_password'),
    path('api/auth/jwt/', views.TokenView.as_view(), name='token_obtain_pair'),
    path('api/auth/jwt/refresh/', views.TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/dingtalk/', views.DingTalkSSOView.as_view(), name='dingtalk_sso'),
    path('api/dingtalk/sync/', views.DingTalkSyncView.as_view(), name='dingtalk_sync'),
    path('app/', TemplateView.as_view(template_name='spa/index.html')),
    re_path(r'^app/.*$', TemplateView.as_view(template_name='spa/index.html')),
    path('prototype/', TemplateView.as_view(template_name='prototype/dashboard.html', extra_context={'nav_dashboard': 'active'})),
    path('prototype/opportunities/', TemplateView.as_view(template_name='prototype/opportunities.html', extra_context={'nav_opps': 'active'})),
    path('prototype/approvals/', TemplateView.as_view(template_name='prototype/approvals.html', extra_context={'nav_approvals': 'active'})),
    path('prototype/regions/', TemplateView.as_view(template_name='prototype/regions.html', extra_context={'nav_regions': 'active'})),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
