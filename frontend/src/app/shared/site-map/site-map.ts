import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnDestroy,
  effect,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';
import * as L from 'leaflet';

export interface MapPoint {
  lat: number;
  lng: number;
}

/** Punto adicional (p. ej. una marcación). `ok`: true dentro de la zona, false fuera, null sin dato. */
export interface MapMarker extends MapPoint {
  label: string;
  ok?: boolean | null;
}

const TILES = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a>';
const DEFAULT_VIEW: L.LatLngExpression = [27.8, -82.5]; // Florida, cuando aún no hay punto
const COLORS = { ok: '#3fb97a', bad: '#e04535', none: '#8a96a4' };

/**
 * Mapa Leaflet + OpenStreetMap con la zona de obra (punto + radio).
 * - `editable`: el punto se mueve con clic en el mapa o arrastrando; emite `pointChange`.
 * - `markers`: puntos extra de solo lectura (marcaciones).
 */
@Component({
  selector: 'app-site-map',
  template: `<div #host class="site-map" role="img" [attr.aria-label]="ariaLabel()" [style.height.px]="height()"></div>`,
  styles: `
    :host {
      display: block;
    }
    .site-map {
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 10px;
      overflow: hidden;
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SiteMap implements AfterViewInit, OnDestroy {
  readonly lat = input<number | null>(null);
  readonly lng = input<number | null>(null);
  readonly radius = input<number>(150);
  readonly editable = input(false);
  readonly markers = input<MapMarker[]>([]);
  readonly height = input(280);
  readonly ariaLabel = input('Mapa de la zona de obra');

  readonly pointChange = output<MapPoint>();

  private readonly host = viewChild.required<ElementRef<HTMLDivElement>>('host');
  private readonly ready = signal(false);

  private map?: L.Map;
  private center?: L.Marker;
  private circle?: L.Circle;
  private extras = L.layerGroup();
  private selfEmitted = false;

  constructor() {
    effect(() => {
      if (!this.ready()) return;
      this.draw(this.lat(), this.lng(), this.radius(), this.editable(), this.markers());
    });
  }

  ngAfterViewInit(): void {
    const map = L.map(this.host().nativeElement, { scrollWheelZoom: false }).setView(DEFAULT_VIEW, 6);
    L.tileLayer(TILES, { maxZoom: 19, attribution: ATTRIBUTION }).addTo(map);
    this.extras.addTo(map);
    map.on('click', (e: L.LeafletMouseEvent) => {
      if (this.editable()) this.emitPoint(e.latlng.lat, e.latlng.lng);
    });
    this.map = map;
    // El contenedor puede estar recién mostrado: se recalcula el tamaño para evitar teselas grises.
    setTimeout(() => map.invalidateSize(), 0);
    this.ready.set(true);
  }

  ngOnDestroy(): void {
    this.map?.remove();
  }

  private emitPoint(lat: number, lng: number): void {
    this.selfEmitted = true;
    this.pointChange.emit({ lat: Number(lat.toFixed(6)), lng: Number(lng.toFixed(6)) });
  }

  private draw(
    lat: number | null,
    lng: number | null,
    radius: number,
    editable: boolean,
    markers: MapMarker[],
  ): void {
    const map = this.map;
    if (!map) return;
    const fit = !this.selfEmitted;
    this.selfEmitted = false;

    this.center?.remove();
    this.circle?.remove();
    this.center = this.circle = undefined;
    this.extras.clearLayers();

    const hasPoint = lat !== null && lng !== null && Number.isFinite(lat) && Number.isFinite(lng);
    if (hasPoint) {
      const pos: L.LatLngExpression = [lat, lng];
      this.circle = L.circle(pos, {
        radius: Math.max(0, Number(radius) || 0),
        color: '#c9a84c',
        weight: 2,
        fillOpacity: 0.12,
      }).addTo(map);
      this.center = L.marker(pos, {
        draggable: editable,
        keyboard: editable,
        icon: L.divIcon({ className: 'site-pin', iconSize: [18, 18], iconAnchor: [9, 9] }),
      }).addTo(map);
      this.center.on('dragend', () => {
        const p = this.center!.getLatLng();
        this.emitPoint(p.lat, p.lng);
      });
    }

    for (const m of markers) {
      const color = m.ok === true ? COLORS.ok : m.ok === false ? COLORS.bad : COLORS.none;
      const tip = document.createElement('span');
      tip.textContent = m.label; // textContent: los nombres nunca se interpretan como HTML
      L.circleMarker([m.lat, m.lng], { radius: 7, color, fillColor: color, fillOpacity: 0.85, weight: 2 })
        .bindTooltip(tip)
        .addTo(this.extras);
    }

    if (!fit) return;
    if (this.circle) {
      map.fitBounds(this.circle.getBounds(), { maxZoom: 18, padding: [24, 24] });
    } else if (markers.length) {
      map.fitBounds(L.latLngBounds(markers.map((m) => [m.lat, m.lng] as L.LatLngTuple)), {
        maxZoom: 17,
        padding: [24, 24],
      });
    }
  }
}
