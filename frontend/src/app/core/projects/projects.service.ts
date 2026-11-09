import { HttpClient } from '@angular/common/http';
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

@Injectable({ providedIn: 'root' })
export class ProjectsService {
  private readonly http = inject(HttpClient);

  list(): Observable<Page<ProjectSummary>> {
    return this.http.get<Page<ProjectSummary>>(`${API_URL}/projects/`);
  }

  /** QR del día (PNG). Requiere sesión, por eso se pide como blob. */
  qr(id: number): Observable<Blob> {
    return this.http.get(`${API_URL}/projects/${id}/qr/`, { responseType: 'blob' });
  }
}
