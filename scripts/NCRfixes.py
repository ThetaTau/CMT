from users.models import UserRoleChange


def run():
    users = UserRoleChange.objects.filter(role__contains="rush")
    for user in users:
        user.role = "recruitment chair"
        user.save()
    print(f"Changed {users.count()} users rush role")
    users = UserRoleChange.objects.filter(role__contains="academic")
    for user in users:
        user.role = "scholarship chair"
        user.save()
    print(f"Changed {users.count()} users academic role")
