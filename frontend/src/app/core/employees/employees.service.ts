import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { API_URL } from '../config/api';
import { Page } from '../models/page';

export type PayType = 'hourly' | 'daily';

export interface Employee {
  id: number;
  document_id: string | null;
  full_name: string;
  position: string;
  pay_type: PayType;
  hourly_rate: string;
  daily_rate: string;
  currency: string;
  active: boolean;
}

export interface EmployeeBody {
  full_name: string;
  document_id: string | null;
  position: string;
  pay_type: PayType;
  daily_rate?: string;
  currency: string;
  initial_rate?: string;
  confirm_duplicate?: boolean;
}

export interface RateEntry {
  id: number;
  rate: string;
  effective_from: string;
  created_at: string;
}

export interface EmployeeFilters {
  search?: string;
  active?: 'true' | 'false' | '';
  page?: number;
}

@Injectable({ providedIn: 'root' })
export class EmployeesService {
  private readonly http = inject(HttpClient);
  private readonly base = `${API_URL}/employees/`;

  list(f: EmployeeFilters): Observable<Page<Employee>> {
    let params = new HttpParams();
    if (f.search?.trim()) params = params.set('search', f.search.trim());
    if (f.active) params = params.set('active', f.active);
    if (f.page && f.page > 1) params = params.set('page', f.page);
    return this.http.get<Page<Employee>>(this.base, { params });
  }

  create(body: EmployeeBody): Observable<Employee> {
    return this.http.post<Employee>(this.base, body);
  }

  update(id: number, body: Partial<EmployeeBody>): Observable<Employee> {
    return this.http.patch<Employee>(`${this.base}${id}/`, body);
  }

  setActive(id: number, active: boolean): Observable<Employee> {
    return this.http.post<Employee>(`${this.base}${id}/${active ? 'activate' : 'deactivate'}/`, {});
  }

  rates(id: number): Observable<RateEntry[]> {
    return this.http.get<RateEntry[]>(`${this.base}${id}/rates/`);
  }

  addRate(id: number, rate: string, effectiveFrom: string): Observable<RateEntry> {
    return this.http.post<RateEntry>(`${this.base}${id}/rates/`, { rate, effective_from: effectiveFrom });
  }
}
