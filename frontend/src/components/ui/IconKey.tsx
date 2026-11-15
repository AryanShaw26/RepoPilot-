import type { ReactNode } from "react";
import { Button, type ButtonProps } from "./Button";

export interface IconKeyProps extends Omit<ButtonProps, "aria-label" | "children"> {
  label: string;
  children: ReactNode;
}

export function IconKey({ label, children, ...props }: IconKeyProps) {
  return (
    <Button size="icon" aria-label={label} title={label} {...props}>
      {children}
    </Button>
  );
}
