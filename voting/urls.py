from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    
    # Authentication URLs
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    
    # Student URLs
    path('dashboard/', views.dashboard, name='dashboard'),
    path('vote/<int:election_id>/', views.vote, name='vote'),
    path('results/', views.results, name='results'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    
    # Admin URLs
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-dashboard/elections/', views.manage_elections, name='manage_elections'),
    path('admin-dashboard/voters/', views.manage_voters, name='manage_voters'),
    path('admin-dashboard/voters/clear/',views.clear_voters,name='clear_voters'),
    path('admin-dashboard/elections/create/', views.create_election, name='create_election'),
    path('admin-dashboard/elections/<int:election_id>/edit/', views.edit_election, name='edit_election'),
    path('admin-dashboard/elections/<int:election_id>/delete/', views.delete_election, name='delete_election'),
    path('admin-dashboard/import-students/', views.import_students, name='import_students'),
    path('admin-dashboard/audit-logs/', views.view_audit_logs, name='view_audit_logs'),
    path('admin-dashboard/export-results/',views.export_results_excel,name='export_results_excel'),
    path(
    'admin-dashboard/export-results-pdf/',views.export_results_pdf,name='export_results_pdf'),
]