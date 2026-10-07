"use client";
import { useEffect, useState } from 'react';
import { Sun, Moon } from 'lucide-react';
import { themeStorageKey } from './brand';

export function ThemeToggle() {
  const [light, setLight] = useState(false);
  useEffect(() => { setLight(document.documentElement.dataset.theme === 'light'); }, []);
  function toggle() {
    const next = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
    document.documentElement.dataset.theme = next;
    setLight(next === 'light');
    try { localStorage.setItem(themeStorageKey, next); } catch { /* Theme still works for this visit. */ }
  }
  return <button type="button" className="theme-toggle" aria-label="밝은 테마" aria-pressed={light} title={light ? '어두운 테마로 전환' : '밝은 테마로 전환'} onClick={toggle}><Sun className="theme-sun" size={19}/><Moon className="theme-moon" size={19}/></button>;
}
