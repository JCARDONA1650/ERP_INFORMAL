import { Role } from '../../core/auth/auth.models';

export interface NavItem {
  label: string;
  path: string;
  /** Roles que ven el ítem. Vacío = todos los autenticados. */
  roles: readonly Role[];
}

/** Menú lateral. Se agregan ítems a medida que existen las pantallas. */
export const NAV_ITEMS: readonly NavItem[] = [
  { label: 'Inicio', path: '/inicio', roles: [] },
  { label: 'Asistencia', path: '/asistencia', roles: ['Supervisor', 'Administrador', 'RRHH'] },
  { label: 'QR de obra', path: '/proyectos/qr', roles: ['Supervisor', 'Administrador', 'RRHH'] },
] as const;
