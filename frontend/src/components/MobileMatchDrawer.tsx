import type { ReactNode } from 'react';

interface MobileMatchDrawerProps {
  children: ReactNode;
}

export function MobileMatchDrawer({ children }: MobileMatchDrawerProps) {
  return <>{children}</>;
}
