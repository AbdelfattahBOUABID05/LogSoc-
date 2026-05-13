import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MAT_DIALOG_DATA, MatDialogRef, MatDialogModule } from '@angular/material/dialog';

export interface DialogData {
  title: string;
  message: string;
  placeholder?: string;
  inputType?: 'text' | 'password' | 'email';
  initialValue?: string;
  confirmText?: string;
  cancelText?: string;
  showInput?: boolean;
}

@Component({
  selector: 'app-custom-modal',
  standalone: true,
  imports: [CommonModule, FormsModule, MatDialogModule],
  template: `
    <div class="glass-card w-full max-w-lg overflow-hidden border-none shadow-[0_20px_50px_rgba(0,0,0,0.5)] animate-slide-up bg-[#001f3f]/95 backdrop-blur-xl">
      <div class="p-8 border-b border-slate-200 dark:border-white/5 bg-white/50 dark:bg-white/5 flex justify-between items-center">
        <div class="flex items-center gap-4">
          <div class="w-12 h-12 rounded-2xl bg-indigo-600/10 flex items-center justify-center text-indigo-600 border border-indigo-600/20 shadow-xl">
            <i class="fas fa-info-circle text-xl"></i>
          </div>
          <div>
            <h3 class="font-black text-xl text-slate-900 dark:text-white uppercase tracking-wider italic">
              {{ data.title }}
            </h3>
            <p class="text-[10px] text-slate-500 dark:text-white/30 font-black uppercase tracking-[0.2em] mt-1">
              Action Système SOC
            </p>
          </div>
        </div>
        <button (click)="onCancel()" class="w-10 h-10 rounded-xl bg-slate-100 dark:bg-white/5 flex items-center justify-center text-slate-400 hover:text-red-500 transition-all border border-transparent hover:border-red-500/20">
          <i class="fas fa-times"></i>
        </button>
      </div>
      
      <div class="p-10 space-y-6">
        <p class="text-slate-600 dark:text-white/60 font-medium tracking-tight">
          {{ data.message }}
        </p>

        <div *ngIf="data.showInput" class="space-y-3">
          <label class="block text-[10px] font-black text-slate-500 dark:text-white/30 uppercase tracking-[0.2em] ml-1">
            {{ data.placeholder || 'Saisie requise' }}
          </label>
          <div class="relative group/input">
            <i class="fas fa-edit absolute left-5 top-5 text-slate-400 group-focus-within/input:text-indigo-500 transition-colors"></i>
            <input [type]="data.inputType || 'text'" [(ngModel)]="inputValue"
                   class="w-full pl-12 pr-5 py-4 bg-slate-50 dark:bg-white/5 border border-slate-200 dark:border-white/10 rounded-2xl focus:ring-2 focus:ring-indigo-500/50 outline-none transition-all text-indigo-900 dark:text-white font-bold placeholder-slate-400"
                   [placeholder]="data.placeholder || ''"
                   (keyup.enter)="onConfirm()">
          </div>
        </div>

        <div class="pt-8 flex gap-4">
          <button type="button" (click)="onCancel()"
                  class="flex-1 px-8 py-5 border border-slate-200 dark:border-white/10 text-slate-500 dark:text-white/40 font-black uppercase tracking-[0.2em] text-xs rounded-2xl hover:bg-white dark:hover:bg-white/10 transition-all">
            {{ data.cancelText || 'Annuler' }}
          </button>
          <button type="button" (click)="onConfirm()"
                  class="flex-1 px-8 py-5 bg-indigo-600 text-white font-black uppercase tracking-[0.2em] text-xs rounded-2xl hover:bg-indigo-700 transition-all shadow-[0_10px_20px_rgba(79,70,229,0.3)]">
            {{ data.confirmText || 'Confirmer' }}
          </button>
        </div>
      </div>
    </div>
  `,
  styles: [`
    :host {
      display: block;
      background: transparent;
    }
  `]
})
export class CustomModalComponent {
  inputValue: string;

  constructor(
    public dialogRef: MatDialogRef<CustomModalComponent>,
    @Inject(MAT_DIALOG_DATA) public data: DialogData
  ) {
    this.inputValue = data.initialValue || '';
  }

  onCancel(): void {
    this.dialogRef.close(null);
  }

  onConfirm(): void {
    if (this.data.showInput) {
      this.dialogRef.close(this.inputValue);
    } else {
      this.dialogRef.close(true);
    }
  }
}
