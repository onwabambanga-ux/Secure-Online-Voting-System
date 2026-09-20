from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('voting', '0010_alter_election_election_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='candidate',
            name='campus',
            field=models.CharField(
                max_length=100,
                blank=True,
                null=True
            ),
        ),
    ]