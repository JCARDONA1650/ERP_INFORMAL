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
  { label: 'Proyectos', path: '/proyectos', roles: ['Administrador', 'RRHH'] },
  { label: 'QR de obra', path: '/proyectos/qr', roles: ['Supervisor', 'Administrador', 'RRHH'] },
  { label: 'Nómina', path: '/nomina', roles: ['Administrador', 'RRHH'] },
  { label: 'Finanzas', path: '/finanzas', roles: ['Administrador'] },
  { label: 'Reportes', path: '/reportes', roles: ['Supervisor', 'Administrador', 'RRHH'] },
  { label: 'Trabajadores', path: '/trabajadores', roles: ['Administrador', 'RRHH'] },
] as const;
