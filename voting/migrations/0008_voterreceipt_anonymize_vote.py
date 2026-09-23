from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def create_voter_receipts(apps, schema_editor):
    Vote = apps.get_model('voting', 'Vote')
    VoterReceipt = apps.get_model('voting', 'VoterReceipt')

    for vote in Vote.objects.exclude(src_category__isnull=True):
        VoterReceipt.objects.get_or_create(
            voter_id=vote.voter_id,
            election_id=vote.election_id,
            src_category=vote.src_category,
            defaults={
                'voted_at': vote.voted_at,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        (
            'voting',
            '0007_remove_vote_one_vote_per_voter_per_election_and_more'
        ),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='VoterReceipt',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID'
                    ),
                ),
                (
                    'src_category',
                    models.CharField(
                        choices=[
                            ('INSTITUTIONAL', 'Institutional SRC'),
                            ('CAMPUS', 'Campus SRC'),
                        ],
                        max_length=20
                    ),
                ),
                (
                    'voted_at',
                    models.DateTimeField(auto_now_add=True)
                ),
                (
                    'election',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='voter_receipts',
                        to='voting.election'
                    )
                ),
                (
                    'voter',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='voter_receipts',
                        to=settings.AUTH_USER_MODEL
                    )
                ),
            ],
        ),

        migrations.RunPython(
            create_voter_receipts,
            migrations.RunPython.noop
        ),

        migrations.AddConstraint(
            model_name='voterreceipt',
            constraint=models.UniqueConstraint(
                fields=('voter', 'election', 'src_category'),
                name='one_receipt_per_category_per_election'
            ),
        ),

        migrations.RemoveConstraint(
            model_name='vote',
            name='one_vote_per_category_per_election',
        ),

        migrations.RemoveField(
            model_name='vote',
            name='voter',
        ),
    ]
