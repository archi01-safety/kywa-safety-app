import type { CSSProperties } from 'react';

// Deployment branding only. Risk and workflow status colors remain independent.
export type BrandColors = { original: string; button: string; buttonText: string; hover: string; darkText: string; lightText: string };
export type PublicBranding = { primary: string; logo: string; website: string; department: string; email: string; phone: string; colors: BrandColors };
// Neutral until /api/bootstrap supplies the selected institution. Never flash KYWA red.
export const brand = {
  name: '안전관리 시스템', shortName: '', logo: '',
  department: '', email: '', phone: '', telephone: '',
  colors: { original: '#64748B', button: '#475569', buttonText: '#FFFFFF', hover: '#334155', darkText: '#CBD5E1', lightText: '#475569' },
};
export function variables(colors: BrandColors) {
  return {
    '--brand-original': colors.original, '--brand-button': colors.button,
    '--brand-on-button': colors.buttonText, '--brand-hover': colors.hover,
    '--brand-dark-text': colors.darkText, '--brand-light-text': colors.lightText,
  } as CSSProperties;
}
export const brandVariables = variables(brand.colors);
export const themeStorageKey = 'safety-ui-theme';
