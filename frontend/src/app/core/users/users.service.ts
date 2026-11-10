import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { API_URL } from '../config/api';

export interface ManagedUser {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  role: string | null;
  is_active: boolean;
  must_change_password: boolean;
  can_manage: boolean;
}

export interface UserList {
  /** Roles que el usuario actual puede asignar. */
  roles: string[];
  results: ManagedUser[];
}

export interface UserBody {
  username?: string;
  first_name?: string;
  last_name?: string;
  email?: string;
  role?: string;
  is_active?: boolean;
}

/** Gestión de usuarios (solo Administrador / Super Admin). */
@Injectable({ providedIn: 'root' })
export class UsersService {
  private readonly http = inject(HttpClient);

  list(): Observable<UserList> {
    return this.http.get<UserList>(`${API_URL}/users/`);
  }

  /** Devuelve la contraseña temporal una sola vez. */
  create(body: UserBody): Observable<ManagedUser & { temp_password: string }> {
    return this.http.post<ManagedUser & { temp_password: string }>(`${API_URL}/users/`, body);
  }

  update(id: number, body: UserBody): Observable<ManagedUser> {
    return this.http.patch<ManagedUser>(`${API_URL}/users/${id}/`, body);
  }

  resetPassword(id: number): Observable<{ temp_password: string }> {
    return this.http.post<{ temp_password: string }>(`${API_URL}/users/${id}/reset-password/`, {});
  }
}
