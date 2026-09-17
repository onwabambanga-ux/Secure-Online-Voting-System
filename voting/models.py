from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class StudentProfile(models.Model):

    ACCOUNT_STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('SUSPENDED', 'Suspended'),
        ('INACTIVE', 'Inactive'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        related_name='student_profile',
        null=True,
        blank=True
    )

    student_number = models.CharField(
        max_length=50,
        unique=True
    )

    full_name = models.CharField(
        max_length=200
    )

    campus = models.CharField(
        max_length=100
    )

    faculty = models.CharField(
        max_length=150
    )

    registered = models.BooleanField(
        default=False
    )

    eligible = models.BooleanField(
        default=False
    )

    account_status = models.CharField(
        max_length=20,
        choices=ACCOUNT_STATUS_CHOICES,
        default='ACTIVE'
    )

    def __str__(self):
        return f"{self.student_number} - {self.full_name}"


class Election(models.Model):

    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SCHEDULED', 'Scheduled'),
        ('OPEN', 'Open'),
        ('CLOSED', 'Closed'),
        ('RESULTS', 'Results'),
    ]

    ELECTION_TYPE_CHOICES = [
        ('INSTITUTIONAL', 'Institutional SRC'),
        ('CAMPUS', 'Campus SRC'),
        ('RUNOFF', 'Runoff'),
    ]

    title = models.CharField(
        max_length=200
    )

    description = models.TextField()

    election_type = models.CharField(
        max_length=20,
        choices=ELECTION_TYPE_CHOICES,
        default='INSTITUTIONAL'
    )

    campus = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    start_date = models.DateTimeField()

    end_date = models.DateTimeField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT'
    )

    def __str__(self):
        return self.title

    def update_status(self):

        now = timezone.now()

        if self.status in ['DRAFT', 'RESULTS']:
            return

        if now < self.start_date:
            new_status = 'SCHEDULED'

        elif self.start_date <= now <= self.end_date:
            new_status = 'OPEN'

        else:
            new_status = 'CLOSED'

        if self.status != new_status:
            self.status = new_status
            self.save(update_fields=['status'])


class Candidate(models.Model):

    SRC_CATEGORY_CHOICES = [
        ('INSTITUTIONAL', 'Institutional SRC'),
        ('CAMPUS', 'Campus SRC'),
    ]

    CANDIDATE_TYPE_CHOICES = [
        ('ORGANIZATION', 'Organization'),
        ('INDEPENDENT', 'Independent Candidate'),
    ]

    election = models.ForeignKey(
        Election,
        on_delete=models.CASCADE,
        related_name='candidates'
    )

    src_category = models.CharField(
        max_length=20,
        choices=SRC_CATEGORY_CHOICES,
        default='INSTITUTIONAL'
    )

    candidate_type = models.CharField(
        max_length=20,
        choices=CANDIDATE_TYPE_CHOICES
    )

    name = models.CharField(
        max_length=200
    )

    description = models.TextField(
        blank=True
    )

    image = models.ImageField(
        upload_to='candidate_images/',
        blank=True,
        null=True
    )

    def __str__(self):
        return self.name


class VoterReceipt(models.Model):
    """
    Records that a student has voted in an election/category.

    This model identifies the voter but does NOT store
    which candidate they selected.
    """

    SRC_CATEGORY_CHOICES = [
        ('INSTITUTIONAL', 'Institutional SRC'),
        ('CAMPUS', 'Campus SRC'),
    ]

    voter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='voter_receipts'
    )

    election = models.ForeignKey(
        Election,
        on_delete=models.CASCADE,
        related_name='voter_receipts'
    )

    src_category = models.CharField(
        max_length=20,
        choices=SRC_CATEGORY_CHOICES
    )

    voted_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'voter',
                    'election',
                    'src_category'
                ],
                name='one_receipt_per_category_per_election'
            )
        ]

    def __str__(self):
        return (
            f'{self.voter.username} voted in '
            f'{self.election.title} - {self.src_category}'
        )


class Vote(models.Model):

    SRC_CATEGORY_CHOICES = [
        ('INSTITUTIONAL', 'Institutional SRC'),
        ('CAMPUS', 'Campus SRC'),
    ]

    election = models.ForeignKey(
        Election,
        on_delete=models.CASCADE,
        related_name='votes'
    )

    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.CASCADE,
        related_name='votes'
    )

    src_category = models.CharField(
        max_length=20,
        choices=SRC_CATEGORY_CHOICES,
        null=True,
        blank=True
    )

    voted_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return (
            f'{self.candidate.name} - '
            f'{self.election.title} - '
            f'{self.src_category}'
        )


class AuditLog(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )

    action = models.CharField(
        max_length=100
    )

    description = models.TextField()

    timestamp = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.action} - {self.timestamp}"
