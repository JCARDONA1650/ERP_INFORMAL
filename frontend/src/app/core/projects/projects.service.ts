import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { API_URL } from '../config/api';
import { Page } from '../models/page';

export interface ProjectSummary {
  id: number;
  name: string;
  slug: string;
  active: boolean;
}

/** `block` rechaza marcar fuera de la zona; `review` lo acepta y lo deja para revisión. */
export type OutOfZonePolicy = 'block' | 'review';

export interface ProjectSite {
  latitude: number | string;
  longitude: number | string;
  radius_m: number;
  out_of_zone_policy: OutOfZonePolicy;
  address: string;
}

/** Proyecto completo tal como lo devuelve la API de gestión. */
export interface Project extends ProjectSummary {
  contract_value: string;
  contract_currency: string;
  /** Si es true, toda marcación debe traer foto tomada en el momento. */
  photo_required: boolean;
  site: ProjectSite | null;
  supervisors: number[];
  employees: number[];
}

export interface ProjectBody {
  name?: string;
  contract_value?: string;
  contract_currency?: string;
  photo_required?: boolean;
  active?: boolean;
  site?: {
    latitude: number;
    longitude: number;
    radius_m: number;
    out_of_zone_policy: OutOfZonePolicy;
    address: string;
  } | null;
  supervisors?: number[];
  employees?: number[];
}

export interface AddressResult {
  label: string;
  latitude: number;
  longitude: number;
}

export interface SupervisorOption {
  id: number;
  username: string;
  full_name: string;
}

@Injectable({ providedIn: 'root' })
export class ProjectsService {
  private readonly http = inject(HttpClient);

  list(): Observable<Page<ProjectSummary>> {
    return this.http.get<Page<ProjectSummary>>(`${API_URL}/projects/`);
  }

  /** Lista completa para gestión (hasta 200 por página). */
  listFull(page = 1): Observable<Page<Project>> {
    let params = new HttpParams().set('page_size', 200);
    if (page > 1) params = params.set('page', page);
    return this.http.get<Page<Project>>(`${API_URL}/projects/`, { params });
  }

  create(body: ProjectBody): Observable<Project> {
    return this.http.post<Project>(`${API_URL}/projects/`, body);
  }

  update(id: number, body: ProjectBody): Observable<Project> {
    return this.http.patch<Project>(`${API_URL}/projects/${id}/`, body);
  }

  supervisors(): Observable<SupervisorOption[]> {
    return this.http.get<SupervisorOption[]>(`${API_URL}/users/supervisors/`);
  }

  /** Busca una dirección (hasta 5 resultados con coordenadas). */
  searchAddress(query: string): Observable<{ results: AddressResult[] }> {
    return this.http.get<{ results: AddressResult[] }>(`${API_URL}/geocode/search/`, { params: { q: query } });
  }

  /** Dirección aproximada de un punto del mapa. */
  reverseAddress(lat: number, lon: number): Observable<{ address: string }> {
    return this.http.get<{ address: string }>(`${API_URL}/geocode/reverse/`, {
      params: { lat: String(lat), lon: String(lon) },
    });
  }

  /** Enlace de marcación del día (lo que codifica el QR). */
  qrLink(id: number): Observable<{ url: string }> {
    return this.http.get<{ url: string }>(`${API_URL}/projects/${id}/qr-link/`);
  }

  /** QR del día (PNG). Requiere sesión, por eso se pide como blob. */
  qr(id: number): Observable<Blob> {
    return this.http.get(`${API_URL}/projects/${id}/qr/`, { responseType: 'blob' });
  }
}
