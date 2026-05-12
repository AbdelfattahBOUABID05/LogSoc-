import { trigger, transition, style, query, animate, group, animateChild, sequence } from '@angular/animations';

export const slideUpFade = trigger('routeAnimations', [
  transition('* <=> *', [
    style({ position: 'relative' }),
    query(':enter, :leave', [
      style({
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        zIndex: 1
      })
    ], { optional: true }),
    
    query(':enter', [
      style({ opacity: 0, transform: 'scale(0.98)' })
    ], { optional: true }),

    sequence([
      query(':leave', [
        animate('400ms ease-in', style({ opacity: 0, transform: 'scale(1.02)' }))
      ], { optional: true }),
      query(':enter', [
        animate('500ms ease-out', style({ opacity: 1, transform: 'scale(1)' }))
      ], { optional: true })
    ])
  ])
]);

export const brandedTransition = trigger('brandedTransition', [
  transition('* => *', [
    style({ position: 'relative' }),
    
    // The branded overlay
    query('.brand-overlay', [
      style({ opacity: 0, transform: 'scale(1.2)' }),
      animate('400ms ease-out', style({ opacity: 1, transform: 'scale(1)' }))
    ], { optional: true }),

    group([
      query(':leave', [
        animate('300ms ease-in', style({ opacity: 0 }))
      ], { optional: true }),
      query(':enter', [
        style({ opacity: 0 }),
        animate('600ms 300ms ease-out', style({ opacity: 1 }))
      ], { optional: true })
    ]),

    query('.brand-overlay', [
      animate('400ms ease-in', style({ opacity: 0, transform: 'scale(0.8)' }))
    ], { optional: true })
  ])
]);

