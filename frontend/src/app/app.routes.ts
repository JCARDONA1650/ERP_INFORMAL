import { Routes } from '@angular/router';

import { authGuard, guestGuard, roleGuard } from './core/auth/auth.guards';

export const routes: Routes = [
  {
    path: 'login',
    canActivate: [guestGuard],
    title: 'Iniciar sesión · INFORMAL ERP',
    loadComponent: () => import('./features/auth/login/login').then((m) => m.Login),
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
