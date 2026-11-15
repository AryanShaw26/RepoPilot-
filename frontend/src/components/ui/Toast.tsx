import { X } from "lucide-react";
import { IconKey } from "./IconKey";

interface ToastProps {
  message: string;
  tone?: "info" | "success" | "error";
  onDismiss: () => void;
}

const toneClasses = {
  info: "border-led-blue text-ink",
  success: "border-led-green text-ink",
  error: "border-led-red text-ink",
};

export function Toast({ message, tone = "info", onDismiss }: ToastProps) {
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      aria-live={tone === "error" ? "assertive" : "polite"}
      className={`fixed bottom-4 right-4 z-[100] flex max-w-[calc(100vw-2rem)] items-center gap-3 rounded-md border-l-4 bg-surface-raised px-4 py-3 shadow-e2 ${toneClasses[tone]}`}
    >
      <p className="text-sm">{message}</p>
      <IconKey label="Dismiss notification" variant="ghost" onClick={onDismiss}>
        <X className="size-4" />
      </IconKey>
    </div>
  );
}
