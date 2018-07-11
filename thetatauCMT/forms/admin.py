from django.contrib import admin
from .models import Badge, Guard, Initiation, Depledge, StatusChange
# Register your models here.


admin.site.register(Badge)
admin.site.register(Guard)
admin.site.register(Initiation)
admin.site.register(Depledge)
admin.site.register(StatusChange)
