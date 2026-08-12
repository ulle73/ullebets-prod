import { ChevronLeft, ChevronRight } from 'lucide-react';

interface PaginationBarProps {
  offset: number;
  limit: number;
  total: number;
  hasMore: boolean;
  onPageChange: (offset: number) => void;
}

export function PaginationBar({ offset, limit, total, hasMore, onPageChange }: PaginationBarProps) {
  if (total <= 0) return null;
  const start = Math.min(total, offset + 1);
  const end = Math.min(total, offset + limit);
  return (
    <nav className="pagination-bar" aria-label="Sidnavigering">
      <span>{start}–{end} av {total}</span>
      <div className="pagination-bar__actions">
        <button type="button" aria-label="Föregående sida" disabled={offset <= 0} onClick={() => onPageChange(Math.max(0, offset - limit))}>
          <ChevronLeft size={15} aria-hidden="true" />
          Föregående
        </button>
        <button type="button" aria-label="Nästa sida" disabled={!hasMore} onClick={() => onPageChange(offset + limit)}>
          Nästa
          <ChevronRight size={15} aria-hidden="true" />
        </button>
      </div>
    </nav>
  );
}
