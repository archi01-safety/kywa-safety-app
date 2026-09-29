import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'KYWA 안전관리 | AI 위험성평가', description: '현장의 발견을 안전한 변화로. 한국청소년활동진흥원 위험성평가 시스템.' };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="ko"><body>{children}</body></html>;
}
