import { Injectable, OnDestroy, signal } from '@angular/core';

import { EN_EXACT, EN_PATTERNS } from './en';

export type Lang = 'es' | 'en';

const STORAGE_KEY = 'informal.lang';
const ATTRS = ['placeholder', 'aria-label', 'title', 'alt'] as const;
const SKIP_TAGS = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEXTAREA']);

interface Pair {
  es: string;
  en: string;
}

/**
 * Traductor ES ↔ EN en tiempo de ejecución. La app se escribe en español; en inglés se
 * reemplazan los textos del DOM (nodos de texto y atributos) usando el diccionario `en.ts`.
 * Un MutationObserver traduce lo que Angular renderice después. Lo que no esté en el
 * diccionario se queda en español. El idioma se recuerda en localStorage.
 */
@Injectable({ providedIn: 'root' })
export class I18n implements OnDestroy {
  readonly lang = signal<Lang>(this.initial());

  private observer?: MutationObserver;
  private textPairs = new WeakMap<Node, Pair>();
  private attrPairs = new WeakMap<Element, Record<string, Pair>>();
  private titlePair?: Pair;
  private applying = false;

  /** Inicia el observador (se llama una vez al arrancar la app). */
  start(): void {
    if (this.observer || typeof document === 'undefined') return;
    document.documentElement.lang = this.lang();
    this.observer = new MutationObserver((records) => this.onMutations(records));
    this.observer.observe(document.documentElement, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
      attributeFilter: [...ATTRS],
    });
    this.applyAll();
  }

  ngOnDestroy(): void {
    this.observer?.disconnect();
    this.observer = undefined;
  }

  set(lang: Lang): void {
    if (lang === this.lang()) return;
    this.lang.set(lang);
    try {
      localStorage.setItem(STORAGE_KEY, lang);
    } catch {
      /* almacenamiento no disponible: el idioma solo dura la sesión */
    }
    if (typeof document !== 'undefined') {
      document.documentElement.lang = lang;
      this.applyAll();
    }
  }

  /** Traduce un texto en español a la lengua activa (útil para código TS). */
  t(es: string): string {
    return this.lang() === 'en' ? this.toEn(es) : es;
  }

  /** ES → EN conservando espacios en los bordes; devuelve el mismo texto si no hay traducción. */
  toEn(es: string): string {
    const key = es.replace(/\s+/g, ' ').trim();
    if (!key) return es;
    const lead = es.match(/^\s*/)?.[0] ?? '';
    const trail = es.match(/\s*$/)?.[0] ?? '';
    if (Object.hasOwn(EN_EXACT, key)) return lead + EN_EXACT[key] + trail;
    for (const [re, out] of EN_PATTERNS) {
      const m = key.match(re);
      if (!m) continue;
      const text =
        typeof out === 'function' ? out(m) : out.replace(/\{(\d+)\}/g, (_, i) => this.toEn(m[Number(i) + 1]));
      return lead + text + trail;
    }
    return es;
  }

  // ── DOM ──

  private applyAll(): void {
    if (typeof document === 'undefined') return;
    this.run(() => {
      this.walk(document.body);
      this.syncTitle();
    });
  }

  private onMutations(records: MutationRecord[]): void {
    if (this.applying) return;
    this.run(() => {
      for (const r of records) {
        if (r.type === 'characterData') {
          if (r.target.parentElement?.tagName === 'TITLE') this.syncTitle();
          else this.syncText(r.target);
        } else if (r.type === 'attributes') {
          this.syncAttr(r.target as Element, r.attributeName as string);
        } else {
          r.addedNodes.forEach((n) => {
            if (n.nodeType === Node.ELEMENT_NODE && (n as Element).tagName === 'TITLE') this.syncTitle();
            else this.walk(n);
          });
        }
      }
    });
  }

  private run(fn: () => void): void {
    this.applying = true;
    try {
      fn();
    } finally {
      // Los cambios propios llegan al observador de forma asíncrona: se ignoran por el par es/en.
      this.applying = false;
    }
  }

  private walk(node: Node): void {
    if (node.nodeType === Node.TEXT_NODE) {
      this.syncText(node);
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    const el = node as Element;
    if (SKIP_TAGS.has(el.tagName)) return;
    for (const a of ATTRS) if (el.hasAttribute(a)) this.syncAttr(el, a);
    el.childNodes.forEach((c) => this.walk(c));
  }

  private resolve(current: string, pair: Pair | undefined): Pair | null {
    const lang = this.lang();
    if (pair && current === pair.en && lang === 'en') return null; // ya traducido
    if (pair && current === pair.es && lang === 'es') return null; // ya en español
    // Si el valor actual es la traducción guardada y se vuelve a español, se restaura.
    if (pair && current === pair.en && lang === 'es') return { es: pair.es, en: pair.en };
    // Texto nuevo (Angular lo actualizó): se toma como español.
    return { es: current, en: this.toEn(current) };
  }

  private syncText(node: Node): void {
    const parent = node.parentElement;
    if (parent && SKIP_TAGS.has(parent.tagName)) return;
    const current = node.nodeValue ?? '';
    const prev = this.textPairs.get(node);
    const next = this.resolve(current, prev);
    if (!next) return;
    this.textPairs.set(node, next);
    const target = this.lang() === 'en' ? next.en : next.es;
    if (target !== current) node.nodeValue = target;
  }

  private syncAttr(el: Element, name: string): void {
    const current = el.getAttribute(name);
    if (current === null) return;
    const pairs = this.attrPairs.get(el) ?? {};
    const next = this.resolve(current, pairs[name]);
    if (!next) return;
    pairs[name] = next;
    this.attrPairs.set(el, pairs);
    const target = this.lang() === 'en' ? next.en : next.es;
    if (target !== current) el.setAttribute(name, target);
  }

  private syncTitle(): void {
    const current = document.title;
    const next = this.resolve(current, this.titlePair);
    if (!next) return;
    this.titlePair = next;
    const target = this.lang() === 'en' ? next.en : next.es;
    if (target !== current) document.title = target;
  }

  private initial(): Lang {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === 'en' || saved === 'es') return saved;
    } catch {
      /* sin almacenamiento */
    }
    return 'es';
  }
}
