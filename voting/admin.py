from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import (
    StudentProfile,
    Election,
    Candidate,
    VoterReceipt,
    Vote,
    VoterReceipt,
    AuditLog
)


# Custom User Admin
class CustomUserAdmin(UserAdmin):
    list_display = (
        'username',
        'email',
        'first_name',
        'last_name',
        'is_staff',
        'is_active'
    )

    list_filter = (
        'is_staff',
        'is_superuser',
        'is_active'
    )

    search_fields = (
        'username',
        'email',
        'first_name',
        'last_name'
    )

    ordering = ('username',)


# Unregister default User admin and register custom
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(Election)
class ElectionAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'election_type',
        'campus',
        'start_date',
        'end_date',
        'status',
    )

    list_filter = (
        'election_type',
        'campus',
        'status',
    )

    search_fields = (
        'title',
        'description',
        'campus',
    )

    ordering = (
        '-start_date',
    )

    date_hierarchy = 'start_date'


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'election',
        'candidate_type',
    )

    list_filter = (
        'election',
        'candidate_type',
    )

    search_fields = (
        'name',
        'election__title',
    )


@admin.register(VoterReceipt)
class VoterReceiptAdmin(admin.ModelAdmin):
    """
    Records that a voter has voted without recording
    which candidate they selected.
    """

    list_display = (
        'voter',
        'election',
        'src_category',
        'voted_at',
    )

    list_filter = (
        'election',
        'src_category',
        'voted_at',
    )

    search_fields = (
        'voter__username',
        'election__title',
    )

    readonly_fields = (
        'voter',
        'election',
        'src_category',
        'voted_at',
    )


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    """
    Anonymous ballots only.

    Intentionally does not display or search for a voter,
    because Vote no longer contains voter information.
    """

    list_display = (
        'election',
        'candidate',
        'src_category',
        'voted_at',
    )

    list_filter = (
        'election',
        'src_category',
        'voted_at',
    )

    search_fields = (
        'election__title',
        'candidate__name',
    )

    readonly_fields = (
        'election',
        'candidate',
        'src_category',
        'voted_at',
    )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        'action',
        'user',
        'description',
        'timestamp',
    )

    list_filter = (
        'action',
        'timestamp',
    )

    search_fields = (
        'action',
        'user__username',
        'description',
    )

    readonly_fields = (
        'action',
        'user',
        'description',
        'timestamp',
    )


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = (
        'student_number',
        'full_name',
        'campus',
        'faculty',
        'registered',
        'eligible',
        'account_status',
        'user',
    )

    search_fields = (
        'student_number',
        'full_name',
        'user__username',
    )

    list_filter = (
        'campus',
        'faculty',
        'registered',
        'eligible',
        'account_status',
    )

    readonly_fields = (
        'student_number',
        'full_name',
        'campus',
        'faculty',
    )
