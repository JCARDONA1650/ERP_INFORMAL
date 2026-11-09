import { Routes } from '@angular/router';

import { authGuard, guestGuard } from './core/auth/auth.guards';

export const routes: Routes = [
  {
    path: 'login',
    canActivate: [guestGuard],
    title: 'Iniciar sesión · INFORMAL ERP',
    loadComponent: () => import('./features/auth/login/login').then((m) => m.Login),
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
