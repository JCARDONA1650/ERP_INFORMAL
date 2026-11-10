import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { API_URL } from '../config/api';

export interface ScanContext {
  project: { name: string; slug: string };
  /** Zona de obra y política fuera de zona; null si el proyecto no tiene zona. */
  site: {
    latitude: number;
    longitude: number;
    radius_m: number;
    out_of_zone_policy: 'block' | 'review';
    address: string;
  } | null;
  employees: { id: number; full_name: string }[];
}

export interface ScanPayload {
  employee: number;
  action: 'in' | 'out';
  photo: File;
  clientUuid: string;
  latitude?: number;
  longitude?: number;
  deviceTs: string;
}

export interface ScanResult {
  message: string;
  duplicate: boolean;
  in_zone: boolean | null;
}

/** Marcación pública del trabajador (sin sesión): se valida con el token del QR. */
@Injectable({ providedIn: 'root' })
export class ScanService {
  private readonly http = inject(HttpClient);

  context(slug: string, token: string): Observable<ScanContext> {
    return this.http.get<ScanContext>(`${API_URL}/scan/${slug}/context/`, {
      params: new HttpParams().set('t', token),
    });
  }

  submit(slug: string, token: string, p: ScanPayload): Observable<ScanResult> {
    const body = new FormData();
    body.set('employee', String(p.employee));
    body.set('action', p.action);
    body.set('photo', p.photo);
    body.set('client_uuid', p.clientUuid);
    body.set('device_ts', p.deviceTs);
    if (p.latitude !== undefined && p.longitude !== undefined) {
      body.set('latitude', String(p.latitude));
      body.set('longitude', String(p.longitude));
    }
    return this.http.post<ScanResult>(`${API_URL}/scan/${slug}/`, body, {
      params: new HttpParams().set('t', token),
    });
  }
}
