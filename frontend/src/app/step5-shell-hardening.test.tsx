import { fireEvent, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '../test/render-app';

const dashboard={selectedDate:'2026-08-13',timezone:'Europe/Stockholm',generatedAt:'2026-08-12T20:00:00Z',matchupSource:'missing',matches:[],matchups:[]};

function shellFixtures(extra: Record<string, unknown> = {}) {
  return { '/api/v1/dashboard': dashboard, ...extra };
}

describe('step 5 shell hardening',()=>{
  it('offers a keyboard skip link that targets the main content',()=>{
    renderApp('/oversikt', shellFixtures());
    expect(screen.getByRole('link',{name:'Hoppa till huvudinnehåll'})).toHaveAttribute('href','#main-content');
    expect(screen.getByRole('main')).toHaveAttribute('id','main-content');
  });

  it('preserves only the shared date when moving between primary sections',()=>{
    renderApp('/resultatloop?date=2026-08-13&status=settled&stat=fouls&direction=over', shellFixtures({
      '/api/v1/auto':{count:0,rawCount:0,excludedComboLegCount:0,excludedShadowPredictionCount:0,collapsedDuplicateCount:0,summary:{total:0,valid:0,excluded:0},page:{limit:50,offset:0,hasMore:false},selections:[]},
    }));
    const nav=screen.getByRole('navigation',{name:'Huvudnavigation'});
    expect(within(nav).getByRole('link',{name:'Spel & resultat'})).toHaveAttribute('href','/auto?date=2026-08-13');
    expect(within(nav).queryByRole('link',{name:'Resultatloop'})).not.toBeInTheDocument();
  });

  it('keeps contextual model and system tools reachable inside the mobile drawer',()=>{
    renderApp('/oversikt', shellFixtures());
    fireEvent.click(screen.getByRole('button',{name:'Öppna matcher'}));
    const dialog=screen.getByRole('dialog');
    const mobileTools=within(dialog).getByRole('navigation',{name:'Verktyg i mobil'});
    expect(within(mobileTools).getByRole('link',{name:'Modell & proof'})).toHaveAttribute('href','/modell');
    expect(within(mobileTools).getByRole('link',{name:'Systemstatus'})).toHaveAttribute('href','/systemstatus');
  });

  it.each([
    '/oversikt',
    '/auto',
    '/watchlist',
    '/historik',
    '/matcher/m1',
    '/lag/team',
    '/liga/league',
    '/modell',
    '/systemstatus',
    '/saknas',
  ])('keeps route %s inside the styled application shell', (path) => {
    renderApp(path, shellFixtures());
    const main=screen.getByRole('main');
    expect(main).toBeInTheDocument();
    expect(main.childElementCount).toBeGreaterThan(0);
  });
});
