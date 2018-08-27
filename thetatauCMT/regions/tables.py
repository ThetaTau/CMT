import django_tables2 as tables


class RegionChapterTaskTable(tables.Table):
    task_name = tables.Column('task_name')
    task_owner = tables.Column('task_owner')
    school_type = tables.Column('school_type')
    date = tables.DateColumn(verbose_name="Due Date")

    class Meta:
        attrs = {'class': 'table table-striped table-hover'}
