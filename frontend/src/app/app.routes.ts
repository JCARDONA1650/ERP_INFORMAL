import { Routes } from '@angular/router';

import { authGuard, guestGuard, roleGuard, sessionGuard } from './core/auth/auth.guards';

export const routes: Routes = [
  {
    path: 'login',
    canActivate: [guestGuard],
    title: 'Iniciar sesión · INFORMAL ERP',
    loadComponent: () => import('./features/auth/login/login').then((m) => m.Login),
  },
  {
    path: 'privacidad',
    title: 'Política de datos · INFORMAL ERP',
    loadComponent: () => import('./features/legal/privacy').then((m) => m.Privacy),
  },
  {
    path: 'cambiar-clave',
    canActivate: [sessionGuard],
    title: 'Cambiar contraseña · INFORMAL ERP',
    loadComponent: () =>
      import('./features/auth/change-password/change-password').then((m) => m.ChangePassword),
  },
  {
    // Pública: el trabajador marca sin usuario; el QR firmado del día es su llave.
    path: 'marcar/:slug',
    title: 'Marcar asistencia · INFORMAL ERP',
    loadComponent: () => import('./features/mark/mark').then((m) => m.Mark),
  },
  {
    path: '',
    canActivate: [authGuard],
    loadComponent: () => import('./layout/shell/shell').then((m) => m.Shell),
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'inicio' },
      {
        path: 'inicio',
        title: 'Inicio · INFORMAL ERP',
        loadComponent: () => import('./features/home/home').then((m) => m.Home),
      },
      {
        path: 'asistencia',
        canActivate: [roleGuard('Supervisor', 'Administrador', 'RRHH')],
        title: 'Asistencia · INFORMAL ERP',
        loadComponent: () =>
          import('./features/attendance/attendance-list').then((m) => m.AttendanceList),
      },
      {
        path: 'marcar-asistido',
        canActivate: [roleGuard('Supervisor', 'Administrador')],
        title: 'Marcar por un trabajador · INFORMAL ERP',
        loadComponent: () =>
          import('./features/assisted-mark/assisted-mark').then((m) => m.AssistedMark),
      },
      {
        path: 'proyectos',
        pathMatch: 'full',
        canActivate: [roleGuard('Administrador', 'RRHH')],
        title: 'Proyectos · INFORMAL ERP',
        loadComponent: () => import('./features/projects/projects-page').then((m) => m.ProjectsPage),
      },
      {
        path: 'proyectos/qr',
        canActivate: [roleGuard('Supervisor', 'Administrador', 'RRHH')],
        title: 'QR de obra · INFORMAL ERP',
        loadComponent: () => import('./features/projects/project-qr').then((m) => m.ProjectQr),
      },
      {
        path: 'nomina',
        canActivate: [roleGuard('Administrador', 'RRHH')],
        title: 'Nómina · INFORMAL ERP',
        loadComponent: () => import('./features/payroll/period-list').then((m) => m.PeriodList),
      },
      {
        path: 'nomina/:id',
        canActivate: [roleGuard('Administrador', 'RRHH')],
        title: 'Periodo de nómina · INFORMAL ERP',
        loadComponent: () => import('./features/payroll/period-detail').then((m) => m.PeriodDetail),
      },
      {
        path: 'finanzas',
        canActivate: [roleGuard('Administrador')],
        title: 'Finanzas · INFORMAL ERP',
        loadComponent: () => import('./features/finance/finance-page').then((m) => m.FinancePage),
      },
      {
        path: 'reportes',
        canActivate: [roleGuard('Supervisor', 'Administrador', 'RRHH')],
        title: 'Reportes · INFORMAL ERP',
        loadComponent: () => import('./features/reports/reports-page').then((m) => m.ReportsPage),
      },
      {
        path: 'trabajadores',
        canActivate: [roleGuard('Administrador', 'RRHH')],
        title: 'Trabajadores · INFORMAL ERP',
        loadComponent: () => import('./features/employees/employees-page').then((m) => m.EmployeesPage),
      },
      {
        path: 'usuarios',
        canActivate: [roleGuard('Administrador')],
        title: 'Usuarios · INFORMAL ERP',
        loadComponent: () => import('./features/users/users-page').then((m) => m.UsersPage),
      },
      {
        path: 'forbidden',
        title: 'Sin permisos · INFORMAL ERP',
        loadComponent: () => import('./features/errors/forbidden').then((m) => m.Forbidden),
      },
    ],
  },
  {
    path: '**',
    title: 'No encontrada · INFORMAL ERP',
    loadComponent: () => import('./features/errors/not-found').then((m) => m.NotFound),
  },
];
