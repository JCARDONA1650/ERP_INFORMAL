import { Component, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { I18n } from './core/i18n/i18n.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet],
  template: '<router-outlet />',
})
export class App {
  constructor() {
    inject(I18n).start();
  }
}
