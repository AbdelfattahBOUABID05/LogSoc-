import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable, timer } from 'rxjs';
import { switchMap, take } from 'rxjs/operators';

@Injectable({
  providedIn: 'root'
})
export class LoadingService {
  private loadingSubject = new BehaviorSubject<boolean>(false);
  public loading$: Observable<boolean> = this.loadingSubject.asObservable();

  constructor() {}

  /**
   * Shows the loading overlay and automatically hides it after the specified duration
   * @param duration Duration in milliseconds (default: 1500ms)
   */
  showAndHide(duration: number = 1500): void {
    this.show();
    timer(duration).pipe(take(1)).subscribe(() => this.hide());
  }

  /**
   * Shows the loading overlay
   */
  show(): void {
    this.loadingSubject.next(true);
  }

  /**
   * Hides the loading overlay
   */
  hide(): void {
    this.loadingSubject.next(false);
  }
}