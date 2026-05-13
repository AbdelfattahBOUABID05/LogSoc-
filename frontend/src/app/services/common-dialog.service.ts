import { Injectable } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { Observable } from 'rxjs';
import { CustomModalComponent, DialogData } from '../components/shared/custom-modal/custom-modal.component';

@Injectable({
  providedIn: 'root'
})
export class CommonDialogService {
  constructor(private dialog: MatDialog) {}

  alert(title: string, message: string, confirmText: string = 'OK'): Observable<boolean> {
    const data: DialogData = {
      title,
      message,
      confirmText,
      showInput: false
    };

    return this.dialog.open(CustomModalComponent, {
      data,
      panelClass: 'custom-dialog-container',
      maxWidth: '500px',
      width: '100%',
      backdropClass: 'custom-dialog-backdrop'
    }).afterClosed();
  }

  confirm(title: string, message: string, confirmText: string = 'Confirmer', cancelText: string = 'Annuler'): Observable<boolean> {
    const data: DialogData = {
      title,
      message,
      confirmText,
      cancelText,
      showInput: false
    };

    return this.dialog.open(CustomModalComponent, {
      data,
      panelClass: 'custom-dialog-container',
      maxWidth: '500px',
      width: '100%',
      backdropClass: 'custom-dialog-backdrop'
    }).afterClosed();
  }

  prompt(title: string, message: string, placeholder: string = '', inputType: 'text' | 'password' | 'email' = 'text', initialValue: string = ''): Observable<string | null> {
    const data: DialogData = {
      title,
      message,
      placeholder,
      inputType,
      initialValue,
      showInput: true
    };

    return this.dialog.open(CustomModalComponent, {
      data,
      panelClass: 'custom-dialog-container',
      maxWidth: '500px',
      width: '100%',
      backdropClass: 'custom-dialog-backdrop'
    }).afterClosed();
  }
}
