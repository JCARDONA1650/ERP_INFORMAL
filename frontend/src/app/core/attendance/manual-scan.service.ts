import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { API_URL } from '../config/api';
import { ScanResult } from '../scan/scan.service';

export interface ManualProject {
  id: number;
  name: string;
  photo_required: boolean;
  site: {
    latitude: number;
    longitude: number;
    radius_m: number;
    out_of_zone_policy: 'block' | 'review';
    address: string;
  } | null;
  employees: { id: number; full_name: string }[];
}

export interface ManualScanPayload {
  project: number;
  employee: number;
  action: 'in' | 'out';
  photo: File | null;
  clientUuid: string;
  deviceTs: string;
  latitude?: number;
  longitude?: number;
}

/** Marcación asistida: el Supervisor/Administrador registra a un trabajador sin celular. */
@Injectable({ providedIn: 'root' })
export class ManualScanService {
  private readonly http = inject(HttpClient);

  projects(): Observable<ManualProject[]> {
    return this.http.get<ManualProject[]>(`${API_URL}/attendance/manual/context/`);
  }

  submit(p: ManualScanPayload): Observable<ScanResult> {
    const body = new FormData();
    body.set('project', String(p.project));
    body.set('employee', String(p.employee));
    body.set('action', p.action);
    body.set('client_uuid', p.clientUuid);
    body.set('device_ts', p.deviceTs);
    if (p.photo) body.set('photo', p.photo);
    if (p.latitude !== undefined && p.longitude !== undefined) {
      body.set('latitude', String(p.latitude));
      body.set('longitude', String(p.longitude));
    }
    return this.http.post<ScanResult>(`${API_URL}/attendance/manual/`, body);
  }
}
