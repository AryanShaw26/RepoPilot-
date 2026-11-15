import { useEffect, useRef, type ReactNode } from "react";
import { X } from "lucide-react";
import { IconKey } from "./IconKey";

interface DialogProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
}

export function Dialog({ open, title, onClose, children }: DialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="dialog-title"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
      className="max-h-[90vh] w-[min(42rem,calc(100vw-2rem))] overflow-auto rounded-lg border border-edge bg-surface-raised p-0 text-ink shadow-e3 backdrop:bg-ink/40"
    >
      <header className="flex items-center justify-between border-b border-edge p-4">
        <h2 id="dialog-title" className="font-display text-xl">{title}</h2>
        <IconKey label="Close dialog" variant="ghost" onClick={onClose}>
          <X className="size-5" />
        </IconKey>
      </header>
      <div className="p-5">{children}</div>
    </dialog>
  );
}
