export type Role = 'SuperAdmin' | 'Administrador' | 'RRHH' | 'Supervisor';

export interface User {
  id: number;
  username: string;
  full_name: string;
  roles: Role[];
}

export interface LoginResponse {
  access: string;
  refresh: string;
  user: User;
}

export interface RefreshResponse {
  access: string;
  refresh?: string;
}
