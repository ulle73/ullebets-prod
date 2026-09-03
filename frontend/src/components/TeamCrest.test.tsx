import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { TeamCrest, teamCrestSources } from './TeamCrest';

describe('TeamCrest', () => {
  it('prefers the bundled team asset when an old image URL points at a known filename', () => {
    expect(teamCrestSources({ imageUrl: 'https://old.example/images/teams/2961.webp', teamId: null, teamKey: null })).toEqual([
      '/images/teams/2961.webp',
      '/images/teams/2961.png',
      'https://old.example/images/teams/2961.webp',
    ]);
  });

  it('resolves a bundled png from the team id when no image URL exists', () => {
    render(<TeamCrest name="Live Team" imageUrl={null} teamId={1} teamKey="team-key" />);
    const crest = screen.getByRole('img', { name: 'Live Team klubbmärke' });
    expect(crest.querySelector('img')).toHaveAttribute('src', '/images/teams/1.png');
  });

  it('can derive a numeric asset id from a tagged team key', () => {
    expect(teamCrestSources({ imageUrl: null, teamId: null, teamKey: 'opta:1644' })).toEqual([
      '/images/teams/1644.png',
      '/images/teams/1644.webp',
    ]);
  });

  it('starts from the first source again when the team changes', () => {
    const { rerender } = render(<TeamCrest name="First Team" imageUrl={null} teamId={1} />);
    const firstImage = screen.getByRole('img', { name: 'First Team klubbmärke' }).querySelector('img');
    fireEvent.error(firstImage as HTMLImageElement);
    expect(firstImage).toHaveAttribute('src', '/images/teams/1.webp');

    rerender(<TeamCrest name="Second Team" imageUrl={null} teamId={2} />);
    expect(screen.getByRole('img', { name: 'Second Team klubbmärke' }).querySelector('img')).toHaveAttribute('src', '/images/teams/2.png');
  });
});
