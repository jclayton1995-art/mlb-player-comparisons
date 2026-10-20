import { useState } from 'react';
import { headshot } from '../api';

export function Avatar({ id, name, size = 36, className = '' }: { id: number; name: string; size?: number; className?: string }) {
  const [broken, setBroken] = useState(false);
  const initials = name.split(' ').filter(Boolean).map((p) => p[0]).slice(0, 2).join('');
  return (
    <span className={'avatar ' + className} style={{ width: size, height: size, fontSize: size * 0.36 }} aria-hidden="true">
      {broken ? initials : <img src={headshot(id, size * 2)} alt="" loading="lazy" onError={() => setBroken(true)} />}
    </span>
  );
}
