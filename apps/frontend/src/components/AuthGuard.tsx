'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';

const PUBLIC_PATHS = ['/login', '/'];

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (PUBLIC_PATHS.includes(pathname)) {
      setChecked(true);
      return;
    }
    const token = localStorage.getItem('access_token');
    if (!token) {
      localStorage.removeItem('refresh_token');
      router.replace('/login');
    } else {
      setChecked(true);
    }
  }, [pathname, router]);

  if (PUBLIC_PATHS.includes(pathname)) return <>{children}</>;
  if (!checked) return null;

  return <>{children}</>;
}
