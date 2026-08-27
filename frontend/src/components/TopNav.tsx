import { NavLink, useLocation } from 'react-router-dom';
import { sharedDateSearch } from '../domain/navigation';

const primaryRoutes = [
  { to: '/oversikt', label: 'Översikt' },
  { to: '/auto', label: 'Spel & resultat' },
  { to: '/watchlist', label: 'Watchlist' },
  { to: '/historik', label: 'Historik' },
] as const;

export function TopNav() {
  const location = useLocation();
  const sharedSearch = sharedDateSearch(location.search);
  return (
    <nav className="top-nav" aria-label="Huvudnavigation">
      {primaryRoutes.map((route) => (
        <NavLink key={route.to} to={`${route.to}${sharedSearch}`} className={({ isActive }) => `top-nav__link${isActive ? ' is-active' : ''}`}>
          {route.label}
        </NavLink>
      ))}
    </nav>
  );
}
