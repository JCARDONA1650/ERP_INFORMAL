import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnDestroy,
  inject,
  output,
  signal,
  viewChild,
} from '@angular/core';

const MAX_SIDE = 1280;
const QUALITY = 0.8;

type CameraState = 'idle' | 'live' | 'captured';

/**
 * Captura de foto con la cámara en vivo (getUserMedia). A propósito NO hay selector de
 * archivos: la imagen solo puede venir de la cámara, en el momento, para dificultar que se
 * suba una foto ajena o antigua. Requiere HTTPS (o localhost) y permiso del navegador.
 */
@Component({
  selector: 'app-camera-capture',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="cam">
      @if (error(); as message) {
        <p class="cam__error" role="alert">{{ message }}</p>
      }

      <video
        #video
        class="cam__video"
        [hidden]="state() !== 'live'"
        autoplay
        playsinline
        muted
        aria-label="Vista previa de la cámara"
      ></video>

      @if (state() === 'captured' && previewUrl(); as url) {
        <img class="cam__preview" [src]="url" alt="Foto tomada" />
      }

      <div class="cam__actions">
        @switch (state()) {
          @case ('idle') {
            <button class="btn btn--ghost" type="button" (click)="open()">Abrir cámara</button>
          }
          @case ('live') {
            <button class="btn btn--primary" type="button" (click)="snap()">Tomar foto</button>
            <button class="btn btn--ghost" type="button" (click)="reset()">Cancelar</button>
          }
          @case ('captured') {
            <button class="btn btn--ghost" type="button" (click)="open()">Repetir foto</button>
          }
        }
      </div>
    </div>
  `,
  styles: `
    .cam {
      display: grid;
      gap: 0.6rem;
    }
    .cam__video,
    .cam__preview {
      width: 100%;
      max-height: 320px;
      object-fit: cover;
      border-radius: 10px;
      border: 1px solid var(--border);
      background: #000;
    }
    .cam__actions {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
    }
    .cam__error {
      margin: 0;
      padding: 0.6rem 0.8rem;
      border: 1px solid var(--danger);
      background: var(--danger-soft);
      color: #fca5a5;
      border-radius: 10px;
      font-size: 0.9rem;
    }
  `,
})
export class CameraCapture implements OnDestroy {
  /** Emite el archivo tomado, o null si se descarta. */
  readonly photo = output<File | null>();

  protected readonly state = signal<CameraState>('idle');
  protected readonly error = signal<string | null>(null);
  protected readonly previewUrl = signal<string | null>(null);

  private readonly video = viewChild.required<ElementRef<HTMLVideoElement>>('video');
  private stream: MediaStream | null = null;

  protected async open(): Promise<void> {
    this.error.set(null);
    this.discard();
    if (!navigator.mediaDevices?.getUserMedia) {
      this.error.set('Este navegador no permite usar la cámara aquí. Abre la app con HTTPS desde un celular.');
      return;
    }
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 } },
        audio: false,
      });
    } catch {
      this.error.set('No se pudo abrir la cámara. Permite el acceso a la cámara en el navegador.');
      return;
    }
    const el = this.video().nativeElement;
    el.srcObject = this.stream;
    await el.play().catch(() => undefined);
    this.state.set('live');
  }

  protected async snap(): Promise<void> {
    const el = this.video().nativeElement;
    if (!el.videoWidth || !el.videoHeight) {
      this.error.set('La cámara aún no está lista. Espera un segundo e inténtalo de nuevo.');
      return;
    }
    const scale = Math.min(1, MAX_SIDE / Math.max(el.videoWidth, el.videoHeight));
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(el.videoWidth * scale);
    canvas.height = Math.round(el.videoHeight * scale);
    canvas.getContext('2d')?.drawImage(el, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', QUALITY));
    if (!blob) {
      this.error.set('No se pudo tomar la foto. Inténtalo de nuevo.');
      return;
    }
    this.stopStream();
    const file = new File([blob], 'constancia.jpg', { type: 'image/jpeg' });
    this.previewUrl.set(URL.createObjectURL(blob));
    this.state.set('captured');
    this.photo.emit(file);
  }

  /** Vuelve al estado inicial (el padre lo llama tras enviar la marcación). */
  reset(): void {
    this.error.set(null);
    this.discard();
  }

  ngOnDestroy(): void {
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    const url = this.previewUrl();
    if (url) URL.revokeObjectURL(url);
  }

  private discard(): void {
    this.stopStream();
    const url = this.previewUrl();
    if (url) URL.revokeObjectURL(url);
    this.previewUrl.set(null);
    if (this.state() !== 'idle') this.photo.emit(null);
    this.state.set('idle');
  }

  private stopStream(): void {
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    this.video().nativeElement.srcObject = null;
  }
}
