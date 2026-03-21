from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Post

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('biography', 'avatar')}),
    )

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Post)