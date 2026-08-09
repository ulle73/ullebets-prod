import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import type { ReactNode } from 'react';

interface MobileMatchDrawerProps {
  children: ReactNode;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function MobileMatchDrawer({ children, open, onOpenChange }: MobileMatchDrawerProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="drawer-overlay" />
        <Dialog.Content id="mobile-match-drawer" className="drawer-content" aria-describedby={undefined}>
          <Dialog.Title className="sr-only">Dagens matcher</Dialog.Title>
          <Dialog.Close asChild>
            <button type="button" className="drawer-close" aria-label="Stäng matcher"><X size={20} /></button>
          </Dialog.Close>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
