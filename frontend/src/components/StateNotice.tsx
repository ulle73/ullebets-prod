import { CircleAlert, Info, ShieldX } from 'lucide-react';
import type { ReadState } from '../domain/types';

export function StateNotice({ state, title, detail }: { state: ReadState; title: string; detail: string }) {
  const Icon = state === 'failed' ? CircleAlert : state === 'excluded' ? ShieldX : Info;
  return (
    <div className={`state-notice state-notice--${state}`} role={state === 'failed' ? 'alert' : 'status'}>
      <Icon size={17} aria-hidden="true" />
      <div><strong>{title}</strong><p>{detail}</p></div>
    </div>
  );
}
