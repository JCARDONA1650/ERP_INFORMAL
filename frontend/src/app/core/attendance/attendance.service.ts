import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { API_URL } from '../config/api';
import { Page } from '../models/page';

export interface Attendance {
  id: number;
  date: string;
  project: { id: number; name: string };
  employee: { id: number; full_name: string };
  check_in: string | null;
  check_out: string | null;
  check_in_source: string;
  check_out_source: string;
  in_zone: boolean | null;
  needs_review: boolean;
  reviewed_by: string | null;
  reviewed_at: string | null;
  manual_minutes: number | null;
  manual_note: string;
  worked_minutes: number;
  photo_url: string | null;
  notes: string;
}

export interface AttendanceFilters {
  project?: number | null;
  date_from?: string;
  date_to?: string;
  needs_review?: boolean;
  page?: number;
}

@Injectable({ providedIn: 'root' })
export class AttendanceService {
  private readonly http = inject(HttpClient);

  list(filters: AttendanceFilters): Observable<Page<Attendance>> {
    let params = new HttpParams();
    if (filters.project) params = params.set('project', filters.project);
    if (filters.date_from) params = params.set('date_from', filters.date_from);
    if (filters.date_to) params = params.set('date_to', filters.date_to);
    if (filters.needs_review) params = params.set('needs_review', 'true');
    if (filters.page && filters.page > 1) params = params.set('page', filters.page);
    return this.http.get<Page<Attendance>>(`${API_URL}/attendance/`, { params });
  }

  review(id: number): Observable<Attendance> {
    return this.http.post<Attendance>(`${API_URL}/attendance/${id}/review/`, {});
  }

  adjust(id: number, minutes: number, reason: string): Observable<Attendance> {
    return this.http.post<Attendance>(`${API_URL}/attendance/${id}/adjust/`, { minutes, reason });
  }

  /** La foto exige sesión: se pide con el interceptor y se muestra como blob. */
  photo(id: number): Observable<Blob> {
    return this.http.get(`${API_URL}/attendance/${id}/photo/`, { responseType: 'blob' });
  }
}
