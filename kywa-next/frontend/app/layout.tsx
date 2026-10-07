import type { Metadata } from 'next';
import { brand, brandVariables, themeStorageKey } from './brand';
import './globals.css';
export const metadata: Metadata = { title: `${brand.shortName} 안전관리 | AI 위험성평가`, description: `현장의 발견을 안전한 변화로. ${brand.name} 위험성평가 시스템.` };
const initializeTheme = `try{var t=localStorage.getItem(${JSON.stringify(themeStorageKey)});document.documentElement.dataset.theme=t==='light'?'light':'dark'}catch(e){document.documentElement.dataset.theme='dark'}`;
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="ko" data-theme="dark" style={brandVariables} suppressHydrationWarning><head><script dangerouslySetInnerHTML={{ __html: initializeTheme }}/></head><body>{children}</body></html>;
}
