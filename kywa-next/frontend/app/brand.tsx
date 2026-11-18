import type { CSSProperties } from 'react';

// Deployment branding only. Risk and workflow status colors remain independent.
export type BrandColors = { original: string; button: string; buttonText: string; hover: string; darkText: string; lightText: string };
export type PublicBranding = { technical_support: boolean; primary: string; secondary: string; design: 'standard' | 'premium'; logo: string; website: string; department: string; email: string; phone: string; colors: BrandColors; secondary_colors: BrandColors };
// Neutral until /api/bootstrap supplies the selected institution. Never flash KYWA red.
export const brand = {
  name: '안전관리 시스템', shortName: '', logo: '', technical_support: false,
  department: '', email: '', phone: '', telephone: '',
  colors: { original: '#64748B', button: '#475569', buttonText: '#FFFFFF', hover: '#334155', darkText: '#CBD5E1', lightText: '#475569' },
};
export function variables(colors: BrandColors, secondary: BrandColors = colors) {
  return {
    '--brand-original': colors.original, '--brand-button': colors.button,
    '--brand-on-button': colors.buttonText, '--brand-hover': colors.hover,
    '--brand-dark-text': colors.darkText, '--brand-light-text': colors.lightText,
    '--brand-secondary-original': secondary.original,
    '--brand-secondary-dark-text': secondary.darkText, '--brand-secondary-light-text': secondary.lightText,
  } as CSSProperties;
}
export const brandVariables = variables(brand.colors);
export const themeStorageKey = 'safety-ui-theme';
