import django_tables2 as tables


def get_value_from_a(value):
    """
    <a href="/tasks/detail/15/">True</a>    --> True
    <a href="/tasks/detail/0/">0</a>        --> N/A
    <a href="/tasks/detail/0/"></a>         --> False
    :param value:
    :return:
    """
    if '<a href="/tasks/detail/0/">0' in value:
        return "N/A"
    elif '<a href="/tasks/detail/0/"></a>' in value:
        return False
    elif 'True' in value:
        return True
    return ""


class RegionChapterTaskTable(tables.Table):
    task_name = tables.Column('task_name')
    task_owner = tables.Column('task_owner')
    school_type = tables.Column('school_type')
    date = tables.DateColumn(verbose_name="Due Date")

    class Meta:
        attrs = {'class': 'table table-striped table-hover',
                 'td': {
                     'complete': lambda value: get_value_from_a(value)
                 }}
