import { NavLink, useLocation } from 'react-router-dom';

const primaryRoutes = [
  { to: '/oversikt', label: 'Översikt' },
  { to: '/auto', label: 'Auto' },
  { to: '/watchlist', label: 'Watchlist' },
  { to: '/resultatloop', label: 'Resultatloop' },
  { to: '/historik', label: 'Historik' },
] as const;

export function TopNav() {
  const location = useLocation();
  return (
    <nav className="top-nav" aria-label="Huvudnavigation">
      {primaryRoutes.map((route) => (
        <NavLink key={route.to} to={`${route.to}${location.search}`} className={({ isActive }) => `top-nav__link${isActive ? ' is-active' : ''}`}>
          {route.label}
        </NavLink>
      ))}
    </nav>
  );
}
