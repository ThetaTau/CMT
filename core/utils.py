
def check_officer(request):
    if request.user.groups.filter(
            name__in=['officer', 'natoff']).exists():
        request.is_officer = True
    return request


def check_nat_officer(request):
    if request.user.groups.filter(name='natoff').exists():
        request.is_nat_officer = True
    return request
