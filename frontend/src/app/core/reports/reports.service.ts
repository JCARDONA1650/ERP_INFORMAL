import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, from, switchMap, throwError } from 'rxjs';

import { API_URL } from '../config/api';

export type ReportFormat = 'xlsx' | 'pdf';

export interface AttendanceReportParams {
  date_from: string;
  date_to: string;
  project?: number | null;
}

@Injectable({ providedIn: 'root' })
export class ReportsService {
  private readonly http = inject(HttpClient);

  payroll(periodId: number, fmt: ReportFormat): Observable<Blob> {
    return this.download(`/reports/payroll/${periodId}/${fmt}/`);
  }

  attendance(fmt: ReportFormat, p: AttendanceReportParams): Observable<Blob> {
    let params = new HttpParams().set('date_from', p.date_from).set('date_to', p.date_to);
    if (p.project) params = params.set('project', p.project);
    return this.download(`/reports/attendance/${fmt}/`, params);
  }

  finance(projectId: number, fmt: ReportFormat, from_?: string, to?: string): Observable<Blob> {
    let params = new HttpParams();
    if (from_) params = params.set('date_from', from_);
    if (to) params = params.set('date_to', to);
    return this.download(`/reports/finance/${projectId}/${fmt}/`, params);
  }

  /** Registro detallado de ingresos y gastos; sin proyecto = todos los proyectos. */
  financeLedger(fmt: ReportFormat, f: { project?: number | null; date_from?: string; date_to?: string } = {}): Observable<Blob> {
    let params = new HttpParams();
    if (f.project) params = params.set('project', f.project);
    if (f.date_from) params = params.set('date_from', f.date_from);
    if (f.date_to) params = params.set('date_to', f.date_to);
    return this.download(`/reports/finance/ledger/${fmt}/`, params);
  }

  /** Con responseType blob, el cuerpo del error también llega como Blob: se vuelve a leer como JSON. */
  private download(path: string, params?: HttpParams): Observable<Blob> {
    return this.http.get(`${API_URL}${path}`, { params, responseType: 'blob' }).pipe(
      catchError((err: unknown) => {
        if (err instanceof HttpErrorResponse && err.error instanceof Blob) {
          return from(err.error.text()).pipe(
            switchMap((text) => {
              let body: unknown = null;
              try {
                body = JSON.parse(text);
              } catch {
                /* cuerpo no JSON */
              }
              return throwError(
                () => new HttpErrorResponse({ status: err.status, statusText: err.statusText, error: body, url: err.url ?? undefined }),
              );
            }),
          );
        }
        return throwError(() => err);
      }),
    );
  }
}
