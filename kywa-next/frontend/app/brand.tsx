import type { CSSProperties } from 'react';

// Deployment branding only. Risk and workflow status colors remain independent.
export const brand = {
  name: '한국청소년활동진흥원', shortName: 'KYWA', logo: '/kywa_logo.png',
  department: '경영지원본부 안전경영부', email: 'archi01@kywa.or.kr',
  phone: '02-6959-7138', telephone: '0269597138',
  colors: { original: '#ED174F', button: '#C91546', hover: '#AA103A', darkText: '#FF6B91', lightText: '#B6103D' },
};
export const brandVariables = {
  '--brand-original': brand.colors.original, '--brand-button': brand.colors.button,
  '--brand-hover': brand.colors.hover, '--brand-dark-text': brand.colors.darkText,
  '--brand-light-text': brand.colors.lightText,
} as CSSProperties;
export const themeStorageKey = 'safety-ui-theme';
