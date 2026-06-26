const ROLE_PERMISSIONS: Record<string, string[]> = {
  admin: ['create:source', 'create:analysis', 'view:report', 'view:any:report', 'manage:users'],
  analyst: ['create:source', 'create:analysis', 'view:report'],
  viewer: ['view:report'],
}

export function can(userRole: string | undefined, permission: string): boolean {
  if (!userRole) return false
  const perms = ROLE_PERMISSIONS[userRole] ?? []
  return perms.includes(permission)
}
