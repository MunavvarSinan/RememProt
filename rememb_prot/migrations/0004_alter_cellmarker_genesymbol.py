# Generated by Django 4.1.4 on 2023-02-24 06:16

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('rememb_prot', '0003_alter_remembprot_contxtofdiferentialreg_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cellmarker',
            name='geneSymbol',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='rememb_prot.remembprot'),
        ),
    ]
