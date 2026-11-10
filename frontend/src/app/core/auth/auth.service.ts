import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import {
  Observable,
  catchError,
  finalize,
  map,
  of,
  shareReplay,
  switchMap,
  tap,
  throwError,
} from 'rxjs';

import { API_URL } from '../config/api';
import { LoginResponse, RefreshResponse, Role, User } from './auth.models';

const REFRESH_KEY = 'informal.refresh';

/**
 * Sesión JWT. El access token vive solo en memoria; el refresh token se guarda en
 * localStorage para sobrevivir a recargas (compromiso habitual de una SPA).
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);

  private access: string | null = null;
  private refreshing$: Observable<string> | null = null;
  private readonly _user = signal<User | null>(null);

  readonly user = this._user.asReadonly();
  readonly isAuthenticated = computed(() => this._user() !== null);

  login(username: string, password: string): Observable<User> {
    return this.http
      .post<LoginResponse>(`${API_URL}/auth/login/`, { username, password })
      .pipe(
        tap((res) => {
          this.access = res.access;
          this.storeRefresh(res.refresh);
          this._user.set(res.user);
        }),
        map((res) => res.user),
      );
  }

  /** Cambia la contraseña propia; al terminar, la sesión deja de estar bloqueada. */
  changePassword(current: string, next: string): Observable<void> {
    return this.http
      .post(`${API_URL}/auth/change-password/`, { current_password: current, new_password: next })
      .pipe(
        tap(() => this._user.update((u) => (u ? { ...u, must_change_password: false } : u))),
        map(() => undefined),
      );
  }

  /** Recupera la sesión al arrancar la app a partir del refresh token guardado. */
  restoreSession(): Observable<boolean> {
    if (!this.hasRefreshToken()) return of(false);
    return this.refreshAccessToken().pipe(
      switchMap(() => this.http.get<User>(`${API_URL}/auth/me/`)),
      tap((user) => this._user.set(user)),
      map(() => true),
      catchError(() => {
        this.clear();
        return of(false);
      }),
    );
  }

  /** Renueva el access token; las llamadas simultáneas comparten una sola petición. */
  refreshAccessToken(): Observable<string> {
    const refresh = localStorage.getItem(REFRESH_KEY);
    if (!refresh) return throwError(() => new Error('Sin refresh token'));

    this.refreshing$ ??= this.http
      .post<RefreshResponse>(`${API_URL}/auth/refresh/`, { refresh })
      .pipe(
        tap((res) => {
          this.access = res.access;
          if (res.refresh) this.storeRefresh(res.refresh);
        }),
        map((res) => res.access),
        finalize(() => (this.refreshing$ = null)),
        shareReplay({ bufferSize: 1, refCount: false }),
      );
    return this.refreshing$;
  }

  logout(redirect = true): void {
    this.clear();
    if (redirect) void this.router.navigate(['/login']);
  }

  accessToken(): string | null {
    return this.access;
  }

  hasRefreshToken(): boolean {
    return localStorage.getItem(REFRESH_KEY) !== null;
  }

  /** El SuperAdmin pasa cualquier validación de rol. */
  hasAnyRole(roles: readonly Role[]): boolean {
    const user = this._user();
    if (!user) return false;
    return user.roles.includes('SuperAdmin') || roles.some((r) => user.roles.includes(r));
  }

  private storeRefresh(token: string): void {
    localStorage.setItem(REFRESH_KEY, token);
  }

  private clear(): void {
    this.access = null;
    this.refreshing$ = null;
    this._user.set(null);
    localStorage.removeItem(REFRESH_KEY);
  }
}
