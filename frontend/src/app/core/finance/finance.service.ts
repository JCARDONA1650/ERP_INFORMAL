import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { API_URL } from '../config/api';
import { Page } from '../models/page';

export type MovementKind = 'incomes' | 'expenses';

export const EXPENSE_CATEGORIES: readonly { value: string; label: string }[] = [
  { value: 'materials', label: 'Materiales' },
  { value: 'transport', label: 'Transporte' },
  { value: 'meals', label: 'Comida' },
  { value: 'tools', label: 'Herramientas' },
  { value: 'payroll', label: 'Nómina' },
  { value: 'other', label: 'Otros' },
];

export interface Movement {
  id: number;
  project: number;
  date: string;
  amount: string;
  currency: string;
  description: string;
  created_by: string | null;
  created_at: string;
  category?: string;
}

export interface MovementBody {
  project?: number;
  date: string;
  amount: string;
  currency?: string;
  description: string;
  category?: string;
}

export interface FinanceSummary {
  project: { id: number; name: string };
  contract: { value: string; currency: string; billed_pct: string | null };
  incomes: Record<string, string>;
  expenses: Record<string, string>;
  balance: Record<string, string>;
  expenses_by_category: { category: string; currency: string; total: string }[];
}

export interface MovementFilters {
  project: number;
  date_from?: string;
  date_to?: string;
  page?: number;
}

@Injectable({ providedIn: 'root' })
export class FinanceService {
  private readonly http = inject(HttpClient);

  summary(project: number, from?: string, to?: string): Observable<FinanceSummary> {
    let params = new HttpParams();
    if (from) params = params.set('date_from', from);
    if (to) params = params.set('date_to', to);
    return this.http.get<FinanceSummary>(`${API_URL}/projects/${project}/finance/`, { params });
  }

  list(kind: MovementKind, f: MovementFilters): Observable<Page<Movement>> {
    let params = new HttpParams().set('project', f.project);
    if (f.date_from) params = params.set('date_from', f.date_from);
    if (f.date_to) params = params.set('date_to', f.date_to);
    if (f.page && f.page > 1) params = params.set('page', f.page);
    return this.http.get<Page<Movement>>(`${API_URL}/finance/${kind}/`, { params });
  }

  create(kind: MovementKind, body: MovementBody): Observable<Movement> {
    return this.http.post<Movement>(`${API_URL}/finance/${kind}/`, body);
  }

  update(kind: MovementKind, id: number, body: MovementBody): Observable<Movement> {
    return this.http.patch<Movement>(`${API_URL}/finance/${kind}/${id}/`, body);
  }
}
