export type Role = 'SuperAdmin' | 'Administrador' | 'RRHH' | 'Supervisor';

export interface User {
  id: number;
  username: string;
  full_name: string;
  roles: Role[];
  /** Contraseña temporal: debe cambiarla antes de usar la app. */
  must_change_password?: boolean;
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
