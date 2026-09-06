'use client';

import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';

export default function UserChip() {
  const { user } = useAuth();
  const email = user?.email ?? '';
  const initial = email.charAt(0).toUpperCase() || 'U';

  return (
    <Link href="/settings/profile" className="user-chip" style={{ textDecoration: 'none', color: 'inherit' }}>
      <div className="avatar">{initial}</div>
      <div>
        <div className="name">{email || 'User'}</div>
      </div>
    </Link>
  );
}
