import { ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';

export function NotFoundPage() {
  return (
    <section className="not-found-page">
      <p className="eyebrow">404</p>
      <h2>Sidan kunde inte hittas</h2>
      <p>Adressen pekar inte på en giltig Ullebets-sida.</p>
      <Link className="primary-button" to="/oversikt"><ArrowLeft size={15} aria-hidden="true" />Till översikten</Link>
    </section>
  );
}
