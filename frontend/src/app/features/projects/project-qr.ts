import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';

import { ProjectSummary, ProjectsService } from '../../core/projects/projects.service';

@Component({
  selector: 'app-project-qr',
  templateUrl: './project-qr.html',
  styleUrl: './project-qr.scss',
})
export class ProjectQr implements OnInit, OnDestroy {
  private readonly api = inject(ProjectsService);

  protected readonly projects = signal<ProjectSummary[]>([]);
  protected readonly loading = signal(true);
  protected readonly selected = signal<ProjectSummary | null>(null);
  protected readonly qrUrl = signal<string | null>(null);
  protected readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.api.list().subscribe({
      next: (page) => {
        this.projects.set(page.results.filter((p) => p.active));
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
        this.error.set('No se pudieron cargar los proyectos.');
      },
    });
  }

  ngOnDestroy(): void {
    this.revoke();
  }

  protected show(project: ProjectSummary): void {
    this.error.set(null);
    this.revoke();
    this.selected.set(project);
    this.api.qr(project.id).subscribe({
      next: (blob) => {
        if (this.selected()?.id === project.id) this.qrUrl.set(URL.createObjectURL(blob));
      },
      error: () => this.error.set('No se pudo generar el QR.'),
    });
  }

  protected print(): void {
    window.print();
  }

  private revoke(): void {
    const url = this.qrUrl();
    if (url) URL.revokeObjectURL(url);
    this.qrUrl.set(null);
  }
}
