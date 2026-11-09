import { HttpErrorResponse, HttpInterceptorFn, HttpRequest } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, switchMap, throwError } from 'rxjs';

import { API_URL } from '../config/api';
import { AuthService } from './auth.service';

const PUBLIC_ENDPOINTS = [`${API_URL}/auth/login/`, `${API_URL}/auth/refresh/`];

const withToken = (req: HttpRequest<unknown>, token: string | null) =>
  token ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : req;

/** Agrega el Bearer a la API y, ante un 401, renueva el token una vez y reintenta. */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);

  if (!req.url.startsWith(API_URL) || PUBLIC_ENDPOINTS.some((u) => req.url.startsWith(u))) {
    return next(req);
  }

  return next(withToken(req, auth.accessToken())).pipe(
    catchError((error: unknown) => {
      if (!(error instanceof HttpErrorResponse) || error.status !== 401) {
        return throwError(() => error);
      }
      if (!auth.hasRefreshToken()) {
        auth.logout();
        return throwError(() => error);
      }
      return auth.refreshAccessToken().pipe(
        switchMap((token) => next(withToken(req, token))),
        catchError((refreshError: unknown) => {
          auth.logout();
          return throwError(() => refreshError);
        }),
      );
    }),
  );
};
