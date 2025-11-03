from rest_framework.throttling import UserRateThrottle

class RoleRateThrottle(UserRateThrottle):
    scope = 'role'
