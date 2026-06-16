"""Django admin registrations for the users app.

UserProfile is exposed both as a standalone model (so staff can find
"who has 0 credits left?" via filtering) and as an inline on the
default User admin (so the common workflow of "open user → bump
credits" is one click instead of two).
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Profile"
    fk_name = "user"


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "credits")
    search_fields = ("user__username", "user__email")
    list_filter = ("credits",)


# Re-register User with the profile inline. Unregister-then-register is
# the canonical Django pattern when you want to extend the default
# UserAdmin without subclassing every method.
class UserWithProfileAdmin(UserAdmin):
    inlines = [UserProfileInline]


admin.site.unregister(User)
admin.site.register(User, UserWithProfileAdmin)
