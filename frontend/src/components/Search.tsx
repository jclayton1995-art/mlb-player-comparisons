import { useEffect, useRef, useState } from 'react';
import { api, type SearchHit } from '../api';
import { Avatar } from './Avatar';

type Props = { onPick: (id: number, season: number) => void };

export function Search({ onPick }: Props) {
  const [q, setQ] = useState('');
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const ref = useRef<HTMLInputElement>(null);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        ref.current?.focus();
        ref.current?.select();
      }
    };
    const onClick = (e: MouseEvent) => {
      if (!box.current?.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    window.addEventListener('mousedown', onClick);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('mousedown', onClick);
    };
  }, []);

  useEffect(() => {
    let live = true;
    const t = setTimeout(() => {
      api.search(q).then((h) => {
        if (live) {
          setHits(h);
          setActive(0);
        }
      }).catch(() => {});
    }, 120);
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [q]);

  const pick = (h: SearchHit, season?: number) => {
    onPick(h.mlbam_id, season ?? h.latest_season);
    setOpen(false);
    setQ('');
    ref.current?.blur();
  };

  return (
    <div className="search" ref={box}>
      <svg className="search-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6">
        <circle cx="7" cy="7" r="4.5" />
        <path d="M10.5 10.5 14 14" strokeLinecap="round" />
      </svg>
      <input
        ref={ref}
        className="search-input"
        placeholder="Search a hitter"
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, hits.length - 1)); }
          if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
          if (e.key === 'Enter' && hits[active]) pick(hits[active]);
          if (e.key === 'Escape') setOpen(false);
        }}
        aria-label="Search a hitter"
      />
      {!open && <span className="search-kbd">⌘K</span>}
      {open && (
        <div className="search-pop" role="listbox">
          {hits.length === 0 && <div className="search-empty">No hitters match “{q}”. Try a last name.</div>}
          {hits.map((h, i) => (
            <button
              key={h.mlbam_id}
              className={'search-row' + (i === active ? ' active' : '')}
              onMouseEnter={() => setActive(i)}
              onClick={() => pick(h)}
              role="option"
              aria-selected={i === active}
            >
              <Avatar id={h.mlbam_id} name={h.name} size={36} />
              <div>
                <div className="nm">{h.name}</div>
                <div className="sub">
                  {h.seasons.length} season{h.seasons.length === 1 ? '' : 's'} on record
                  {h.career_wrc != null && <> &nbsp; career wRC+ {Math.round(h.career_wrc)}</>}
                </div>
              </div>
              <div className="yrs">
                {h.seasons.slice(-6).map((s) => (
                  <span
                    key={s}
                    className="yr"
                    onClick={(e) => {
                      e.stopPropagation();
                      pick(h, s);
                    }}
                  >
                    {s}
                  </span>
                ))}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
