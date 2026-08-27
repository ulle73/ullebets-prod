import { LineChart, X } from 'lucide-react';
import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { formatOdds } from '../domain/formatters';
import type { AutoSelection } from '../domain/types';

function checkpointLabel(value: string | null | undefined): string {
  return value?.replace('T_MINUS_', 'T-').replace(/M$/, '').replace(/H$/, 'H').replace(/D$/, 'D') ?? 'Okänd';
}

function observedAtLabel(value: string | null): string {
  if (!value) return 'Tid saknas';
  return new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Europe/Stockholm',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
}

function marketLabel(row: AutoSelection): string {
  const direction = row.direction?.toLocaleUpperCase('sv-SE') ?? 'RIKTNING SAKNAS';
  const line = row.lineValue?.toLocaleString('sv-SE', { maximumFractionDigits: 2 }) ?? 'lina saknas';
  return `${direction} ${line}`;
}

export function OddsMovement({ row }: { row: AutoSelection }) {
  const [open, setOpen] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0, ready: false });
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const closeTimerRef = useRef<number | null>(null);
  const panelId = useId();
  const titleId = `${panelId}-title`;
  const history = row.oddsHistory ?? [];
  const selectedOdds = row.selectedOdds;

  const cancelClose = () => {
    if (closeTimerRef.current !== null) window.clearTimeout(closeTimerRef.current);
    closeTimerRef.current = null;
  };
  const scheduleClose = () => {
    cancelClose();
    if (pinned) return;
    closeTimerRef.current = window.setTimeout(() => setOpen(false), 120);
  };

  useLayoutEffect(() => {
    if (!open || !triggerRef.current) return;
    const updatePosition = () => {
      const trigger = triggerRef.current?.getBoundingClientRect();
      if (!trigger) return;
      const panelWidth = Math.min(360, window.innerWidth - 24);
      const panelHeight = panelRef.current?.getBoundingClientRect().height ?? 310;
      const below = trigger.bottom + 8;
      const top = below + panelHeight <= window.innerHeight - 12
        ? below
        : Math.max(12, trigger.top - panelHeight - 8);
      const left = Math.min(
        Math.max(12, trigger.right - panelWidth),
        Math.max(12, window.innerWidth - panelWidth - 12),
      );
      setPosition({ top, left, ready: true });
    };
    updatePosition();
    window.addEventListener('resize', updatePosition);
    window.addEventListener('scroll', updatePosition, true);
    return () => {
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      setPinned(false);
      setOpen(false);
    };
    const closeOutside = (event: PointerEvent) => {
      const target = event.target as Node;
      if (triggerRef.current?.contains(target) || panelRef.current?.contains(target)) return;
      setPinned(false);
      setOpen(false);
    };
    document.addEventListener('keydown', closeOnEscape);
    document.addEventListener('pointerdown', closeOutside);
    return () => {
      document.removeEventListener('keydown', closeOnEscape);
      document.removeEventListener('pointerdown', closeOutside);
    };
  }, [open]);

  useEffect(() => () => cancelClose(), []);

  const togglePinned = () => {
    cancelClose();
    setPinned((current) => {
      const next = !current;
      setOpen(next || !open);
      return next;
    });
  };
  const matchName = `${row.homeTeamName ?? 'hemmalag'} mot ${row.awayTeamName ?? 'bortalag'}`;

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className="odds-movement__trigger"
        aria-label={`Visa oddsrörelse för ${matchName}`}
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        aria-haspopup="dialog"
        onClick={togglePinned}
        onPointerEnter={() => { cancelClose(); setOpen(true); }}
        onPointerLeave={scheduleClose}
        onFocus={() => { cancelClose(); setOpen(true); }}
        onBlur={scheduleClose}
      >
        <strong>{selectedOdds === null ? '—' : formatOdds(selectedOdds)}</strong>
        <LineChart size={12} aria-hidden="true" />
      </button>
      {open ? createPortal(
        <div
          ref={panelRef}
          id={panelId}
          className="odds-movement__panel"
          role="dialog"
          aria-labelledby={titleId}
          style={{ top: position.top, left: position.left, visibility: position.ready ? 'visible' : 'hidden' }}
          onPointerEnter={cancelClose}
          onPointerLeave={scheduleClose}
        >
          <header className="odds-movement__header">
            <div>
              <h3 id={titleId}>Oddsrörelse & closing</h3>
              <p>Exakt marknad · {marketLabel(row)}</p>
            </div>
            <button type="button" aria-label="Stäng oddsrörelse" onClick={() => { setPinned(false); setOpen(false); }}><X size={14} aria-hidden="true" /></button>
          </header>
          {history.length > 0 ? (
            <ol className="odds-movement__timeline">
              {history.map((point, index) => (
                <li className={point.closing ? 'is-closing' : point.selected ? 'is-selected' : ''} key={`${point.snapshotLabel ?? 'snapshot'}:${point.observedAt ?? index}:${point.odds}`}>
                  <span className="odds-movement__dot" aria-hidden="true" />
                  <div>
                    <strong>{checkpointLabel(point.snapshotLabel)}</strong>
                    <small>{observedAtLabel(point.observedAt)}</small>
                  </div>
                  <b>{formatOdds(point.odds)}</b>
                  <span className="odds-movement__tag">{point.closing ? 'CLOSE' : point.selected ? 'SPEL' : ''}</span>
                </li>
              ))}
            </ol>
          ) : <p className="odds-movement__empty">Ingen sparad oddshistorik för exakt marknad.</p>}
          <footer className="odds-movement__footer">
            <span>Spel {selectedOdds === null ? '—' : formatOdds(selectedOdds)}</span>
            <span>Closing {row.closingOdds === null || row.closingOdds === undefined ? '—' : formatOdds(row.closingOdds)}</span>
          </footer>
        </div>,
        document.body,
      ) : null}
    </>
  );
}
